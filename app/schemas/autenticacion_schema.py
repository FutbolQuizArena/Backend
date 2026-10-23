"""Esquemas Pydantic para el módulo de autenticación y tokens JWT."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Esquema de solicitud para inicio de sesión."""

    email: EmailStr = Field(
        ...,
        max_length=255,
        description="Correo electrónico registrado del usuario",
        examples=["usuario@futbolquiz.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Contraseña en texto plano para verificar",
        examples=["passwordSeguro123"],
    )


class TokenResponse(BaseModel):
    """Esquema de respuesta exitosa de autenticación con token de acceso."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(
        ...,
        description="Token de acceso JSON Web Token (JWT)",
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo de esquema de autorización",
        examples=["bearer"],
    )

