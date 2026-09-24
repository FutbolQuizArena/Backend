"""Pruebas unitarias para los modelos y esquemas de Torneo, ParticipanteTorneo y Cruce."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoTorneo, RolUsuario
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.schemas.torneo_schema import (
    CruceResponse,
    ParticipanteTorneoResponse,
    TorneoResponse,
)


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Fixture que provee un usuario persistido para ser creador de torneos."""
    creador = Usuario(
        nombre="Organizador Torneo",
        email="organizador@futbolquiz.com",
        password_hash="hash_seguro_organizador",
        rol=RolUsuario.ADMINISTRADOR,
    )
    sesion_db.add(creador)
    sesion_db.commit()
    sesion_db.refresh(creador)
    return creador


@pytest.fixture
def jugadores(sesion_db: Session) -> list[Usuario]:
    """Fixture que provee una lista de usuarios jugadores persistidos."""
    lista = []
    for i in range(1, 5):
        jugador = Usuario(
            nombre=f"Jugador {i}",
            email=f"jugador{i}@futbolquiz.com",
            password_hash="hash_jugador",
            rol=RolUsuario.JUGADOR,
        )
        sesion_db.add(jugador)
        lista.append(jugador)
    sesion_db.commit()
    for j in lista:
        sesion_db.refresh(j)
    return lista


