"""Pruebas del historial de torneos con ronda alcanzada (Tarea 4.1.5, RF-15 y RF-17)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.services import autenticacion_service

URL_HISTORIAL = "/api/historial/torneos"
FECHA_BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _crear_usuario(db: Session, nombre: str) -> Usuario:
    usuario = Usuario(
        nombre=nombre, email=f"{nombre.lower()}@futbolquiz.com", password_hash="hash_de_prueba"
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _crear_torneo(
    db: Session,
    creador: Usuario,
    codigo: str,
    estado: EstadoTorneo = EstadoTorneo.FINALIZADO,
    fecha_creacion: datetime = FECHA_BASE,
) -> Torneo:
    torneo = Torneo(
        nombre=f"Torneo {codigo}",
        cantidad_participantes=4,
        codigo_acceso=codigo,
        estado=estado,
        creador_id=creador.id,
        fecha_creacion=fecha_creacion,
    )
    db.add(torneo)
    db.commit()
    db.refresh(torneo)
    return torneo


def _inscribir(db: Session, torneo: Torneo, usuarios: list[Usuario]) -> list[ParticipanteTorneo]:
    participantes = [ParticipanteTorneo(torneo_id=torneo.id, usuario_id=u.id) for u in usuarios]
    db.add_all(participantes)
    db.commit()
    for participante in participantes:
        db.refresh(participante)
    return participantes


def _crear_cruce(
    db: Session,
    torneo: Torneo,
    ronda: int,
    jugador_a: ParticipanteTorneo,
    jugador_b: ParticipanteTorneo,
    ganador: ParticipanteTorneo | None,
) -> Cruce:
    cruce = Cruce(
        torneo_id=torneo.id,
        ronda=ronda,
        jugador_a_id=jugador_a.id,
        jugador_b_id=jugador_b.id,
        ganador_id=ganador.id if ganador else None,
        estado=EstadoCruce.JUGADO if ganador else EstadoCruce.PENDIENTE,
    )
    db.add(cruce)
    db.commit()
    return cruce


def _torneo_de_cuatro_finalizado(db: Session, codigo: str = "ABC123"):
    """Torneo de 4 jugadores terminado: gana el jugador 1, subcampeón el 3, 2 y 4 caen en ronda 1."""
    usuarios = [_crear_usuario(db, f"{codigo}J{n}") for n in range(1, 5)]
    torneo = _crear_torneo(db, usuarios[0], codigo)
    p1, p2, p3, p4 = _inscribir(db, torneo, usuarios)
    _crear_cruce(db, torneo, 1, p1, p2, ganador=p1)
    _crear_cruce(db, torneo, 1, p3, p4, ganador=p3)
    _crear_cruce(db, torneo, 2, p1, p3, ganador=p1)
    return torneo, usuarios


def _encabezado(usuario: Usuario) -> dict[str, str]:
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


def _historial(cliente: TestClient, usuario: Usuario) -> dict:
    return cliente.get(URL_HISTORIAL, headers=_encabezado(usuario)).json()


def test_historial_torneos_requiere_autenticacion(cliente: TestClient) -> None:
    assert cliente.get(URL_HISTORIAL).status_code == 401


def test_historial_torneos_sin_torneos_devuelve_lista_vacia(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Nuevo")

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"torneos": [], "total": 0}


def test_historial_torneos_campeon_alcanza_la_final(
    cliente: TestClient, sesion_db: Session
) -> None:
    torneo, usuarios = _torneo_de_cuatro_finalizado(sesion_db)

    item = _historial(cliente, usuarios[0])["torneos"][0]

    assert item["torneo_id"] == torneo.id
    assert item["nombre"] == torneo.nombre
    assert item["estado"] == "FINALIZADO"
    assert item["ronda_alcanzada"] == 2
    assert item["es_campeon"] is True


def test_historial_torneos_subcampeon_llega_a_la_final_sin_ser_campeon(
    cliente: TestClient, sesion_db: Session
) -> None:
    _, usuarios = _torneo_de_cuatro_finalizado(sesion_db)

    item = _historial(cliente, usuarios[2])["torneos"][0]

    assert item["ronda_alcanzada"] == 2
    assert item["es_campeon"] is False


def test_historial_torneos_eliminado_en_primera_ronda(
    cliente: TestClient, sesion_db: Session
) -> None:
    _, usuarios = _torneo_de_cuatro_finalizado(sesion_db)

    item = _historial(cliente, usuarios[1])["torneos"][0]

    assert item["ronda_alcanzada"] == 1
    assert item["es_campeon"] is False


def test_historial_torneos_sin_cruces_no_tiene_ronda_alcanzada(
    cliente: TestClient, sesion_db: Session
) -> None:
    creador = _crear_usuario(sesion_db, "Creador")
    torneo = _crear_torneo(
        sesion_db, creador, "ESPERA", estado=EstadoTorneo.ESPERANDO_JUGADORES
    )
    _inscribir(sesion_db, torneo, [creador])

    item = _historial(cliente, creador)["torneos"][0]

    assert item["estado"] == "ESPERANDO_JUGADORES"
    assert item["ronda_alcanzada"] is None
    assert item["es_campeon"] is False


def test_historial_torneos_en_curso_no_marca_campeon_aunque_gane_su_cruce(
    cliente: TestClient, sesion_db: Session
) -> None:
    usuarios = [_crear_usuario(sesion_db, f"EnCurso{n}") for n in range(1, 5)]
    torneo = _crear_torneo(sesion_db, usuarios[0], "CURSO1", estado=EstadoTorneo.EN_CURSO)
    p1, p2, p3, p4 = _inscribir(sesion_db, torneo, usuarios)
    _crear_cruce(sesion_db, torneo, 1, p1, p2, ganador=p1)
    _crear_cruce(sesion_db, torneo, 1, p3, p4, ganador=None)

    item = _historial(cliente, usuarios[0])["torneos"][0]

    assert item["estado"] == "EN_CURSO"
    assert item["ronda_alcanzada"] == 1
    assert item["es_campeon"] is False


def test_historial_torneos_solo_muestra_los_del_usuario_autenticado(
    cliente: TestClient, sesion_db: Session
) -> None:
    _, usuarios_a = _torneo_de_cuatro_finalizado(sesion_db, "AAAAAA")
    _, usuarios_b = _torneo_de_cuatro_finalizado(sesion_db, "BBBBBB")

    cuerpo = _historial(cliente, usuarios_a[0])

    assert cuerpo["total"] == 1
    assert cuerpo["torneos"][0]["nombre"] == "Torneo AAAAAA"


def test_historial_torneos_ordena_del_mas_reciente_al_mas_antiguo(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Veterano")
    for dias, codigo in ((0, "VIEJO1"), (2, "NUEVO1"), (1, "MEDIO1")):
        torneo = _crear_torneo(
            sesion_db,
            jugador,
            codigo,
            estado=EstadoTorneo.ESPERANDO_JUGADORES,
            fecha_creacion=FECHA_BASE + timedelta(days=dias),
        )
        _inscribir(sesion_db, torneo, [jugador])

    cuerpo = _historial(cliente, jugador)

    assert [t["nombre"] for t in cuerpo["torneos"]] == [
        "Torneo NUEVO1",
        "Torneo MEDIO1",
        "Torneo VIEJO1",
    ]