"""Controlador para la gestión de categorías en el panel de administración (Tarea 5.1.2)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.models.enumeraciones import EstadoCategoria, RolUsuario
from app.models.usuario import Usuario
from app.schemas.categoria_schema import (
    CategoriaAdminResponse,
    CategoriaCambiarEstadoRequest,
    CategoriaCreate,
    CategoriaUpdate,
)
from app.schemas.comun_schema import MensajeResponse
from app.services import categoria_service

admin_categoria_router = APIRouter(
    prefix="/api/admin/categorias",
    tags=["Administración"],
    dependencies=[
        Depends(obtener_usuario_actual),
        Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
    ],
)


@admin_categoria_router.post(
    "",
    response_model=CategoriaAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva categoría",
    description="Permite a un administrador crear una nueva categoría de preguntas en el sistema.",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Categoría creada exitosamente.",
            "model": CategoriaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_409_CONFLICT: {"description": "Ya existe una categoría con ese nombre."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Nombre de categoría inválido o vacío."},
    },
)
def crear_categoria(
    datos: CategoriaCreate,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> CategoriaAdminResponse:
    """Crea una nueva categoría."""
    return categoria_service.crear_categoria(db, datos)


@admin_categoria_router.get(
    "",
    response_model=list[CategoriaAdminResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar categorías",
    description="Devuelve el listado de categorías con la cantidad de preguntas asociadas y filtros opcionales.",
    responses={
        status.HTTP_200_OK: {
            "description": "Listado de categorías recuperado exitosamente.",
            "model": list[CategoriaAdminResponse],
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
    },
)
def listar_categorias(
    buscar: Optional[str] = Query(None, description="Búsqueda libre por coincidencia de nombre"),
    estado: Optional[EstadoCategoria] = Query(None, description="Filtrar por estado: ACTIVA o BORRADOR"),
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> list[CategoriaAdminResponse]:
    """Lista las categorías con filtros de búsqueda y estado."""
    return categoria_service.listar_categorias_admin(db, buscar=buscar, estado=estado)


@admin_categoria_router.get(
    "/{categoria_id}",
    response_model=CategoriaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de categoría",
    description="Devuelve la información de una categoría específica por su ID junto a su cantidad de preguntas.",
    responses={
        status.HTTP_200_OK: {
            "description": "Detalle de la categoría recuperado exitosamente.",
            "model": CategoriaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Categoría no encontrada."},
    },
)
def obtener_categoria(
    categoria_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> CategoriaAdminResponse:
    """Consulta una categoría puntual por ID."""
    return categoria_service.obtener_categoria(db, categoria_id)


@admin_categoria_router.patch(
    "/{categoria_id}",
    response_model=CategoriaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar categoría",
    description="Permite modificar el nombre y/o estado de una categoría existente.",
    responses={
        status.HTTP_200_OK: {
            "description": "Categoría actualizada exitosamente.",
            "model": CategoriaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Categoría no encontrada."},
        status.HTTP_409_CONFLICT: {"description": "El nuevo nombre ya pertenece a otra categoría."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Datos de actualización inválidos."},
    },
)
def actualizar_categoria(
    categoria_id: int,
    datos: CategoriaUpdate,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> CategoriaAdminResponse:
    """Actualiza una categoría existente."""
    return categoria_service.actualizar_categoria(db, categoria_id, datos)


@admin_categoria_router.patch(
    "/{categoria_id}/estado",
    response_model=CategoriaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar estado de categoría",
    description="Permite alternar rápidamente el estado de la categoría entre ACTIVA y BORRADOR.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estado de la categoría actualizado exitosamente.",
            "model": CategoriaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Categoría no encontrada."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Estado inválido proporcionado."},
    },
)
def cambiar_estado_categoria(
    categoria_id: int,
    datos: CategoriaCambiarEstadoRequest,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> CategoriaAdminResponse:
    """Cambia el estado de una categoría puntual."""
    return categoria_service.cambiar_estado_categoria(db, categoria_id, datos.estado)


@admin_categoria_router.delete(
    "/{categoria_id}",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Eliminar categoría",
    description=(
        "Elimina físicamente una categoría del sistema si no posee preguntas asociadas. "
        "Si posee preguntas vinculadas, la operación es rechazada con código 400 Bad Request."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Categoría eliminada exitosamente.",
            "model": MensajeResponse,
        },
        status.HTTP_400_BAD_REQUEST: {"description": "La categoría posee preguntas asociadas."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Categoría no encontrada."},
    },
)
def eliminar_categoria(
    categoria_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> MensajeResponse:
    """Elimina una categoría vacía."""
    categoria_service.eliminar_categoria(db, categoria_id)
    return MensajeResponse(mensaje="Categoría eliminada exitosamente")