def test_persistencia_torneo_valores_por_defecto(sesion_db: Session, usuario_creador: Usuario) -> None:
    """Verifica la persistencia de Torneo con todos sus campos y valores por defecto correctos."""
    codigo = Torneo.generar_codigo_acceso()
    torneo = Torneo(
        nombre="Copa Libertadores Trivia",
        cantidad_participantes=8,
        codigo_acceso=codigo,
        contrasena_acceso="clave123",
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    assert torneo.id is not None
    assert torneo.nombre == "Copa Libertadores Trivia"
    assert torneo.cantidad_participantes == 8
    assert torneo.codigo_acceso == codigo
    assert torneo.contrasena_acceso == "clave123"
    assert torneo.estado == EstadoTorneo.ESPERANDO_JUGADORES
    assert torneo.creador_id == usuario_creador.id
    assert torneo.fecha_creacion is not None


def test_relacion_torneo_creador(sesion_db: Session, usuario_creador: Usuario) -> None:
    """Verifica la relación de navegación entre Torneo y su creador (Usuario)."""
    torneo = Torneo(
        nombre="Mundial Trivia 2026",
        cantidad_participantes=4,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    assert torneo.creador is not None
    assert torneo.creador.id == usuario_creador.id
    assert torneo.creador.email == "organizador@futbolquiz.com"


def test_generar_codigo_acceso() -> None:
    """Verifica que generar_codigo_acceso devuelva un string alfanumérico no vacío de longitud razonable (6 caracteres)."""
    codigo1 = Torneo.generar_codigo_acceso()
    codigo2 = Torneo.generar_codigo_acceso()

    assert isinstance(codigo1, str)
    assert len(codigo1) == 6
    assert codigo1.isalnum()
    assert codigo1.isupper()

    # Códigos consecutivos deben ser distintos
    assert codigo1 != codigo2


def test_esta_completo(sesion_db: Session, usuario_creador: Usuario, jugadores: list[Usuario]) -> None:
    """Verifica que esta_completo() sea False con 0 participantes y True cuando se alcanza el cupo."""
    torneo = Torneo(
        nombre="Torneo Relampago",
        cantidad_participantes=2,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    # Con 0 participantes
    assert torneo.esta_completo() is False

    # Agregar primer participante
    p1 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=jugadores[0].id)
    sesion_db.add(p1)
    sesion_db.commit()
    sesion_db.refresh(torneo)
    assert torneo.esta_completo() is False

    # Agregar segundo participante -> alcanza el cupo (2/2)
    p2 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=jugadores[1].id)
    sesion_db.add(p2)
    sesion_db.commit()
    sesion_db.refresh(torneo)
    assert torneo.esta_completo() is True


def test_persistencia_participante_torneo(
    sesion_db: Session, usuario_creador: Usuario, jugadores: list[Usuario]
) -> None:
    """Verifica la persistencia de ParticipanteTorneo con FKs correctas y fecha_ingreso por defecto."""
    torneo = Torneo(
        nombre="Copa America",
        cantidad_participantes=4,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    participante = ParticipanteTorneo(
        usuario_id=jugadores[0].id,
        torneo_id=torneo.id,
    )
    sesion_db.add(participante)
    sesion_db.commit()
    sesion_db.refresh(participante)

    assert participante.id is not None
    assert participante.usuario_id == jugadores[0].id
    assert participante.torneo_id == torneo.id
    assert participante.fecha_ingreso is not None
    assert participante.usuario.nombre == jugadores[0].nombre
    assert participante.torneo.nombre == "Copa America"


def test_persistencia_cruce(
    sesion_db: Session, usuario_creador: Usuario, jugadores: list[Usuario]
) -> None:
    """Verifica la persistencia de Cruce con jugador_a, jugador_b, ganador nullable y estado PENDIENTE."""
    torneo = Torneo(
        nombre="Supercopa Trivia",
        cantidad_participantes=4,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    p1 = ParticipanteTorneo(usuario_id=jugadores[0].id, torneo_id=torneo.id)
    p2 = ParticipanteTorneo(usuario_id=jugadores[1].id, torneo_id=torneo.id)
    sesion_db.add_all([p1, p2])
    sesion_db.commit()
    sesion_db.refresh(p1)
    sesion_db.refresh(p2)

    cruce = Cruce(
        torneo_id=torneo.id,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p2.id,
    )
    sesion_db.add(cruce)
    sesion_db.commit()
    sesion_db.refresh(cruce)

    assert cruce.id is not None
    assert cruce.torneo_id == torneo.id
    assert cruce.ronda == 1
    assert cruce.jugador_a_id == p1.id
    assert cruce.jugador_b_id == p2.id
    assert cruce.ganador_id is None
    assert cruce.estado == EstadoCruce.PENDIENTE
    assert cruce.jugador_a.id == p1.id
    assert cruce.jugador_b.id == p2.id
    assert cruce.ganador is None


def test_serializacion_torneo_response_segura(sesion_db: Session, usuario_creador: Usuario) -> None:
    """Verifica que TorneoResponse serialice desde el modelo y NUNCA exponga contrasena_acceso."""
    torneo = Torneo(
        nombre="Torneo Privado",
        cantidad_participantes=4,
        codigo_acceso="SECRET7",
        contrasena_acceso="super_password_privado",
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    respuesta = TorneoResponse.model_validate(torneo)

    assert respuesta.id == torneo.id
    assert respuesta.nombre == "Torneo Privado"
    assert respuesta.cantidad_participantes == 4
    assert respuesta.codigo_acceso == "SECRET7"
    assert respuesta.estado == EstadoTorneo.ESPERANDO_JUGADORES
    assert respuesta.creador_id == usuario_creador.id
    assert respuesta.fecha_creacion is not None

    dump = respuesta.model_dump()
    assert "contrasena_acceso" not in dump
    assert "contrasena" not in dump


def test_serializacion_esquemas_participante_y_cruce(
    sesion_db: Session, usuario_creador: Usuario, jugadores: list[Usuario]
) -> None:
    """Verifica que ParticipanteTorneoResponse y CruceResponse serialicen correctamente desde modelos ORM."""
    torneo = Torneo(
        nombre="Torneo Test Schemas",
        cantidad_participantes=2,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    p1 = ParticipanteTorneo(usuario_id=jugadores[0].id, torneo_id=torneo.id)
    p2 = ParticipanteTorneo(usuario_id=jugadores[1].id, torneo_id=torneo.id)
    sesion_db.add_all([p1, p2])
    sesion_db.commit()
    sesion_db.refresh(p1)
    sesion_db.refresh(p2)

    resp_p = ParticipanteTorneoResponse.model_validate(p1)
    assert resp_p.id == p1.id
    assert resp_p.usuario_id == jugadores[0].id
    assert resp_p.torneo_id == torneo.id
    assert resp_p.fecha_ingreso is not None

    cruce = Cruce(
        torneo_id=torneo.id,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p2.id,
        ganador_id=p1.id,
        estado=EstadoCruce.JUGADO,
    )
    sesion_db.add(cruce)
    sesion_db.commit()
    sesion_db.refresh(cruce)

    resp_c = CruceResponse.model_validate(cruce)
    assert resp_c.id == cruce.id
    assert resp_c.torneo_id == torneo.id
    assert resp_c.ronda == 1
    assert resp_c.jugador_a_id == p1.id
    assert resp_c.jugador_b_id == p2.id
    assert resp_c.ganador_id == p1.id
    assert resp_c.estado == EstadoCruce.JUGADO


def test_cascada_eliminacion_torneo(
    sesion_db: Session, usuario_creador: Usuario, jugadores: list[Usuario]
) -> None:
    """Verifica que al eliminar un Torneo, se eliminan en cascada sus Participantes y Cruces asociados."""
    torneo = Torneo(
        nombre="Torneo para Eliminar",
        cantidad_participantes=2,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()
    sesion_db.refresh(torneo)

    p1 = ParticipanteTorneo(usuario_id=jugadores[0].id, torneo_id=torneo.id)
    p2 = ParticipanteTorneo(usuario_id=jugadores[1].id, torneo_id=torneo.id)
    sesion_db.add_all([p1, p2])
    sesion_db.commit()
    sesion_db.refresh(p1)
    sesion_db.refresh(p2)

    cruce = Cruce(
        torneo_id=torneo.id,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p2.id,
    )
    sesion_db.add(cruce)
    sesion_db.commit()
    sesion_db.refresh(cruce)

    torneo_id = torneo.id
    p1_id = p1.id
    cruce_id = cruce.id

    # Eliminar el torneo
    sesion_db.delete(torneo)
    sesion_db.commit()

    # Verificar que el participante y el cruce fueron eliminados en cascada
    assert sesion_db.query(Torneo).filter_by(id=torneo_id).first() is None
    assert sesion_db.query(ParticipanteTorneo).filter_by(id=p1_id).first() is None
    assert sesion_db.query(Cruce).filter_by(id=cruce_id).first() is None


def test_metodos_diferidos_no_lanzan_error(sesion_db: Session, usuario_creador: Usuario) -> None:
    """Verifica que los métodos que se implementan en 3.1.3 y 3.2 estén declarados y ejecutables sin error."""
    torneo = Torneo(
        nombre="Torneo Metodos",
        cantidad_participantes=4,
        codigo_acceso=Torneo.generar_codigo_acceso(),
        creador_id=usuario_creador.id,
    )
    cruce = Cruce(
        torneo_id=1,
        ronda=1,
        jugador_a_id=1,
        jugador_b_id=2,
    )

    # unirse() implementado en 3.1.3: retorna bool
    torneo.estado = EstadoTorneo.ESPERANDO_JUGADORES
    assert isinstance(torneo.unirse(usuario=usuario_creador), bool)
    assert torneo.unirse(usuario=usuario_creador) is True
    # generar_cruces() implementado en 3.2.1: retorna lista de tuplas de participantes
    assert isinstance(torneo.generar_cruces(), list)
    # determinar_ganador() diferido a 3.2
    assert cruce.determinar_ganador() is None

