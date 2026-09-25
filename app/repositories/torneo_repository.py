"""Repositorio de acceso a datos para la entidad Torneo y sus participantes."""

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo


def _subquery_conteo_participantes(db: Session):
    """Subquery escalar correlacionada para calcular el total de participantes por torneo sin N+1."""
    return (
        db.query(func.count(ParticipanteTorneo.id))
        .filter(ParticipanteTorneo.torneo_id == Torneo.id)
        .correlate(Torneo)
        .scalar_subquery()
    )


def obtener_por_id(db: Session, id: int) -> Torneo | None:
    """Obtiene un torneo por su ID con relaciones cargadas eficientemente. Retorna None si no existe."""
    return (
        db.query(Torneo)
        .options(
            joinedload(Torneo.creador),
            joinedload(Torneo.participantes).joinedload(ParticipanteTorneo.usuario),
        )
        .filter(Torneo.id == id)
        .first()
    )


def obtener_por_codigo_acceso(db: Session, codigo: str) -> Torneo | None:
    """Obtiene un torneo por su código de acceso único. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.codigo_acceso == codigo).first()


# Alias consolidado para evitar duplicación
obtener_por_codigo = obtener_por_codigo_acceso


def es_participante(db: Session, torneo_id: int, usuario_id: int) -> bool:
    """Verifica si un usuario ya se encuentra registrado como participante en un torneo."""
    return (
        db.query(ParticipanteTorneo)
        .filter(
            ParticipanteTorneo.torneo_id == torneo_id,
            ParticipanteTorneo.usuario_id == usuario_id,
        )
        .first()
        is not None
    )


def obtener_participante(db: Session, torneo_id: int, usuario_id: int) -> ParticipanteTorneo | None:
    """Obtiene el registro de ParticipanteTorneo para un torneo y usuario específicos."""
    return (
        db.query(ParticipanteTorneo)
        .filter(
            ParticipanteTorneo.torneo_id == torneo_id,
            ParticipanteTorneo.usuario_id == usuario_id,
        )
        .first()
    )


def crear(db: Session, torneo: Torneo) -> Torneo:
    """Persiste una nueva entidad Torneo en la base de datos."""
    db.add(torneo)
    db.commit()
    db.refresh(torneo)
    return torneo


def eliminar_torneo(db: Session, torneo: Torneo) -> None:
    """Elimina un torneo y sus entidades hijas asociadas en cascada (participantes y cruces)."""
    db.delete(torneo)
    db.commit()


def agregar_participante(db: Session, participante: ParticipanteTorneo) -> ParticipanteTorneo:
    """Persiste la inscripción de un participante en un torneo."""
    db.add(participante)
    db.commit()
    db.refresh(participante)
    return participante


def eliminar_participante(db: Session, participante: ParticipanteTorneo) -> None:
    """Elimina la inscripción de un participante y confirma la transacción."""
    db.delete(participante)
    db.commit()


def actualizar_estado(db: Session, torneo: Torneo, nuevo_estado: EstadoTorneo) -> Torneo:
    """Actualiza el estado de un torneo y confirma la transacción."""
    torneo.estado = nuevo_estado
    db.commit()
    db.refresh(torneo)
    return torneo


def crear_cruces(
    db: Session | list[Cruce],
    cruces: list[Cruce] | None = None,
) -> list[Cruce]:
    """Persiste una lista de entidades Cruce en la base de datos y confirma la transacción.

    Soporta invocación directa:
      - crear_cruces(db, cruces)
      - crear_cruces(cruces) (infiriendo la sesión del modelo asociado)
    """
    if isinstance(db, list):
        lista_cruces = db
        sesion = None
        for c in lista_cruces:
            from sqlalchemy.orm import object_session
            s = object_session(c) or (object_session(c.torneo) if hasattr(c, "torneo") and c.torneo else None)
            if s is not None:
                sesion = s
                break
        if sesion is None:
            raise ValueError("No se pudo inferir la sesión de base de datos para persistir los cruces")
    else:
        sesion = db
        lista_cruces = cruces or []

    sesion.add_all(lista_cruces)
    sesion.commit()
    for cruce in lista_cruces:
        sesion.refresh(cruce)
    return lista_cruces


def obtener_cruces_por_torneo(
    db: Session | int,
    torneo_id: int | None = None,
) -> list[Cruce]:
    """Obtiene todos los cruces de un torneo ordenados por ronda.

    Carga eficientemente las relaciones de participantes y usuarios asociados.
    """
    if isinstance(db, int):
        id_torneo = db
        sesion = None
    else:
        sesion = db
        id_torneo = torneo_id

    if sesion is None:
        raise ValueError("Se requiere una sesión de base de datos para consultar los cruces")

    return (
        sesion.query(Cruce)
        .options(
            joinedload(Cruce.jugador_a).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.jugador_b).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.ganador).joinedload(ParticipanteTorneo.usuario),
        )
        .filter(Cruce.torneo_id == id_torneo)
        .order_by(Cruce.ronda.asc(), Cruce.id.asc())
        .all()
    )


def listar_por_participante(db: Session, usuario_id: int) -> list[tuple[Torneo, int]]:
    """Obtiene los torneos donde el usuario es participante, junto con el conteo de participantes actual."""
    conteo = _subquery_conteo_participantes(db)
    return (
        db.query(Torneo, conteo)
        .join(ParticipanteTorneo, ParticipanteTorneo.torneo_id == Torneo.id)
        .filter(ParticipanteTorneo.usuario_id == usuario_id)
        .order_by(Torneo.fecha_creacion.desc())
        .all()
    )


def listar_disponibles(db: Session, usuario_id: int) -> list[tuple[Torneo, int]]:
    """Obtiene torneos en ESPERANDO_JUGADORES donde el usuario aún NO participa y hay cupo disponible."""
    conteo = _subquery_conteo_participantes(db)
    subquery_torneos_usuario = (
        db.query(ParticipanteTorneo.torneo_id)
        .filter(ParticipanteTorneo.usuario_id == usuario_id)
        .scalar_subquery()
    )
    resultados = (
        db.query(Torneo, conteo)
        .filter(
            Torneo.estado == EstadoTorneo.ESPERANDO_JUGADORES,
            ~Torneo.id.in_(subquery_torneos_usuario),
        )
        .order_by(Torneo.fecha_creacion.desc())
        .all()
    )
    return [(torneo, cant or 0) for torneo, cant in resultados if (cant or 0) < torneo.cantidad_participantes]


def listar_finalizados_por_participante(db: Session, usuario_id: int) -> list[tuple[Torneo, int]]:
    """Obtiene los torneos con estado FINALIZADO en los que el usuario participó."""
    conteo = _subquery_conteo_participantes(db)
    return (
        db.query(Torneo, conteo)
        .join(ParticipanteTorneo, ParticipanteTorneo.torneo_id == Torneo.id)
        .filter(
            Torneo.estado == EstadoTorneo.FINALIZADO,
            ParticipanteTorneo.usuario_id == usuario_id,
        )
        .order_by(Torneo.fecha_creacion.desc())
        .all()
    )


def obtener_cruce_por_id(db: Session, cruce_id: int) -> Cruce | None:
    """Obtiene un cruce por su ID con relaciones cargadas eficientemente (Tarea 3.2.2)."""
    return (
        db.query(Cruce)
        .options(
            joinedload(Cruce.jugador_a).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.jugador_b).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.ganador).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.torneo).joinedload(Torneo.participantes),
        )
        .filter(Cruce.id == cruce_id)
        .first()
    )


def obtener_cruces_por_ronda(db: Session, torneo_id: int, ronda: int) -> list[Cruce]:
    """Retorna los cruces de una ronda específica ordenados por ID ascendente (Tarea 3.2.2)."""
    return (
        db.query(Cruce)
        .options(
            joinedload(Cruce.jugador_a).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.jugador_b).joinedload(ParticipanteTorneo.usuario),
            joinedload(Cruce.ganador).joinedload(ParticipanteTorneo.usuario),
        )
        .filter(Cruce.torneo_id == torneo_id, Cruce.ronda == ronda)
        .order_by(Cruce.id.asc())
        .all()
    )


def actualizar_cruce(db: Session, cruce: Cruce) -> Cruce:
    """Actualiza y confirma los cambios de un cruce en la base de datos (Tarea 3.2.2)."""
    db.commit()
    db.refresh(cruce)
    return cruce


def obtener_ronda_actual(db: Session, torneo_id: int) -> int:
    """Calcula la ronda máxima registrada para un torneo (Tarea 3.2.2)."""
    ronda_max = (
        db.query(func.max(Cruce.ronda))
        .filter(Cruce.torneo_id == torneo_id)
        .scalar()
    )
    return ronda_max or 1
