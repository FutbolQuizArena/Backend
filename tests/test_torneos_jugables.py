"""Recorridos HTTP reales, aislamiento de duelos y recuperación de fallos de torneo."""

import pytest

from app.models.categoria import Categoria
from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoPartida, EstadoTorneo
from app.models.partida_duelo import PartidaDuelo
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.services import autenticacion_service, duelo_service, ranking_service, torneo_service
from app.schemas.torneo_schema import TorneoCreate, TorneoUnirseRequest


def encabezado(usuario):
    return {"Authorization": f"Bearer {autenticacion_service.generar_token_jwt(usuario)}"}


@pytest.fixture
def jugadores(sesion_db):
    usuarios = [Usuario(nombre=f"Jugador {n}", email=f"jugable{n}@test.com", password_hash="prueba") for n in range(16)]
    sesion_db.add_all(usuarios)
    categoria = Categoria(nombre="Preguntas jugables")
    sesion_db.add(categoria)
    sesion_db.flush()
    sesion_db.add_all([
        Pregunta(categoria_id=categoria.id, enunciado=f"Pregunta {n}", opcion_a="Correcta",
                 opcion_b="B", opcion_c="C", opcion_d="D", respuesta_correcta="A")
        for n in range(10)
    ])
    sesion_db.commit()
    return usuarios


def crear_torneo(db, jugadores, capacidad=4):
    torneo = torneo_service.crear_torneo(db, TorneoCreate(nombre="Copa jugable", cantidad_participantes=capacidad), jugadores[0])
    for usuario in jugadores[1:capacidad]:
        torneo_service.unirse_a_torneo(db, TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso), usuario)
    return torneo


def iniciar(cliente, torneo, cruce, usuario):
    respuesta = cliente.post(f"/api/torneos/{torneo.id}/cruces/{cruce.id}/iniciar-duelo", headers=encabezado(usuario))
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def responder(cliente, usuario, pregunta_id, opcion="A", tiempo=1):
    return cliente.post(f"/api/duelos/preguntas/{pregunta_id}/respuesta", headers=encabezado(usuario),
                        json={"opcion_seleccionada": opcion, "tiempo_respuesta_segundos": tiempo})


def disputar(cliente, torneo, cruce):
    usuario_a, usuario_b = cruce.jugador_a.usuario, cruce.jugador_b.usuario
    a = iniciar(cliente, torneo, cruce, usuario_a)
    b = iniciar(cliente, torneo, cruce, usuario_b)
    assert a["duelo_id"] == b["duelo_id"]
    assert len(a["duelo"]["preguntas"]) == len(b["duelo"]["preguntas"]) == 10
    assert {p["id"] for p in a["duelo"]["preguntas"]}.isdisjoint({p["id"] for p in b["duelo"]["preguntas"]})
    for preguntas, usuario, opcion in [(a["duelo"]["preguntas"], usuario_a, "A"), (b["duelo"]["preguntas"], usuario_b, None)]:
        for p in preguntas:
            assert "respuesta_correcta" not in p
            respuesta = responder(cliente, usuario, p["id"], opcion)
            assert respuesta.status_code == 200, respuesta.text
    return a["duelo_id"]


@pytest.mark.parametrize("capacidad", [4, 8, 16])
def test_torneo_completo_por_http_avanza_sin_resolver_manualmente(cliente, sesion_db, jugadores, capacidad):
    torneo = crear_torneo(sesion_db, jugadores, capacidad)
    ronda = 1
    puntos_esperados = {u.id: 0 for u in jugadores}
    while torneo.estado != EstadoTorneo.FINALIZADO:
        cruces = sesion_db.query(Cruce).filter_by(torneo_id=torneo.id, ronda=ronda).order_by(Cruce.id).all()
        assert len(cruces) == capacidad // 2 ** ronda
        for cruce in cruces:
            ganador_id = cruce.jugador_a.usuario_id
            duelo_id = disputar(cliente, torneo, cruce)
            sesion_db.refresh(cruce)
            assert cruce.estado == EstadoCruce.JUGADO
            assert cruce.ganador.usuario_id == ganador_id
            puntos_esperados[ganador_id] += 950  # 10 respuestas correctas en un segundo.
            # Reintentar desde ambos clientes no crea rondas ni puntos adicionales.
            for usuario in (cruce.jugador_a.usuario, cruce.jugador_b.usuario):
                r = cliente.post(f"/api/torneos/{torneo.id}/cruces/{cruce.id}/resolver", headers=encabezado(usuario), json={"duelo_id": duelo_id})
                assert r.status_code == 200, r.text
            sesion_db.refresh(torneo)
        ronda += 1
    puntos_esperados[ganador_id] += 1500
    assert sesion_db.query(Cruce).filter_by(torneo_id=torneo.id).count() == capacidad - 1
    for usuario in jugadores:
        sesion_db.refresh(usuario)
        assert usuario.puntaje_total == puntos_esperados[usuario.id]


