"""Modelo de base de datos para la entidad Cruce."""

from typing import TYPE_CHECKING
from sqlalchemy import Column, Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.core.base_datos import Base
from app.models.enumeraciones import EstadoCruce

if TYPE_CHECKING:
    from app.models.participante_torneo import ParticipanteTorneo
    from app.models.torneo import Torneo


class Cruce(Base):
    """Modelo ORM que representa un cruce o enfrentamiento eliminatorio dentro de un torneo."""

    __tablename__ = "cruces_torneo"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    torneo_id = Column(
        Integer,
        ForeignKey("torneos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ronda = Column(Integer, nullable=False)
    jugador_a_id = Column(
        Integer,
        ForeignKey("participantes_torneo.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jugador_b_id = Column(
        Integer,
        ForeignKey("participantes_torneo.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ganador_id = Column(
        Integer,
        ForeignKey("participantes_torneo.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    estado = Column(
        SQLEnum(EstadoCruce, name="estado_cruce_enum"),
        nullable=False,
        default=EstadoCruce.PENDIENTE,
        server_default=EstadoCruce.PENDIENTE.value,
    )

    # Relaciones
    torneo = relationship("Torneo", back_populates="cruces")
    jugador_a = relationship("ParticipanteTorneo", foreign_keys=[jugador_a_id])
    jugador_b = relationship("ParticipanteTorneo", foreign_keys=[jugador_b_id])
    ganador = relationship("ParticipanteTorneo", foreign_keys=[ganador_id])

    def __repr__(self) -> str:
        return (
            f"<Cruce(id={self.id}, torneo_id={self.torneo_id}, ronda={self.ronda}, "
            f"jugador_a_id={self.jugador_a_id}, jugador_b_id={self.jugador_b_id}, "
            f"ganador_id={self.ganador_id}, estado='{self.estado}')>"
        )

    def determinar_ganador(self) -> None:
        """Determina el participante ganador del cruce a partir del resultado del duelo.

        Se implementa en la sub-tarea 3.2 (motor de eliminación directa), ya que
        depende del resultado de PartidaDuelo (Módulo 2).
        """
        pass

