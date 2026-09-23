"""Controlador para rutas de gestión de usuarios y edición de perfil."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.usuario_schema import CambiarPasswordRequest, UsuarioResponse, UsuarioUpdate
from app.services import usuario_service

usuario_router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


@usuario_router.patch(
    "/me",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil del usuario autenticado",
    description=(
        "Permite al usuario autenticado modificar su nombre, correo electrónico y opcionalmente su contraseña. "
        "Si el correo es modificado, se valida que no esté en uso por otra cuenta. "
        "Si se desea cambiar la contraseña, se debe suministrar la contraseña actual válida. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Perfil actualizado exitosamente.",
            "model": UsuarioResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, o contraseña actual incorrecta.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "CREDENCIALES_INVALIDAS",
                        "message": "La contraseña actual es incorrecta",
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
    """Endpoint protegido para actualizar nombre, email y opcionalmente contraseña del usuario actual."""
    usuario_actualizado = usuario_service.actualizar_perfil_usuario(
        db=db,
        usuario_actual=usuario_actual,
        nombre=datos.nombre,
        email=datos.email,
        password_actual=datos.password_actual,
        nueva_password=datos.nueva_password,
    )
    return UsuarioResponse.model_validate(usuario_actualizado)


@usuario_router.patch(
    "/me/password",
    response_model=UsuarioResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar contraseña del usuario autenticado (modal)",
    description=(
        "Permite al usuario autenticado cambiar exclusivamente su contraseña desde el modal de seguridad. "
        "Verifica que la contraseña actual ingresada coincida antes de hashear y persistir la nueva. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Contraseña actualizada exitosamente.",
            "model": UsuarioResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Contraseña actual incorrecta o token no autorizado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "CREDENCIALES_INVALIDAS",
                        "message": "La contraseña actual es incorrecta",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación en los datos enviados.",
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
def cambiar_password_me(
    datos: CambiarPasswordRequest,
    db: Session = Depends(obtener_db),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
) -> UsuarioResponse:
    """Endpoint protegido para el modal de cambio de contraseña."""
    usuario_actualizado = usuario_service.cambiar_password_usuario(
        db=db,
        usuario_actual=usuario_actual,
        password_actual=datos.password_actual,
        nueva_password=datos.nueva_password,
    )
    return UsuarioResponse.model_validate(usuario_actualizado)

