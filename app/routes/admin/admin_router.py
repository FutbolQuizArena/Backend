"""Router maestro para la consolidación y defensa en profundidad del panel de administración (Tarea 5.1.4)."""

from fastapi import APIRouter, Depends

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.routes.admin.categoria_router import admin_categoria_router
from app.routes.admin.pregunta_router import admin_pregunta_router
from app.routes.admin.usuario_router import admin_usuario_router
from app.schemas.comun_schema import SemillaResumenResponse
from app.services import semilla_service
from sqlalchemy.orm import Session

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


@admin_router.post(
    "/sistema/sembrar",
    response_model=SemillaResumenResponse,
    summary="Sembrar categorías y preguntas iniciales",
    description=(
        "Lee el archivo de datos semilla (scripts/preguntas_seed.json) y persiste "
        "las categorías y preguntas en la base de datos de manera modular e idempotente."
    ),
    responses={
        200: {
            "description": "Siembra procesada exitosamente.",
            "model": SemillaResumenResponse,
        },
        401: {"description": "Token inválido, expirado o ausente."},
        403: {"description": "Acceso denegado (requiere rol ADMINISTRADOR)."},
    },
)
def sembrar_datos_sistema(
    db: Session = Depends(obtener_db),
    admin: Usuario = Depends(obtener_usuario_actual),
) -> SemillaResumenResponse:
    """Ejecuta la siembra de preguntas y categorías desde el archivo seed JSON."""
    preguntas = semilla_service.cargar_preguntas_desde_json()
    resumen = semilla_service.sembrar_preguntas_y_categorias(db, preguntas)
    return SemillaResumenResponse(**resumen)
