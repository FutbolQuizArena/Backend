"""Router maestro para la consolidación y defensa en profundidad del panel de administración (Tarea 5.1.4)."""

from fastapi import APIRouter, Depends

from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.models.enumeraciones import RolUsuario
from app.routes.admin.categoria_router import admin_categoria_router
from app.routes.admin.pregunta_router import admin_pregunta_router
from app.routes.admin.usuario_router import admin_usuario_router

admin_router = APIRouter(
    prefix="/api/admin",
    tags=["Administración"],
    dependencies=[
        Depends(obtener_usuario_actual),
        Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
    ],
)

# Inclusión de subrouters bajo el prefijo raíz /api/admin
admin_router.include_router(admin_pregunta_router)
admin_router.include_router(admin_categoria_router)
admin_router.include_router(admin_usuario_router)
