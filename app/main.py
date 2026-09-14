"""Punto de entrada de la aplicación FastAPI para FutbolQuiz Arena API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CONFIGURACION
from app.core.exceptions import registrar_manejadores_excepcion
from app.routes.salud_router import salud_router


def crear_aplicacion() -> FastAPI:
    """Crea y configura la instancia de FastAPI."""
    aplicacion = FastAPI(
        title=CONFIGURACION.TITULO_APP,
        version=CONFIGURACION.VERSION_APP,
        description=CONFIGURACION.DESCRIPCION_APP,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configuración de CORS para permitir la conexión con el frontend
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registro de manejadores de excepción globales
    registrar_manejadores_excepcion(aplicacion)

    # Inclusión de routers
    aplicacion.include_router(salud_router)

    return aplicacion


# Instancia principal de la aplicación para Uvicorn
app = crear_aplicacion()

