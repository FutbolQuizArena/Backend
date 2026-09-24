"""Modelo de base de datos para la entidad Torneo."""

from datetime import datetime, timezone
import bcrypt
import random
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
        """Valida si un usuario puede unirse al torneo según estado, cupo y credenciales.

        Devuelve True si pasa todas las validaciones de negocio. La persistencia y
        creación del ParticipanteTorneo se realiza en la capa de servicios.
        """
        # Torneo debe estar esperando jugadores
        if self.estado != EstadoTorneo.ESPERANDO_JUGADORES:
            return False

        # Torneo no debe estar completo
        if self.esta_completo():
            return False

        # Si el torneo tiene contraseña de acceso, debe verificarse contra el hash
        if self.contrasena_acceso:
            if not contrasena_ingresada:
                return False
            try:
                if not bcrypt.checkpw(
                    contrasena_ingresada.encode("utf-8"),
                    self.contrasena_acceso.encode("utf-8"),
                ):
                    return False
            except Exception:
                return False

        return True

    def salir(self, usuario: "Usuario") -> str:
        """Determina la acción a tomar ante la salida de un participante del torneo.

        Reglas de negocio:
          - Si el estado no es ESPERANDO_JUGADORES, no se permite la salida ('no_permitido').
          - Si el usuario que sale es el creador del torneo, el torneo se cancela ('torneo_cancelado').
          - Si el usuario es un participante regular, se retira del torneo ('participante_eliminado').

        Retorna:
            - 'no_permitido': El torneo ya comenzó o finalizó.
            - 'torneo_cancelado': El usuario que sale es el creador del torneo.
            - 'participante_eliminado': El usuario es un participante regular.
        """
        if self.estado != EstadoTorneo.ESPERANDO_JUGADORES:
            return "no_permitido"

        if usuario.id == self.creador_id:
            return "torneo_cancelado"

        return "participante_eliminado"

    def generar_cruces(self) -> list[tuple["ParticipanteTorneo", "ParticipanteTorneo"]]:
        """Genera los emparejamientos aleatorios para la Ronda 1 del torneo.

        Toma los participantes inscriptos (self.participantes), los mezcla aleatoriamente
        y arma pares consecutivos (jugador_a, jugador_b).
        No interactúa con la base de datos ni instancia entidades Cruce.
        """
        participantes_mezclados = list(self.participantes or [])
        random.shuffle(participantes_mezclados)
        pares: list[tuple["ParticipanteTorneo", "ParticipanteTorneo"]] = []
        for i in range(0, len(participantes_mezclados), 2):
            if i + 1 < len(participantes_mezclados):
                pares.append((participantes_mezclados[i], participantes_mezclados[i + 1]))
        return pares

