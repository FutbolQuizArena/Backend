"""Modelo de base de datos para la entidad ParticipanteTorneo."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.base_datos import Base

if TYPE_CHECKING:
    from app.models.torneo import Torneo
    from app.models.usuario import Usuario


class ParticipanteTorneo(Base):
    """Modelo ORM que representa la inscripción de un usuario en un torneo."""

    __tablename__ = "participantes_torneo"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    torneo_id = Column(
        Integer,
        ForeignKey("torneos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_ingreso = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("torneo_id", "usuario_id", name="uq_participante_torneo_usuario"),
    )

    # Relaciones
    usuario = relationship("Usuario")
    torneo = relationship("Torneo", back_populates="participantes")

    def __repr__(self) -> str:
        return f"<ParticipanteTorneo(id={self.id}, torneo_id={self.torneo_id}, usuario_id={self.usuario_id})>"