def test_retomar_cruce_aisla_duelos_anteriores_y_preguntas(cliente, sesion_db, jugadores):
    torneo = crear_torneo(sesion_db, jugadores)
    cruce = torneo.cruces[0]
    anterior = PartidaDuelo(jugador1_id=cruce.jugador_a.usuario_id, jugador2_id=cruce.jugador_b.usuario_id,
                           estado=EstadoPartida.FINALIZADA, modalidad="ONLINE")
    sesion_db.add(anterior)
    sesion_db.commit()
    a = iniciar(cliente, torneo, cruce, cruce.jugador_a.usuario)
    assert a["duelo_id"] != anterior.id
    b = iniciar(cliente, torneo, cruce, cruce.jugador_b.usuario)
    assert a["duelo_id"] == b["duelo_id"]
    assert responder(cliente, cruce.jugador_b.usuario, a["duelo"]["preguntas"][0]["id"]).status_code == 401
    assert responder(cliente, cruce.jugador_a.usuario, a["duelo"]["preguntas"][0]["id"]).status_code == 200
    assert responder(cliente, cruce.jugador_a.usuario, a["duelo"]["preguntas"][0]["id"]).status_code == 400
    assert responder(cliente, cruce.jugador_a.usuario, a["duelo"]["preguntas"][1]["id"], tiempo=-1).status_code == 422
    retomado = iniciar(cliente, torneo, cruce, cruce.jugador_a.usuario)
    assert retomado["duelo"]["preguntas"][0]["esta_respondida"] is True
    assert sum(p["esta_respondida"] for p in retomado["duelo"]["preguntas"]) == 1
    detalle = cliente.get(f"/api/torneos/{torneo.id}", headers=encabezado(jugadores[0])).json()
    assert next(c for c in detalle["cuadro"] if c["id"] == cruce.id)["duelo_id"] == a["duelo_id"]
    url = f"/api/torneos/{torneo.id}/cruces/{cruce.id}/resolver"
    for datos in [{"ganador_participante_id": cruce.jugador_a_id}, {"duelo_id": a["duelo_id"], "ganador_participante_id": cruce.jugador_a_id}]:
        assert cliente.post(url, headers=encabezado(cruce.jugador_a.usuario), json=datos).status_code == 422
    assert cliente.post(url, headers=encabezado(cruce.jugador_a.usuario), json={"duelo_id": anterior.id}).status_code == 400
    assert cliente.post(url, headers=encabezado(cruce.jugador_a.usuario), json={"duelo_id": a["duelo_id"]}).status_code == 400
    assert cruce.estado == EstadoCruce.PENDIENTE


def test_cada_torneo_tiene_su_duelo_aunque_coincidan_jugadores(cliente, sesion_db, jugadores):
    # Fijar el orden permite repetir el mismo emparejamiento en dos torneos.
    torneos = [crear_torneo(sesion_db, jugadores), crear_torneo(sesion_db, jugadores)]
    cruces = [t.cruces[0] for t in torneos]
    cruces[1].jugador_a_id = next(p.id for p in torneos[1].participantes if p.usuario_id == cruces[0].jugador_a.usuario_id)
    cruces[1].jugador_b_id = next(p.id for p in torneos[1].participantes if p.usuario_id == cruces[0].jugador_b.usuario_id)
    sesion_db.commit()
    respuestas = [iniciar(cliente, t, c, c.jugador_a.usuario) for t, c in zip(torneos, cruces)]
    assert respuestas[0]["duelo_id"] != respuestas[1]["duelo_id"]


def test_sin_banco_suficiente_no_deja_duelo_parcial(cliente, sesion_db, jugadores):
    torneo = crear_torneo(sesion_db, jugadores)
    sesion_db.query(Pregunta).first().estado = "BORRADOR"
    sesion_db.commit()
    cruce = torneo.cruces[0]
    r = cliente.post(f"/api/torneos/{torneo.id}/cruces/{cruce.id}/iniciar-duelo", headers=encabezado(cruce.jugador_a.usuario))
    assert r.status_code == 422
    assert sesion_db.query(PartidaDuelo).count() == 0
    sesion_db.refresh(cruce)
    assert cruce.duelo_id is None
    # Una categoría vacía adicional no impide jugar cuando hay otra válida.
    sesion_db.query(Pregunta).first().estado = "ACTIVA"
    sesion_db.add(Categoria(nombre="Vacía"))
    sesion_db.commit()
    iniciar(cliente, torneo, cruce, cruce.jugador_a.usuario)


