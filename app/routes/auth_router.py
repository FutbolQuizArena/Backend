"""Controlador para rutas de autenticación y registro de usuarios."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import obtener_db
from app.schemas.usuario_schema import UsuarioCreate, UsuarioResponse
from app.services import usuario_service

auth_router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@auth_router.post(
    "/registro",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description=(
        "Permite dar de alta una nueva cuenta de usuario en la plataforma. "
        "Verifica que el correo electrónico no se encuentre registrado previamente, "
        "hashea la contraseña de manera segura y asigna el rol JUGADOR por defecto."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Usuario registrado exitosamente.",
            "model": UsuarioResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflicto: El correo electrónico ya se encuentra registrado.",
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
        422: {
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
def registrar(
    datos: UsuarioCreate,
    db: Session = Depends(obtener_db),
) -> UsuarioResponse:
    """Endpoint para registrar un usuario delegando la lógica al servicio."""
    usuario_creado = usuario_service.registrar_usuario(db=db, datos=datos)
    return UsuarioResponse.model_validate(usuario_creado)
