"""Controlador para verificar el estado de salud y conexión del servicio."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import obtener_db
from app.core.exceptions import ExcepcionBaseDatos

salud_router = APIRouter(prefix="/api", tags=["Salud"])


@salud_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Verificar salud del backend y base de datos",
    description="Comprueba que el backend esté operativo y confirma la conectividad activa con PostgreSQL.",
)
def verificar_salud(db: Session = Depends(obtener_db)) -> dict:
    """Confirma que la base de datos esté accesible y responde con estado OK."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as error_db:
        raise ExcepcionBaseDatos(
            mensaje="No se pudo establecer conexión con la base de datos",
            detalle=str(error_db),
        ) from error_db

