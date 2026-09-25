"""Punto de entrada de la aplicación FastAPI para FutbolQuiz Arena API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import registrar_manejadores_excepcion
from app.routes import (
    admin_router,
    autenticacion_router,
    duelo_router,
    partida_router,
    salud_router,
    torneo_router,
    usuario_router,
)

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

    # Configuración de CORS para permitir la conexión con el frontend (Vite, React, etc.)
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        allow_origin_regex=r"^https?:\/\/.*",
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
    aplicacion.include_router(duelo_router)
    aplicacion.include_router(partida_router)
    aplicacion.include_router(admin_router)

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
        # Asociar BearerAuth y tags a todas las operaciones que requieren autenticación
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if isinstance(operation, dict):
                    # Si es ruta administrativa o requiere seguridad
                    if path.startswith("/api/admin") or "security" in operation:
                        operation["security"] = [{"BearerAuth": []}]
                    # Garantizar el tag "Administración" y documentar 401/403 en rutas de admin
                    if path.startswith("/api/admin"):
                        tags = operation.setdefault("tags", [])
                        if "Administración" not in tags:
                            tags.append("Administración")
                        responses = operation.setdefault("responses", {})
                        responses.setdefault("401", {"description": "Token inválido, expirado o ausente."})
                        responses.setdefault("403", {"description": "Acceso restringido a administradores."})

        aplicacion.openapi_schema = schema
        return aplicacion.openapi_schema

    aplicacion.openapi = openapi_personalizado

    return aplicacion


# Instancia principal de la aplicación para Uvicorn
app = crear_aplicacion()
