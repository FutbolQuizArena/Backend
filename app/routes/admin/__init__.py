"""Módulo de rutas para el panel de administración."""

from app.routes.admin.categoria_router import admin_categoria_router
from app.routes.admin.pregunta_router import admin_pregunta_router

__all__ = ["admin_categoria_router", "admin_pregunta_router"]

