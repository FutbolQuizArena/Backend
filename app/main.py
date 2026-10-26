"""Punto de entrada de la aplicación FastAPI para FutbolQuiz Arena API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import registrar_manejadores_excepcion
from app.routes import (
    admin_router,
    autenticacion_router,
    categoria_router,
    duelo_router,
    partida_router,
    ranking_router,
    salud_router,
    torneo_router,
    usuario_router,
)


def configurar_operacion_openapi(ruta: str, operacion: dict) -> None:
    """Documenta la autenticación y las respuestas de una operación."""
    es_administrativa = ruta.startswith("/api/admin")
    if es_administrativa or "security" in operacion:
        operacion["security"] = [{"BearerAuth": []}]

    if not es_administrativa:
        return

    etiquetas = operacion.setdefault("tags", [])
    if "Administración" not in etiquetas:
        etiquetas.append("Administración")
    respuestas = operacion.setdefault("responses", {})
    respuestas.setdefault("401", {"description": "Token inválido, expirado o ausente."})
    respuestas.setdefault("403", {"description": "Acceso restringido a administradores."})


def configurar_operaciones_openapi(esquema: dict) -> None:
    """Aplica la documentación de seguridad a las operaciones del esquema."""
    for ruta, elementos_ruta in esquema.get("paths", {}).items():
        for operacion in elementos_ruta.values():
            if isinstance(operacion, dict):
                configurar_operacion_openapi(ruta, operacion)


def configurar_openapi(aplicacion: FastAPI) -> None:
    """Configura Bearer JWT en Swagger y conserva la caché de OpenAPI."""
    def openapi_personalizado() -> dict:
        if aplicacion.openapi_schema:
            return aplicacion.openapi_schema

        esquema = get_openapi(
            title=aplicacion.title,
            version=aplicacion.version,
            description=aplicacion.description,
            routes=aplicacion.routes,
        )
        esquema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Pegá el token JWT obtenido en /api/auth/login (sin las comillas ni 'Bearer').",
            }
        }
        configurar_operaciones_openapi(esquema)
        aplicacion.openapi_schema = esquema
        return esquema

    aplicacion.openapi = openapi_personalizado


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
    aplicacion.include_router(categoria_router)
    aplicacion.include_router(torneo_router)
    aplicacion.include_router(duelo_router)
    aplicacion.include_router(partida_router)
    aplicacion.include_router(ranking_router)
    aplicacion.include_router(admin_router)

    configurar_openapi(aplicacion)

    return aplicacion


# Instancia principal de la aplicación para Uvicorn
app = crear_aplicacion()
