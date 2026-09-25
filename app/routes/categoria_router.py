"""Controlador para rutas de Categorías públicas y de juego (Ruleta / Modos de juego)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.schemas.categoria_schema import CategoriaResponse
from app.services import categoria_service

categoria_router = APIRouter(prefix="/api/categorias", tags=["Categorías"])


@categoria_router.get(
    "",
    response_model=list[CategoriaResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar categorías activas para el juego",
    description="Devuelve el listado de categorías activas disponibles para la ruleta y las partidas.",
    responses={
        status.HTTP_200_OK: {
            "description": "Listado de categorías activas obtenido exitosamente.",
            "model": list[CategoriaResponse],
        },
    },
)
def listar_categorias_activas(
    db: Session = Depends(obtener_db),
) -> list[CategoriaResponse]:
    """Devuelve todas las categorías activas en el sistema."""
    return categoria_service.listar_categorias_activas(db)
