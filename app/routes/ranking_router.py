"""Controlador para la consulta del ranking general (Tarea 4.1.2, RF-16)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.ranking_schema import RankingResponse
from app.services import ranking_service

TAMANO_PAGINA_POR_DEFECTO = 20
TAMANO_PAGINA_MAXIMO = 100

ranking_router = APIRouter(prefix="/api/ranking", tags=["Ranking"])


@ranking_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Consultar el ranking general",
    description=(
        "Devuelve una página del ranking general de jugadores, ordenado por puntaje "
        "acumulado total de mayor a menor. Incluye solo jugadores habilitados. Además "
        "informa la posición del usuario que consulta (mi_posicion). Disponible para "
        "cualquier usuario autenticado, sin permisos de administrador. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
        },
    },
)
def consultar_ranking(
    usuario_actual: Annotated[Usuario, Depends(obtener_usuario_actual)],
    db: Annotated[Session, Depends(obtener_db)],
    pagina: Annotated[int, Query(ge=1, description="Número de página (comienza en 1)")] = 1,
    tamano_pagina: Annotated[
        int,
        Query(
            ge=1,
            le=TAMANO_PAGINA_MAXIMO,
            description="Cantidad de jugadores por página (máximo 100)",
        ),
    ] = TAMANO_PAGINA_POR_DEFECTO,
) -> RankingResponse:
    """Endpoint de consulta del ranking, delegando la lógica al servicio."""
    return ranking_service.obtener_ranking(
        db, usuario_actual=usuario_actual, pagina=pagina, tamano_pagina=tamano_pagina
    )