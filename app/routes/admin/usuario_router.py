"""Controlador para la gestión de usuarios en el panel de administración (Tarea 5.1.3)."""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario_schema import (
    UsuarioAdminCreate,
    UsuarioAdminResponse,
    UsuarioAdminUpdate,
    UsuarioCambiarEstadoRequest,
)
from app.services import usuario_service

admin_usuario_router = APIRouter(
    prefix="/usuarios",
    tags=["Administración"],
    dependencies=[
        Depends(obtener_usuario_actual),
        Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
    ],
)


@admin_usuario_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario desde administración",
    description="Crea una cuenta habilitada con rol JUGADOR o ADMINISTRADOR. La contraseña se almacena hasheada.",
    responses={
        401: {"description": "Token inválido, expirado o ausente."},
        403: {"description": "Acceso restringido a administradores."},
        409: {"description": "El correo electrónico ya se encuentra registrado."},
        422: {"description": "Datos de usuario inválidos."},
    },
)
def crear_usuario(
    datos: UsuarioAdminCreate,
    db: Annotated[Session, Depends(obtener_db)],
) -> UsuarioAdminResponse:
    """Da de alta un usuario con el rol indicado por el administrador."""
    return UsuarioAdminResponse.model_validate(usuario_service.crear_usuario_admin(db, datos))


@admin_usuario_router.patch(
    "/{usuario_id}",
    summary="Editar usuario desde administración",
    description="Actualiza los campos enviados de nombre, email y rol, conservando contraseña, puntaje y estado.",
    responses={
        400: {"description": "Un administrador no puede quitarse su propio rol."},
        401: {"description": "Token inválido, expirado o ausente."},
        403: {"description": "Acceso restringido a administradores."},
        404: {"description": "Usuario no encontrado."},
        409: {"description": "El correo electrónico ya pertenece a otro usuario."},
        422: {"description": "Datos de usuario inválidos."},
    },
)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioAdminUpdate,
    db: Annotated[Session, Depends(obtener_db)],
    admin_actual: Annotated[Usuario, Depends(requiere_rol(RolUsuario.ADMINISTRADOR))],
) -> UsuarioAdminResponse:
    """Edita los datos administrativos de una cuenta existente."""
    usuario = usuario_service.actualizar_usuario_admin(db, admin_actual, usuario_id, datos)
    return UsuarioAdminResponse.model_validate(usuario)


@admin_usuario_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios",
    description="Devuelve el listado de usuarios con filtros opcionales de búsqueda por texto, rol y estado.",
    responses={
        status.HTTP_200_OK: {
            "description": "Listado de usuarios recuperado exitosamente.",
            "model": list[UsuarioAdminResponse],
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
    },
)
def listar_usuarios(
    buscar: Optional[str] = Query(None, description="Búsqueda por coincidencia en nombre o correo electrónico"),
    rol: Optional[RolUsuario] = Query(None, description="Filtrar por rol: JUGADOR o ADMINISTRADOR"),
    esta_habilitado: Optional[bool] = Query(None, description="Filtrar por estado de habilitación"),
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> list[UsuarioAdminResponse]:
    """Lista usuarios para el panel de administración."""
    return usuario_service.listar_usuarios_admin(
        db,
        buscar=buscar,
        rol=rol,
        esta_habilitado=esta_habilitado,
    )


@admin_usuario_router.get(
    "/{usuario_id}",
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de usuario",
    description="Devuelve la información administrativa de un usuario específico por su ID.",
    responses={
        status.HTTP_200_OK: {
            "description": "Detalle del usuario recuperado exitosamente.",
            "model": UsuarioAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Usuario no encontrado."},
    },
)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> UsuarioAdminResponse:
    """Consulta los datos de un usuario puntual."""
    return usuario_service.obtener_usuario_admin(db, usuario_id)


@admin_usuario_router.patch(
    "/{usuario_id}/estado",
    status_code=status.HTTP_200_OK,
    summary="Cambiar estado de habilitación de usuario",
    description="Permite habilitar o deshabilitar una cuenta de usuario sin borrar su historial ni puntajes acumulados.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estado del usuario actualizado exitosamente.",
            "model": UsuarioAdminResponse,
        },
        status.HTTP_400_BAD_REQUEST: {"description": "Un administrador no puede deshabilitar su propia cuenta."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Usuario no encontrado."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Cuerpo de solicitud inválido."},
    },
)
def cambiar_estado_usuario(
    usuario_id: int,
    datos: UsuarioCambiarEstadoRequest,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> UsuarioAdminResponse:
    """Modifica el estado de habilitación de un usuario."""
    return usuario_service.cambiar_estado_usuario(
        db,
        admin_actual=admin_actual,
        usuario_id=usuario_id,
        nuevo_estado=datos.esta_habilitado,
    )

