"""Modelo de base de datos para la entidad Torneo."""

from datetime import datetime, timezone
import secrets
import string
from typing import TYPE_CHECKING
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.base_datos import Base
from app.models.enumeraciones import EstadoTorneo

if TYPE_CHECKING:
    from app.models.cruce import Cruce
    from app.models.participante_torneo import ParticipanteTorneo
    from app.models.usuario import Usuario


class Torneo(Base):
    """Modelo ORM que representa un torneo en el sistema."""

    __tablename__ = "torneos"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nombre = Column(String(100), nullable=False)
    cantidad_participantes = Column(Integer, nullable=False)
    codigo_acceso = Column(String(10), unique=True, index=True, nullable=False)
    contrasena_acceso = Column(String(255), nullable=True)
    estado = Column(
        SQLEnum(EstadoTorneo, name="estado_torneo_enum"),
        nullable=False,
        default=EstadoTorneo.ESPERANDO_JUGADORES,
        server_default=EstadoTorneo.ESPERANDO_JUGADORES.value,
    )
    creador_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_creacion = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relaciones
    creador = relationship("Usuario", foreign_keys=[creador_id])
    participantes = relationship(
        "ParticipanteTorneo",
        back_populates="torneo",
        cascade="all, delete-orphan",
    )
    cruces = relationship(
        "Cruce",
        back_populates="torneo",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Torneo(id={self.id}, nombre='{self.nombre}', codigo_acceso='{self.codigo_acceso}', estado='{self.estado}')>"

    @staticmethod
    def generar_codigo_acceso(longitud: int = 6) -> str:
        """Genera un código de acceso alfanumérico corto y aleatorio en mayúsculas."""
        caracteres = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(caracteres) for _ in range(longitud))

    def esta_completo(self) -> bool:
        """Verifica si el torneo alcanzó el cupo máximo de participantes."""
        return len(self.participantes or []) >= (self.cantidad_participantes or 0)

    def unirse(self, usuario: "Usuario", contrasena_ingresada: str | None = None) -> bool:
        """Permite a un usuario incorporarse al torneo validando cupo y credenciales de acceso.

        Se implementa en la sub-tarea 3.1.3 (endpoint ingresar por código), ya que
        requiere lógica de persistencia y orquestación con la base de datos.
        """
        pass

    def generar_cruces(self) -> None:
        """Genera el fixture inicial de cruces eliminatorios del torneo.

        Se implementa en la sub-tarea 3.2 (motor de eliminación directa), ya que
        requiere lógica de persistencia y orquestación con PartidaDuelo.
        """
        pass

