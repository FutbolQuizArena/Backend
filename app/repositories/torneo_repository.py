"""Repositorio de acceso a datos para la entidad Torneo y sus participantes."""

from sqlalchemy.orm import Session

from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo


def obtener_por_id(db: Session, id: int) -> Torneo | None:
    """Obtiene un torneo por su ID. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.id == id).first()


def obtener_por_codigo(db: Session, codigo_acceso: str) -> Torneo | None:
    """Obtiene un torneo por su código de acceso único. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.codigo_acceso == codigo_acceso).first()


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

