"""Controlador del historial personal del jugador (Tareas 4.1.3 a 4.1.5, RF-15 y RF-17)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.historial_schema import HistorialPartidasIndividualesResponse
from app.services import historial_service

historial_router = APIRouter(prefix="/api/historial", tags=["Historial"])


@historial_router.get(
    "/partidas-individuales",
    status_code=status.HTTP_200_OK,
    summary="Consultar el historial de partidas individuales",
    description=(
        "Devuelve las partidas individuales finalizadas del usuario autenticado, de la más "
        "reciente a la más antigua, con su categoría, puntaje final y fecha. Cada jugador "
        "solo ve sus propias partidas. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
        },
    },
)
def consultar_historial_partidas_individuales(
    usuario_actual: Annotated[Usuario, Depends(obtener_usuario_actual)],
    db: Annotated[Session, Depends(obtener_db)],
) -> HistorialPartidasIndividualesResponse:
    """Endpoint del historial de partidas individuales, delegando la lógica al servicio."""
    return historial_service.obtener_historial_partidas_individuales(
        db, usuario_actual=usuario_actual
    )