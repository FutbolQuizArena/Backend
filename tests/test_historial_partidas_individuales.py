"""Pruebas del historial de partidas individuales (Tarea 4.1.3, RF-15 y RF-17)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPartida, TipoPartida
from app.models.partida import PartidaIndividual
from app.models.usuario import Usuario
from app.services import autenticacion_service

URL_HISTORIAL = "/api/historial/partidas-individuales"


def _crear_usuario(db: Session, nombre: str) -> Usuario:
    usuario = Usuario(
        nombre=nombre, email=f"{nombre.lower()}@futbolquiz.com", password_hash="hash_de_prueba"
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _crear_categoria(db: Session, nombre: str = "Mundiales") -> Categoria:
    categoria = Categoria(nombre=nombre)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


def _crear_partida(
    db: Session,
    jugador: Usuario,
    categoria: Categoria,
    puntaje_final: int,
    estado: EstadoPartida = EstadoPartida.FINALIZADA,
    fecha_fin: datetime | None = None,
) -> PartidaIndividual:
    partida = PartidaIndividual(
        tipo=TipoPartida.INDIVIDUAL,
        categoria_id=categoria.id,
        estado=estado,
        jugador_id=jugador.id,
        puntaje_final=puntaje_final,
        fecha_fin=fecha_fin,
    )
    db.add(partida)
    db.commit()
    db.refresh(partida)
    return partida


def _encabezado(usuario: Usuario) -> dict[str, str]:
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


def test_historial_requiere_autenticacion(cliente: TestClient) -> None:
    assert cliente.get(URL_HISTORIAL).status_code == 401


def test_historial_sin_partidas_devuelve_lista_vacia(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Nuevo")

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"partidas": [], "total": 0}


def test_historial_devuelve_puntaje_categoria_y_fecha(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Jugador")
    categoria = _crear_categoria(sesion_db, "Copa Libertadores")
    fecha = datetime(2026, 9, 1, 15, 30, tzinfo=timezone.utc)
    partida = _crear_partida(sesion_db, jugador, categoria, puntaje_final=85, fecha_fin=fecha)

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    item = cuerpo["partidas"][0]
    assert item["partida_id"] == partida.id
    assert item["categoria_nombre"] == "Copa Libertadores"
    assert item["puntaje_final"] == 85
    assert item["fecha_fin"].startswith("2026-09-01T15:30")


def test_historial_ordena_de_la_mas_reciente_a_la_mas_antigua(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Orden")
    categoria = _crear_categoria(sesion_db)
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    _crear_partida(sesion_db, jugador, categoria, 10, fecha_fin=base)
    _crear_partida(sesion_db, jugador, categoria, 30, fecha_fin=base + timedelta(days=2))
    _crear_partida(sesion_db, jugador, categoria, 20, fecha_fin=base + timedelta(days=1))

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    assert [p["puntaje_final"] for p in respuesta.json()["partidas"]] == [30, 20, 10]


def test_historial_excluye_partidas_en_curso(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "EnCurso")
    categoria = _crear_categoria(sesion_db)
    _crear_partida(sesion_db, jugador, categoria, 0, estado=EstadoPartida.EN_CURSO)
    terminada = _crear_partida(
        sesion_db, jugador, categoria, 40, fecha_fin=datetime(2026, 9, 1, tzinfo=timezone.utc)
    )

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 1
    assert cuerpo["partidas"][0]["partida_id"] == terminada.id


def test_historial_solo_muestra_las_partidas_del_usuario_autenticado(
    cliente: TestClient, sesion_db: Session
) -> None:
    yo = _crear_usuario(sesion_db, "Yo")
    otro = _crear_usuario(sesion_db, "Otro")
    categoria = _crear_categoria(sesion_db)
    fecha = datetime(2026, 9, 1, tzinfo=timezone.utc)
    _crear_partida(sesion_db, yo, categoria, 11, fecha_fin=fecha)
    _crear_partida(sesion_db, otro, categoria, 99, fecha_fin=fecha)

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(yo))

    assert [p["puntaje_final"] for p in respuesta.json()["partidas"]] == [11]