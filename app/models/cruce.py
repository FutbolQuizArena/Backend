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

    def determinar_ganador(self, ganador: "ParticipanteTorneo") -> None:
        """Determina y asigna el participante ganador del cruce (Tarea 3.2.2).

        Valida que el participante ganador pertenezca al cruce (jugador_a o jugador_b).
        Actualiza ganador_id y marca el cruce como JUGADO.
        """
        if ganador is None or ganador.id not in (self.jugador_a_id, self.jugador_b_id):
            id_ganador = getattr(ganador, "id", None)
            raise ValueError(
                f"El participante ID {id_ganador} no pertenece al cruce ID {self.id} "
                f"(jugadores: {self.jugador_a_id}, {self.jugador_b_id})"
            )

        self.ganador_id = ganador.id
        self.estado = EstadoCruce.JUGADO

