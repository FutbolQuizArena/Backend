"""Modelo de base de datos para la entidad Usuario."""

from datetime import datetime, timezone
import bcrypt
from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, Integer, String, func
from sqlalchemy.sql import expression

from app.core.database import Base
from app.models.enums import RolUsuario


class Usuario(Base):
    """Modelo ORM que representa a un usuario en el sistema."""

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(
        SQLEnum(RolUsuario, name="rol_usuario_enum"),
        nullable=False,
        default=RolUsuario.JUGADOR,
        server_default=RolUsuario.JUGADOR.value,
    )
    puntaje_total = Column(Integer, nullable=False, default=0, server_default="0")
    esta_habilitado = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=expression.true(),
    )
    fecha_alta = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, email='{self.email}', rol='{self.rol}')>"

    def autenticar(self, password_ingresado: str) -> bool:
        """Valida si la contraseña ingresada coincide con el hash del usuario.

        Encapsula el acceso a password_hash según el diagrama de clases E4.
        """
        if not self.password_hash or not password_ingresado:
            return False
        try:
            return bcrypt.checkpw(
                password_ingresado.encode("utf-8"),
                self.password_hash.encode("utf-8"),
            )
        except Exception:
            return False
