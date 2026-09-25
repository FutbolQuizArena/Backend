"""
Modelo de duelo (Tarea 2.1.7).

Hereda de Partida (definida en partida.py), compartiendo la misma tabla de
preguntas (PreguntaPartida) mediante numero_jugador (1 o 2).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.enumeraciones import ModalidadDuelo, TipoPartida
from app.models.partida import Partida


class PartidaDuelo(Partida):
    """Partida jugada entre dos jugadores, en línea (asincrónico) o local (RF-05/RF-06)."""

    __tablename__ = "partidas_duelo"

    id = Column(Integer, ForeignKey("partidas.id"), primary_key=True)
    modalidad = Column(String(20), nullable=False, default=ModalidadDuelo.ONLINE.value)

    jugador1_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    jugador2_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    nombre_invitado = Column(String(100), nullable=True)  # solo para duelo LOCAL, jugador 2 sin cuenta

    puntaje_jugador1 = Column(Integer, nullable=False, default=0, server_default="0")
    puntaje_jugador2 = Column(Integer, nullable=False, default=0, server_default="0")
    numero_ganador = Column(Integer, nullable=True)  # 1, 2, o None si es empate/no terminó

    fecha_emparejamiento = Column(DateTime(timezone=True), nullable=True)

    jugador1 = relationship("Usuario", foreign_keys=[jugador1_id])
    jugador2 = relationship("Usuario", foreign_keys=[jugador2_id])

    __mapper_args__ = {"polymorphic_identity": TipoPartida.DUELO}

    @property
    def es_duelo_online(self) -> bool:
        return self.modalidad == ModalidadDuelo.ONLINE.value

    @property
    def esta_esperando_rival(self) -> bool:
        """Un duelo ONLINE espera rival cuando todavía no tiene jugador2_id asignado."""
        return self.es_duelo_online and self.jugador2_id is None

    @property
    def es_empate(self) -> bool:
        return self.puntaje_jugador1 == self.puntaje_jugador2

    def unirse_como_rival(self, jugador2_id: int) -> None:
        """Asigna al segundo jugador de un duelo online y marca el momento del emparejamiento."""
        self.jugador2_id = jugador2_id
        self.fecha_emparejamiento = datetime.now(timezone.utc)

    def determinar_ganador(self) -> None:
        """Calcula el número de jugador ganador según los puntajes acumulados (None si empatan)."""
        if self.puntaje_jugador1 > self.puntaje_jugador2:
            self.numero_ganador = 1
        elif self.puntaje_jugador2 > self.puntaje_jugador1:
            self.numero_ganador = 2
        else:
            self.numero_ganador = None