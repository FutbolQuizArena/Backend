"""Rutas y controladores de la API REST."""

from app.routes.admin import (
    admin_categoria_router,
    admin_pregunta_router,
    admin_router,
    admin_usuario_router,
)
from app.routes.autenticacion_router import autenticacion_router
from app.routes.categoria_router import categoria_router
from app.routes.duelo_router import duelo_router
from app.routes.partida_router import partida_router
from app.routes.salud_router import salud_router
from app.routes.torneo_router import torneo_router
from app.routes.usuario_router import usuario_router

__all__ = [
    "admin_categoria_router",
    "admin_pregunta_router",
    "admin_router",
    "admin_usuario_router",
    "autenticacion_router",
    "categoria_router",
    "duelo_router",
    "partida_router",
    "salud_router",
    "torneo_router",
    "usuario_router",
]
