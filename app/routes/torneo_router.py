"""Controlador para rutas de gestión y participación en Torneos."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.torneo_schema import TorneoCreadoResponse, TorneoCreate
from app.services import torneo_service

torneo_router = APIRouter(prefix="/api/torneos", tags=["Torneos"])


@torneo_router.post(
    "",
    response_model=TorneoCreadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo torneo",
    description=(
        "Crea un nuevo torneo con cupo de 4, 8 o 16 participantes y contraseña opcional. "
        "Genera automáticamente el código de acceso alfanumérico e inscribe de manera "
        "inmediata al usuario creador como primer participante del torneo. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Torneo creado exitosamente con código de acceso asignado.",
            "model": TorneoCreadoResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación en los datos del torneo (nombre vacío o cupo distinto de 4, 8 o 16).",
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
def crear_torneo(
    datos: TorneoCreate,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> TorneoCreadoResponse:
    """Endpoint para crear un torneo delegando la lógica al servicio."""
    torneo = torneo_service.crear_torneo(
        db=db,
        datos=datos,
        usuario_actual=usuario_actual,
    )
    return TorneoCreadoResponse.model_validate(torneo)

