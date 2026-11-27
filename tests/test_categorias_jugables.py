"""Disponibilidad del juego y protección transaccional del último banco jugable."""

from datetime import datetime, timezone

import pytest

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta, RolUsuario
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.repositories import categoria_repository
from app.services import autenticacion_service, duelo_service
from app.services.semilla_service import sembrar_preguntas_y_categorias
from tests.test_semilla_service import datos_pregunta


def crear_banco(db, nombre="Jugable", cantidad=10, estado=EstadoCategoria.ACTIVA):
    categoria = Categoria(nombre=nombre, estado=estado)
    db.add(categoria)
    db.flush()
    db.add_all([
        Pregunta(categoria_id=categoria.id, enunciado=f"{nombre} {n}", opcion_a="A",
                 opcion_b="B", opcion_c="C", opcion_d="D", respuesta_correcta="A")
        for n in range(cantidad)
    ])
    db.commit()
    return categoria


@pytest.fixture
def administrador(sesion_db):
    usuario = Usuario(nombre="Admin Banco", email="banco@test.com", password_hash="prueba", rol=RolUsuario.ADMINISTRADOR)
    sesion_db.add(usuario)
    sesion_db.commit()
    return {"Authorization": f"Bearer {autenticacion_service.generar_token_jwt(usuario)}"}


@pytest.mark.parametrize("ruta", ["/api/categorias", "/api/partidas/categorias"])
def test_listado_excluye_vacias_insuficientes_borradores_y_eliminadas(cliente, sesion_db, ruta):
    valida = crear_banco(sesion_db)
    crear_banco(sesion_db, "Vacia", 0)
    crear_banco(sesion_db, "Nueve", 9)
    crear_banco(sesion_db, "Borrador", 10, EstadoCategoria.BORRADOR)
    con_borrador = crear_banco(sesion_db, "Pregunta borrador", 10)
    sesion_db.query(Pregunta).filter_by(categoria_id=con_borrador.id).first().estado = EstadoPregunta.BORRADOR
    con_eliminada = crear_banco(sesion_db, "Pregunta eliminada", 10)
    sesion_db.query(Pregunta).filter_by(categoria_id=con_eliminada.id).first().eliminada_en = datetime.now(timezone.utc)
    sesion_db.commit()
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert [c["id"] for c in respuesta.json()] == [valida.id]
    for _ in range(10):
        assert categoria_repository.obtener_categoria_aleatoria(sesion_db).id == valida.id


@pytest.mark.parametrize("accion", ["categoria_estado", "categoria_editar", "categoria_eliminar",
                                    "pregunta_estado", "pregunta_editar", "pregunta_eliminar", "pregunta_mover"])
def test_rechazo_atomico_de_operaciones_que_quitan_ultima_jugable(cliente, sesion_db, administrador, accion):
    categoria = crear_banco(sesion_db)
    destino = crear_banco(sesion_db, "Destino", 0, EstadoCategoria.BORRADOR)
    pregunta = sesion_db.query(Pregunta).filter_by(categoria_id=categoria.id).first()
    categoria_id, pregunta_id = categoria.id, pregunta.id
    operaciones = {
        "categoria_estado": ("patch", f"/api/admin/categorias/{categoria_id}/estado", {"estado": "BORRADOR"}),
        "categoria_editar": ("patch", f"/api/admin/categorias/{categoria_id}", {"nombre": "Cambio revertido", "estado": "BORRADOR"}),
        "categoria_eliminar": ("delete", f"/api/admin/categorias/{categoria_id}", None),
        "pregunta_estado": ("patch", f"/api/admin/preguntas/{pregunta_id}/estado", {"estado": "BORRADOR"}),
        "pregunta_editar": ("patch", f"/api/admin/preguntas/{pregunta_id}", {"enunciado": "Cambio revertido", "estado": "BORRADOR"}),
        "pregunta_eliminar": ("delete", f"/api/admin/preguntas/{pregunta_id}", None),
        "pregunta_mover": ("patch", f"/api/admin/preguntas/{pregunta_id}", {"categoria_id": destino.id}),
    }
    metodo, ruta, datos = operaciones[accion]
    opciones = {"headers": administrador}
    if datos is not None:
        opciones["json"] = datos
    respuesta = getattr(cliente, metodo)(ruta, **opciones)
    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["code"] == "ULTIMA_CATEGORIA_JUGABLE"
    assert "Primero habilitá otra categoría" in respuesta.json()["message"]
    sesion_db.refresh(categoria)
    sesion_db.refresh(pregunta)
    assert categoria.estado == EstadoCategoria.ACTIVA
    assert categoria.nombre == "Jugable"
    assert pregunta.estado == EstadoPregunta.ACTIVA
    assert pregunta.eliminada_en is None
    assert pregunta.categoria_id == categoria_id
    assert pregunta.enunciado != "Cambio revertido"
    assert [c["id"] for c in cliente.get("/api/partidas/categorias").json()] == [categoria_id]


