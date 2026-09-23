"""Repositorio de acceso a datos para la entidad Torneo y sus participantes."""

from sqlalchemy import func
from sqlalchemy.orm import Session

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
    """Obtiene un torneo por su ID. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.id == id).first()


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


def crear(db: Session, torneo: Torneo) -> Torneo:
    """Persiste una nueva entidad Torneo en la base de datos."""
    db.add(torneo)
    db.commit()
    db.refresh(torneo)
    return torneo


def agregar_participante(db: Session, participante: ParticipanteTorneo) -> ParticipanteTorneo:
    """Persiste la inscripción de un participante en un torneo."""
    db.add(participante)
    db.commit()
    db.refresh(participante)
    return participante


def actualizar_estado(db: Session, torneo: Torneo, nuevo_estado: EstadoTorneo) -> Torneo:
    """Actualiza el estado de un torneo y confirma la transacción."""
    torneo.estado = nuevo_estado
    db.commit()
    db.refresh(torneo)
    return torneo


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