def test_fallo_al_premiar_revierte_resultado_y_permite_reintentar(cliente, sesion_db, jugadores, monkeypatch):
    torneo = crear_torneo(sesion_db, jugadores)
    for cruce in list(torneo.cruces):
        disputar(cliente, torneo, cruce)
    final = sesion_db.query(Cruce).filter_by(torneo_id=torneo.id, ronda=2).one()
    a = iniciar(cliente, torneo, final, final.jugador_a.usuario)
    b = iniciar(cliente, torneo, final, final.jugador_b.usuario)
    for p in a["duelo"]["preguntas"]:
        assert responder(cliente, final.jugador_a.usuario, p["id"]).status_code == 200
    for p in b["duelo"]["preguntas"][:-1]:
        assert responder(cliente, final.jugador_b.usuario, p["id"], None).status_code == 200
    puntajes = {u.id: u.puntaje_total for u in jugadores}
    acumular = ranking_service.acumular_puntaje

    def fallar_premio(db, usuario_id, puntos, confirmar=True):
        if puntos == 1500:
            raise RuntimeError("Fallo de prueba al premiar")
        return acumular(db, usuario_id, puntos, confirmar=confirmar)

    with monkeypatch.context() as contexto:
        contexto.setattr(ranking_service, "acumular_puntaje", fallar_premio)
        with pytest.raises(RuntimeError, match="Fallo de prueba"):
            responder(cliente, final.jugador_b.usuario, b["duelo"]["preguntas"][-1]["id"], None)
    sesion_db.refresh(final)
    assert final.estado == EstadoCruce.PENDIENTE
    assert final.duelo.estado == EstadoPartida.EN_CURSO
    for u in jugadores:
        sesion_db.refresh(u)
        assert u.puntaje_total == puntajes[u.id]
    # El fallo también revierte la última respuesta, que se puede enviar nuevamente.
    r = responder(cliente, final.jugador_b.usuario, b["duelo"]["preguntas"][-1]["id"], None)
    assert r.status_code == 200
    sesion_db.refresh(torneo)
    assert torneo.estado == EstadoTorneo.FINALIZADO
    for _ in range(2):
        duelo_service.finalizar_duelo_si_corresponde(sesion_db, a["duelo_id"])
    sesion_db.refresh(final.jugador_a.usuario)
    assert final.jugador_a.usuario.puntaje_total == puntajes[final.jugador_a.usuario_id] + 950 + 1500


def test_empate_de_torneo_coincide_con_resultado_del_duelo(cliente, sesion_db, jugadores):
    torneo = crear_torneo(sesion_db, jugadores)
    cruce = torneo.cruces[0]
    a = iniciar(cliente, torneo, cruce, cruce.jugador_a.usuario)
    b = iniciar(cliente, torneo, cruce, cruce.jugador_b.usuario)
    for datos, usuario, tiempo in [(a, cruce.jugador_a.usuario, 10), (b, cruce.jugador_b.usuario, 5)]:
        for p in datos["duelo"]["preguntas"]:
            assert responder(cliente, usuario, p["id"], None, tiempo).status_code == 200
    resultado = cliente.get(f"/api/duelos/{a['duelo_id']}", headers=encabezado(cruce.jugador_a.usuario)).json()
    assert resultado["numero_ganador"] == 2
    assert resultado["es_empate"] is False
    sesion_db.refresh(cruce)
    assert cruce.ganador_id == cruce.jugador_b_id


def test_fallo_al_crear_duelo_no_deja_preguntas_ni_asociacion(sesion_db, jugadores, monkeypatch):
    from app.models.partida import PreguntaPartida
    from app.schemas.duelo_schema import DueloJuegoResponse

    torneo = crear_torneo(sesion_db, jugadores)
    cruce = torneo.cruces[0]

    def fallar(*args, **kwargs):
        raise RuntimeError("Fallo de prueba al serializar")

    with monkeypatch.context() as contexto:
        contexto.setattr(DueloJuegoResponse, "desde_duelo", fallar)
        with pytest.raises(RuntimeError, match="Fallo de prueba"):
            torneo_service.iniciar_duelo_cruce(sesion_db, torneo.id, cruce.id, cruce.jugador_a.usuario)
    assert sesion_db.query(PartidaDuelo).count() == 0
    assert sesion_db.query(PreguntaPartida).count() == 0
    sesion_db.refresh(cruce)
    assert cruce.duelo_id is None
    respuesta = torneo_service.iniciar_duelo_cruce(sesion_db, torneo.id, cruce.id, cruce.jugador_a.usuario)
    assert len(respuesta.duelo.preguntas) == 10


def test_fallo_al_generar_primera_ronda_revierte_ultimo_ingreso(sesion_db, jugadores, monkeypatch):
    torneo = torneo_service.crear_torneo(sesion_db, TorneoCreate(nombre="Copa atómica", cantidad_participantes=4), jugadores[0])
    datos = TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso)
    for usuario in jugadores[1:3]:
        torneo_service.unirse_a_torneo(sesion_db, datos, usuario)
    generar = torneo_service.generar_cruces_para_torneo

    def fallar(*args, **kwargs):
        generar(*args, **kwargs)
        raise RuntimeError("Fallo de prueba al generar cruces")

    with monkeypatch.context() as contexto:
        contexto.setattr(torneo_service, "generar_cruces_para_torneo", fallar)
        with pytest.raises(RuntimeError, match="Fallo de prueba"):
            torneo_service.unirse_a_torneo(sesion_db, datos, jugadores[3])
    sesion_db.refresh(torneo)
    assert torneo.estado == EstadoTorneo.ESPERANDO_JUGADORES
    assert len(torneo.participantes) == 3
    assert len(torneo.cruces) == 0
    torneo_service.unirse_a_torneo(sesion_db, datos, jugadores[3])
    assert torneo.estado == EstadoTorneo.EN_CURSO
    assert len(torneo.participantes) == 4
    assert len(torneo.cruces) == 2
