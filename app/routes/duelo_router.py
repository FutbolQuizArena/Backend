"""Controlador para rutas de consulta de Duelos (Tarea 2.1.11)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.excepciones import ExcepcionNoAutorizado, ExcepcionRecursoNoEncontrado
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.repositories import duelo_repository
from app.schemas.duelo_schema import DueloEstadoResponse
from app.services.duelo_juego_service import finalizar_duelo_si_corresponde

duelo_router = APIRouter(prefix="/api/duelos", tags=["Duelos"])


@duelo_router.get(
    "/{duelo_id}",
    response_model=DueloEstadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar estado y resultado de un duelo",
    description=(
        "Devuelve el estado actual de un duelo (esperando rival, en curso o finalizado) "
        "y, si ya está finalizado, el puntaje de ambos jugadores y quién ganó. "
        "Solo pueden consultarlo los dos jugadores que participan del duelo. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
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
        status.HTTP_403_FORBIDDEN: {
            "description": "El usuario autenticado no participa de este duelo.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "NO_AUTORIZADO",
                        "message": "No formás parte de este duelo",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "El duelo especificado no fue encontrado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "RECURSO_NO_ENCONTRADO",
                        "message": "No se encontró el duelo",
                        "detail": None,
                    }
                }
            },
        },
    },
)
def consultar_estado_duelo(
    duelo_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> DueloEstadoResponse:
    """Endpoint para consultar el estado/resultado de un duelo, finalizándolo si ya corresponde."""
    duelo = duelo_repository.obtener_duelo_por_id(db, duelo_id)
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró el duelo")

    if usuario_actual.id not in (duelo.jugador1_id, duelo.jugador2_id):
        raise ExcepcionNoAutorizado(mensaje="No formás parte de este duelo")

    duelo = finalizar_duelo_si_corresponde(db, duelo_id)
    return DueloEstadoResponse.model_validate(duelo)