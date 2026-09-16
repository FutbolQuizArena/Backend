"""Punto de entrada de la aplicación FastAPI para FutbolQuiz Arena API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CONFIGURACION
from app.core.exceptions import registrar_manejadores_excepcion
from app.routes.auth_router import auth_router
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
    aplicacion.include_router(auth_router)

    # Configuración de OpenAPI para habilitar el botón "Authorize" (Bearer JWT) en Swagger UI
    from fastapi.openapi.utils import get_openapi

    def openapi_personalizado():
        if aplicacion.openapi_schema:
            return aplicacion.openapi_schema
        schema = get_openapi(
            title=aplicacion.title,
            version=aplicacion.version,
            description=aplicacion.description,
            routes=aplicacion.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Ingrese el token JWT obtenido en /api/auth/login para autorizar peticiones.",
            }
        }
        aplicacion.openapi_schema = schema
        return aplicacion.openapi_schema

    aplicacion.openapi = openapi_personalizado

    return aplicacion


# Instancia principal de la aplicación para Uvicorn
app = crear_aplicacion()

