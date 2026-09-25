"""
Modelos de partida individual (Tarea 2.1.1).

Sigue el diagrama de clases: Partida (base) → PartidaIndividual / PartidaDuelo.
PartidaDuelo vive en partida_duelo.py (Tarea 2.1.7) y hereda de Partida acá definida,
así ambas comparten la misma tabla de preguntas (PreguntaPartida).
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.base_datos import Base
from app.models.enumeraciones import EstadoPartida, TipoPartida


class Partida(Base):
    """Modelo base común a partida individual y duelo (herencia por tabla unida)."""

    __tablename__ = "partidas"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    tipo = Column(SQLEnum(TipoPartida, name="tipo_partida_enum"), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)  # null si es duelo PENDIENTE_RIVAL
    estado = Column(
        SQLEnum(EstadoPartida, name="estado_partida_enum"),
        nullable=False,
        default=EstadoPartida.EN_CURSO,
        server_default=EstadoPartida.EN_CURSO.value,
    )
    fecha_inicio = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    fecha_fin = Column(DateTime(timezone=True), nullable=True)

    categoria = relationship("Categoria")
    preguntas = relationship(
        "PreguntaPartida",
        back_populates="partida",
        cascade="all, delete-orphan",
        order_by="(PreguntaPartida.numero_jugador, PreguntaPartida.orden)",
    )

    __mapper_args__ = {"polymorphic_on": tipo}

    def preguntas_de_jugador(self, numero_jugador: int) -> list["PreguntaPartida"]:
        return [p for p in self.preguntas if p.numero_jugador == numero_jugador]

    @property
    def categoria_nombre(self) -> Optional[str]:
        """Nombre de la categoría asociada a la partida o duelo."""
        return self.categoria.nombre if self.categoria else None


class PartidaIndividual(Partida):
    """Partida jugada por un único jugador (RF-04)."""

    __tablename__ = "partidas_individuales"

    id = Column(Integer, ForeignKey("partidas.id"), primary_key=True)
    jugador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    puntaje_final = Column(Integer, nullable=False, default=0, server_default="0")

    jugador = relationship("Usuario", foreign_keys=[jugador_id])

    __mapper_args__ = {"polymorphic_identity": TipoPartida.INDIVIDUAL}


class PreguntaPartida(Base):
    """
    Una pregunta asignada a un jugador dentro de una partida.
    Partida individual: 10 filas (numero_jugador = 1).
    Duelo: 20 filas, las MISMAS 10 preguntas para el jugador 1 y para el jugador 2.
    """

    __tablename__ = "preguntas_partida"
    __table_args__ = (
        UniqueConstraint("partida_id", "numero_jugador", "orden", name="uq_pregunta_partida_orden"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    partida_id = Column(Integer, ForeignKey("partidas.id"), nullable=False, index=True)
    pregunta_id = Column(Integer, ForeignKey("preguntas.id"), nullable=False)
    orden = Column(Integer, nullable=False)  # 1..10
    numero_jugador = Column(Integer, nullable=False, default=1, server_default="1")  # 1 o 2
    opcion_seleccionada = Column(String(1), nullable=True)
    es_correcta = Column(Boolean, nullable=False, default=False, server_default="false")
    esta_respondida = Column(Boolean, nullable=False, default=False, server_default="false")
    tiempo_respuesta_segundos = Column(Integer, nullable=True)
    puntaje_obtenido = Column(Integer, nullable=False, default=0, server_default="0")
    fecha_mostrada = Column(DateTime(timezone=True), nullable=True)

    partida = relationship("Partida", back_populates="preguntas")
    pregunta = relationship("Pregunta")

    def registrar_respuesta(
        self, opcion: Optional[str], tiempo_segundos: int, es_correcta: bool, puntaje: int
    ) -> None:
        self.opcion_seleccionada = opcion
        self.tiempo_respuesta_segundos = tiempo_segundos
        self.es_correcta = es_correcta
        self.puntaje_obtenido = puntaje
        self.esta_respondida = True