@pytest.mark.parametrize("accion", ["categoria_estado", "pregunta_eliminar", "pregunta_estado", "pregunta_mover"])
def test_permite_operacion_si_otra_categoria_sigue_jugable(cliente, sesion_db, administrador, accion):
    origen = crear_banco(sesion_db)
    otra = crear_banco(sesion_db, "Otra")
    pregunta = sesion_db.query(Pregunta).filter_by(categoria_id=origen.id).first()
    if accion == "categoria_estado":
        respuesta = cliente.patch(f"/api/admin/categorias/{origen.id}/estado", headers=administrador, json={"estado": "BORRADOR"})
    elif accion == "pregunta_eliminar":
        respuesta = cliente.delete(f"/api/admin/preguntas/{pregunta.id}", headers=administrador)
    elif accion == "pregunta_estado":
        respuesta = cliente.patch(f"/api/admin/preguntas/{pregunta.id}/estado", headers=administrador, json={"estado": "BORRADOR"})
    else:
        respuesta = cliente.patch(f"/api/admin/preguntas/{pregunta.id}", headers=administrador, json={"categoria_id": otra.id})
    assert respuesta.status_code == 200, respuesta.text
    assert [c["id"] for c in cliente.get("/api/categorias").json()] == [otra.id]


def test_mover_pregunta_puede_transferir_la_categoria_jugable(cliente, sesion_db, administrador):
    origen = crear_banco(sesion_db)
    destino = crear_banco(sesion_db, "Destino", 9)
    pregunta = sesion_db.query(Pregunta).filter_by(categoria_id=origen.id).first()
    respuesta = cliente.patch(f"/api/admin/preguntas/{pregunta.id}", headers=administrador, json={"categoria_id": destino.id})
    assert respuesta.status_code == 200
    assert [c["id"] for c in cliente.get("/api/categorias").json()] == [destino.id]


def test_permiso_se_basa_en_resultado_y_no_en_ultima_pregunta(cliente, sesion_db, administrador):
    categoria = crear_banco(sesion_db, cantidad=11)
    preguntas = sesion_db.query(Pregunta).filter_by(categoria_id=categoria.id).all()
    assert cliente.delete(f"/api/admin/preguntas/{preguntas[0].id}", headers=administrador).status_code == 200
    assert cliente.delete(f"/api/admin/preguntas/{preguntas[1].id}", headers=administrador).status_code == 409


def test_carga_inicial_y_administracion_conservan_categorias_no_jugables(cliente, sesion_db, administrador):
    assert cliente.get("/api/categorias").json() == []
    respuesta = cliente.post("/api/admin/categorias", headers=administrador, json={"nombre": "Inicial"})
    categoria_id = respuesta.json()["id"]
    vacia_id = cliente.post("/api/admin/categorias", headers=administrador, json={"nombre": "Vacia", "estado": "BORRADOR"}).json()["id"]
    assert len(cliente.get("/api/admin/categorias", headers=administrador).json()) == 2
    assert cliente.delete(f"/api/admin/categorias/{vacia_id}", headers=administrador).status_code == 200
    for n in range(10):
        r = cliente.post("/api/admin/preguntas", headers=administrador, json={
            "categoria_id": categoria_id, "enunciado": f"Inicial {n}", "opcion_a": "A",
            "opcion_b": "B", "opcion_c": "C", "opcion_d": "D", "respuesta_correcta": "A",
        })
        assert r.status_code == 201, r.text
        assert bool(cliente.get("/api/categorias").json()) == (n == 9)


def test_permite_editar_banco_incompleto_y_borrar_vacia_aunque_haya_otra(cliente, sesion_db, administrador):
    crear_banco(sesion_db, cantidad=9)
    pregunta = sesion_db.query(Pregunta).first()
    assert cliente.delete(f"/api/admin/preguntas/{pregunta.id}", headers=administrador).status_code == 200
    crear_banco(sesion_db, "Completa")
    vacia = crear_banco(sesion_db, "Vacia", 0)
    assert cliente.delete(f"/api/admin/categorias/{vacia.id}", headers=administrador).status_code == 200


def test_siembra_no_reactiva_borradores_y_no_duplica_en_mismo_lote(sesion_db):
    categoria = crear_banco(sesion_db, "Mundiales", 0, EstadoCategoria.BORRADOR)
    datos = datos_pregunta()
    resultado = sembrar_preguntas_y_categorias(sesion_db, [datos, datos])
    assert categoria.estado == EstadoCategoria.BORRADOR
    assert resultado["preguntas_creadas"] == 1
    assert resultado["preguntas_omitidas"] == 1
    assert not categoria_repository.hay_categoria_jugable(sesion_db)


def test_inicio_individual_respeta_categoria_elegida_y_duelos_ignoran_no_jugables(cliente, sesion_db, administrador):
    una = crear_banco(sesion_db)
    otra = crear_banco(sesion_db, "Otra")
    insuficiente = crear_banco(sesion_db, "Nueve", 9)
    respuesta = cliente.post("/api/partidas/individual", headers=administrador, json={"categoria_id": otra.id})
    assert respuesta.status_code == 201
    assert respuesta.json()["categoria_id"] == otra.id
    assert len(respuesta.json()["preguntas"]) == 10
    assert cliente.post("/api/partidas/individual", headers=administrador, json={"categoria_id": insuficiente.id}).status_code == 422
    # Al quedar una sola jugable, también los duelos locales y online la seleccionan.
    otra.estado = EstadoCategoria.BORRADOR
    sesion_db.commit()
    jugador = sesion_db.query(Usuario).first()
    assert duelo_service.iniciar_duelo_local(sesion_db, jugador, "Invitado").categoria_id == una.id
    assert duelo_service.buscar_o_crear_duelo_online(sesion_db, jugador).categoria_id == una.id

