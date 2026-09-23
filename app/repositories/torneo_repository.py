"""Repositorio de acceso a datos para la entidad Torneo y sus participantes."""

from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo


def obtener_por_id(db: Session, id: int) -> Torneo | None:
    """Obtiene un torneo por su ID. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.id == id).first()


def obtener_por_codigo_acceso(db: Session, codigo: str) -> Torneo | None:
    """Obtiene un torneo por su código de acceso único. Retorna None si no existe."""
    return db.query(Torneo).filter(Torneo.codigo_acceso == codigo).first()


# Alias por compatibilidad
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
