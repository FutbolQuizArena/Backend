"""Punto de entrada de la aplicación FastAPI para FutbolQuiz Arena API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import registrar_manejadores_excepcion
from app.routes.autenticacion_router import autenticacion_router
from app.routes.salud_router import salud_router
from app.routes.torneo_router import torneo_router
from app.routes.usuario_router import usuario_router


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
    aplicacion.include_router(autenticacion_router)
    aplicacion.include_router(usuario_router)
    aplicacion.include_router(torneo_router)

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
        # Configuración de BearerAuth estándar en componentes OpenAPI
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Pegá el token JWT obtenido en /api/auth/login (sin las comillas ni 'Bearer').",
            }
        }
        # Asociar BearerAuth a todas las operaciones que requieren autenticación
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if isinstance(operation, dict) and "security" in operation:
                    operation["security"] = [{"BearerAuth": []}]

        aplicacion.openapi_schema = schema
        return aplicacion.openapi_schema

    aplicacion.openapi = openapi_personalizado

    return aplicacion


# Instancia principal de la aplicación para Uvicorn
app = crear_aplicacion()

