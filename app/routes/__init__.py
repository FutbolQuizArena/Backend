"""Rutas y controladores de la API REST."""
from app.routes.autenticacion_router import autenticacion_router
from app.routes.salud_router import salud_router
from app.routes.torneo_router import torneo_router
from app.routes.usuario_router import usuario_router

__all__ = ["autenticacion_router", "salud_router", "torneo_router", "usuario_router"]
