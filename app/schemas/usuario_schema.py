"""Esquemas Pydantic para la entidad Usuario."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import RolUsuario


class UsuarioBase(BaseModel):
    """Atributos compartidos del usuario."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre o apodo del usuario")
    email: EmailStr = Field(..., max_length=255, description="Correo electrónico único del usuario")


class UsuarioCreate(UsuarioBase):
    """Esquema para creación interna de usuario en el servicio (recibe password, no expone password_hash)."""

    password: str = Field(..., min_length=6, description="Contraseña en texto plano para procesar en el servicio")
    rol: RolUsuario = Field(default=RolUsuario.JUGADOR, description="Rol asignado al usuario")


class UsuarioUpdate(UsuarioBase):
    """Esquema para actualización de datos de perfil del usuario autenticado."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre o apodo actualizado del usuario")
    email: EmailStr = Field(..., max_length=255, description="Correo electrónico actualizado del usuario")


class UsuarioResponse(BaseModel):
    """Esquema de respuesta devuelto al frontend. Nunca expone password_hash ni password."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del usuario")
    nombre: str = Field(..., description="Nombre o apodo del usuario")
    email: EmailStr = Field(..., description="Correo electrónico del usuario")
    rol: RolUsuario = Field(..., description="Rol del usuario")
    puntaje_total: int = Field(default=0, description="Puntaje total acumulado")
    esta_habilitado: bool = Field(default=True, description="Indica si el usuario está habilitado")
    fecha_alta: datetime | None = Field(default=None, description="Fecha de alta del usuario")

