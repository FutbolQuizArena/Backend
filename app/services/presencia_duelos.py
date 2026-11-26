"""Revisión de duelos independiente de las pestañas y tolerante a varios workers."""

import asyncio
from contextlib import asynccontextmanager
import logging

from app.core.base_datos import SesionLocal, obtener_db
from app.services.duelo_service import cerrar_duelos_desconectados

logger = logging.getLogger(__name__)


def revisar_duelos() -> None:
    with SesionLocal() as db:
        cerrar_duelos_desconectados(db)


async def _revisar_periodicamente() -> None:
    while True:
        await asyncio.sleep(5)
        try:
            await asyncio.to_thread(revisar_duelos)
        except Exception:
            logger.exception("No se pudo revisar la presencia de los duelos; se reintentará")


@asynccontextmanager
async def ciclo_presencia(aplicacion):
    # Los clientes de tests con DB reemplazada no deben consultar la DB del despliegue.
    if obtener_db in aplicacion.dependency_overrides:
        yield
        return
    tarea = asyncio.create_task(_revisar_periodicamente())
    try:
        yield
    finally:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass
