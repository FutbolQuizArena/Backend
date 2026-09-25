"""Controlador para la gestión de preguntas en el panel de administración (Tarea 5.1.1)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.models.enumeraciones import EstadoPregunta, RolUsuario
from app.models.usuario import Usuario
from app.schemas.comun_schema import MensajeResponse
from app.schemas.pregunta_schema import (
    PreguntaAdminResponse,
    PreguntaCambiarEstadoRequest,
    PreguntaCreate,
    PreguntaListadoResponse,
    PreguntaUpdate,
)
from app.services import pregunta_service

admin_pregunta_router = APIRouter(
    prefix="/preguntas",
    tags=["Administración"],
    dependencies=[
        Depends(obtener_usuario_actual),
        Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
    ],
)


@admin_pregunta_router.post(
    "",
    response_model=PreguntaAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva pregunta",
    description=(
        "Permite a un administrador crear una nueva pregunta de opción múltiple "
        "con sus cuatro opciones obligatorias, categoría y respuesta correcta ('A', 'B', 'C' o 'D')."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Pregunta creada exitosamente en el banco de contenido.",
            "model": PreguntaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "La categoría indicada no existe."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Error en la validación de campos u opciones."},
    },
)
def crear_pregunta(
    datos: PreguntaCreate,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaAdminResponse:
    """Crea una pregunta en el banco de preguntas."""
    pregunta = pregunta_service.crear_pregunta(db, datos)
    return PreguntaAdminResponse.model_validate(pregunta)


@admin_pregunta_router.get(
    "",
    response_model=PreguntaListadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar preguntas con paginación y filtros",
    description=(
        "Devuelve un listado paginado (6 preguntas por página) de preguntas no eliminadas. "
        "Permite filtrar por búsqueda parcial de texto en el enunciado, categoría y estado (ACTIVA o BORRADOR)."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Listado de preguntas recuperado exitosamente.",
            "model": PreguntaListadoResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
    },
)
def listar_preguntas(
    page: int = Query(1, ge=1, description="Número de página a consultar (comienza en 1)"),
    buscar: Optional[str] = Query(None, description="Búsqueda libre por texto en el enunciado"),
    categoria_id: Optional[int] = Query(None, description="Filtrar por identificador de categoría"),
    estado: Optional[EstadoPregunta] = Query(None, description="Filtrar por estado: ACTIVA o BORRADOR"),
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaListadoResponse:
    """Consulta la lista paginada de preguntas con filtros."""
    return pregunta_service.listar_preguntas(
        db=db,
        page=page,
        page_size=6,
        buscar=buscar,
        categoria_id=categoria_id,
        estado=estado,
    )


@admin_pregunta_router.get(
    "/{pregunta_id}",
    response_model=PreguntaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una pregunta",
    description="Devuelve la información completa de una pregunta específica por su ID.",
    responses={
        status.HTTP_200_OK: {
            "description": "Detalle de la pregunta recuperado exitosamente.",
            "model": PreguntaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Pregunta inexistente o eliminada."},
    },
)
def obtener_pregunta(
    pregunta_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaAdminResponse:
    """Consulta una pregunta puntual por ID."""
    pregunta = pregunta_service.obtener_pregunta(db, pregunta_id)
    return PreguntaAdminResponse.model_validate(pregunta)


@admin_pregunta_router.patch(
    "/{pregunta_id}",
    response_model=PreguntaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar parcialmente una pregunta",
    description="Permite modificar el enunciado, opciones, categoría, dificultad o estado de una pregunta existente.",
    responses={
        status.HTTP_200_OK: {
            "description": "Pregunta actualizada exitosamente.",
            "model": PreguntaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Pregunta o categoría inexistente."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Error en validación de datos enviados."},
    },
)
def actualizar_pregunta(
    pregunta_id: int,
    datos: PreguntaUpdate,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaAdminResponse:
    """Actualiza una pregunta existente."""
    pregunta = pregunta_service.actualizar_pregunta(db, pregunta_id, datos)
    return PreguntaAdminResponse.model_validate(pregunta)


@admin_pregunta_router.delete(
    "/{pregunta_id}",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Eliminar pregunta (soft-delete)",
    description=(
        "Aplica una baja lógica a la pregunta seteando su fecha de eliminación. "
        "La pregunta no aparecerá más en los listados del panel ni en las partidas nuevas, "
        "pero se preserva el registro físico para mantener intacto el historial de partidas ya jugadas."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Pregunta eliminada exitosamente del banco de contenido.",
            "model": MensajeResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Pregunta no encontrada o ya eliminada."},
    },
)
def eliminar_pregunta(
    pregunta_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> MensajeResponse:
    """Elimina lógicamente una pregunta."""
    pregunta_service.eliminar_pregunta(db, pregunta_id)
    return MensajeResponse(mensaje="Pregunta eliminada exitosamente del banco de contenido")


@admin_pregunta_router.post(
    "/{pregunta_id}/duplicar",
    response_model=PreguntaAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicar pregunta existente",
    description=(
        "Crea una copia idéntica de la pregunta indicada en estado BORRADOR "
        "para que el administrador pueda revisarla o editarla antes de publicarla."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Pregunta duplicada exitosamente en estado BORRADOR.",
            "model": PreguntaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Pregunta origen no encontrada o eliminada."},
    },
)
def duplicar_pregunta(
    pregunta_id: int,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaAdminResponse:
    """Duplica una pregunta existente."""
    copia = pregunta_service.duplicar_pregunta(db, pregunta_id)
    return PreguntaAdminResponse.model_validate(copia)


@admin_pregunta_router.patch(
    "/{pregunta_id}/estado",
    response_model=PreguntaAdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar estado de la pregunta",
    description="Permite alternar rápidamente el estado de la pregunta entre ACTIVA y BORRADOR.",
    responses={
        status.HTTP_200_OK: {
            "description": "Estado de la pregunta actualizado exitosamente.",
            "model": PreguntaAdminResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Token inválido, expirado o ausente."},
        status.HTTP_403_FORBIDDEN: {"description": "Acceso restringido a usuarios administradores."},
        status.HTTP_404_NOT_FOUND: {"description": "Pregunta no encontrada o eliminada."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Estado inválido proporcionado."},
    },
)
def cambiar_estado_pregunta(
    pregunta_id: int,
    datos: PreguntaCambiarEstadoRequest,
    db: Session = Depends(obtener_db),
    admin_actual: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR)),
) -> PreguntaAdminResponse:
    """Cambia el estado de una pregunta."""
    pregunta = pregunta_service.cambiar_estado_pregunta(db, pregunta_id, datos.estado)
    return PreguntaAdminResponse.model_validate(pregunta)
