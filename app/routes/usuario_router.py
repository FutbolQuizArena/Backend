"""Controlador para rutas de gestión de usuarios y edición de perfil."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioResponse, UsuarioUpdate
from app.services import usuario_service

usuario_router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


@usuario_router.patch(
    "/me",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario autenticado",
    description=(
        "Permite al usuario autenticado modificar su nombre y correo electrónico. "
        "Si el correo es modificado, se valida que no esté en uso por otra cuenta. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Perfil actualizado exitosamente.",
            "model": UsuarioResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token de autenticación no proporcionado, inválido o expirado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TOKEN_INVALIDO",
                        "message": "Token de autenticación inválido o expirado",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_409_CONFLICT: {
            "description": "El nuevo correo electrónico ya se encuentra registrado por otro usuario.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "EMAIL_YA_REGISTRADO",
                        "message": "El correo electrónico ya se encuentra registrado",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación en los datos del cuerpo de la solicitud.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ERROR_VALIDACION",
                        "message": "Error de validación en los datos de la solicitud",
                        "detail": "[...]",
                    }
                }
            },
        },
    },
)
def actualizar_perfil_me(
    datos: UsuarioUpdate,
    db: Session = Depends(obtener_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
) -> UsuarioResponse:
    """Endpoint protegido para actualizar nombre y email del usuario actual."""
    usuario_actualizado = usuario_service.actualizar_perfil_usuario(
        db=db,
        usuario_actual=usuario_actual,
        nombre=datos.nombre,
        email=datos.email,
    )
    return UsuarioResponse.model_validate(usuario_actualizado)

