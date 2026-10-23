"""Esquemas Pydantic para la entidad Usuario."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.enumeraciones import RolUsuario


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
    password_actual: str | None = Field(default=None, description="Contraseña actual requerida si se desea cambiarla")
    nueva_password: str | None = Field(default=None, min_length=6, description="Nueva contraseña (opcional, mínimo 6 caracteres)")

    @model_validator(mode="after")
    def validar_password_actual_si_hay_nueva(self) -> "UsuarioUpdate":
        if self.nueva_password and not self.password_actual:
            raise ValueError("Debe proporcionar la contraseña actual para definir una nueva contraseña")
        return self


class CambiarPasswordRequest(BaseModel):
    """Esquema para cambio directo de contraseña desde el modal de seguridad."""

    password_actual: str = Field(..., min_length=1, description="Contraseña actual del usuario")
    nueva_password: str = Field(..., min_length=6, description="Nueva contraseña (mínimo 6 caracteres)")


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


class UsuarioCambiarEstadoRequest(BaseModel):
    """Esquema de solicitud para habilitar o deshabilitar una cuenta de usuario."""

    esta_habilitado: bool = Field(
        ...,
        description="Nuevo estado de habilitación (True para habilitar, False para deshabilitar)",
    )


class UsuarioAdminResponse(UsuarioResponse):
    """Esquema de respuesta para vistas de administración de usuarios.

    Serializa id, nombre, email, rol, puntaje_total, esta_habilitado y fecha_alta,
    asegurando nunca exponer password_hash ni contraseñas.
    """

    pass

