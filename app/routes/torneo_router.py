"""Controlador para rutas de gestión y participación en Torneos."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.torneo_schema import (
    TorneoCreadoResponse,
    TorneoCreate,
    TorneoResponse,
    TorneoUnirseRequest,
)
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


@torneo_router.post(
    "/unirse",
    response_model=TorneoResponse,
    status_code=status.HTTP_200_OK,
    summary="Unirse a un torneo mediante código de acceso",
    description=(
        "Permite a un usuario autenticado unirse a un torneo existente utilizando su código "
        "de acceso y contraseña (si el torneo es privado). Si al unirse se alcanza el cupo "
        "máximo de participantes, el torneo transiciona automáticamente al estado EN_CURSO. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Unión exitosa al torneo. Retorna el estado actualizado del torneo.",
            "model": TorneoResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "El torneo no está disponible para unirse (código inexistente, contraseña errónea, torneo completo o no disponible).",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TORNEO_NO_DISPONIBLE",
                        "message": "El torneo no se encuentra disponible para unirse",
                        "detail": None,
                    }
                }
            },
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
            "description": "Error de validación en los datos de la solicitud.",
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
def unirse_a_torneo(
    datos: TorneoUnirseRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> TorneoResponse:
    """Endpoint para unirse a un torneo delegando la lógica al servicio."""
    torneo = torneo_service.unirse_a_torneo(
        db=db,
        datos=datos,
        usuario_actual=usuario_actual,
    )
    return TorneoResponse.model_validate(torneo)
