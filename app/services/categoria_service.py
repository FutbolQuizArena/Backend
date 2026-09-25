"""Lógica de negocio para la administración de categorías (Tarea 5.1.2)."""

from typing import Optional
from sqlalchemy.orm import Session

from app.core.excepciones import (
    CategoriaConPreguntasError,
    CategoriaYaExisteError,
    ExcepcionRecursoNoEncontrado,
)
from app.models.enumeraciones import EstadoCategoria
from app.repositories import categoria_repository
from app.schemas.categoria_schema import (
    CategoriaAdminResponse,
    CategoriaCreate,
    CategoriaUpdate,
)


def crear_categoria(db: Session, datos: CategoriaCreate) -> CategoriaAdminResponse:
    """Crea una nueva categoría validando que su nombre no exista previamente."""
    nombre_limpio = datos.nombre.strip()
    existente = categoria_repository.obtener_categoria_por_nombre(db, nombre_limpio)
    if existente:
        raise CategoriaYaExisteError(
            mensaje=f"Ya existe una categoría con el nombre '{nombre_limpio}'"
        )

    estado = datos.estado or EstadoCategoria.ACTIVA
    categoria = categoria_repository.crear_categoria(db, nombre=nombre_limpio, estado=estado)
    return CategoriaAdminResponse(
        id=categoria.id,
        nombre=categoria.nombre,
        estado=categoria.estado,
        preguntas_count=0,
    )


def obtener_categoria(db: Session, categoria_id: int) -> CategoriaAdminResponse:
    """Obtiene el detalle de una categoría por ID junto a su cantidad de preguntas asociadas."""
    categoria = categoria_repository.obtener_categoria_por_id(db, categoria_id)
    if not categoria:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La categoría con ID {categoria_id} no fue encontrada"
        )

    preguntas_count = categoria_repository.contar_preguntas_asociadas(db, categoria.id)
    return CategoriaAdminResponse(
        id=categoria.id,
        nombre=categoria.nombre,
        estado=categoria.estado,
        preguntas_count=preguntas_count,
    )


def listar_categorias_admin(
    db: Session,
    buscar: Optional[str] = None,
    estado: Optional[EstadoCategoria] = None,
) -> list[CategoriaAdminResponse]:
    """Lista las categorías para el panel de administración aplicando filtros opcionales."""
    resultados = categoria_repository.listar_categorias_admin(db, buscar=buscar, estado=estado)
    return [
        CategoriaAdminResponse(
            id=cat.id,
            nombre=cat.nombre,
            estado=cat.estado,
            preguntas_count=conteo,
        )
        for cat, conteo in resultados
    ]


def actualizar_categoria(
    db: Session,
    categoria_id: int,
    datos: CategoriaUpdate,
) -> CategoriaAdminResponse:
    """Actualiza nombre y/o estado de una categoría existente."""
    categoria = categoria_repository.obtener_categoria_por_id(db, categoria_id)
    if not categoria:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La categoría con ID {categoria_id} no fue encontrada"
        )

    nuevo_nombre = datos.nombre.strip() if datos.nombre is not None else None
    if nuevo_nombre and nuevo_nombre.lower() != categoria.nombre.lower():
        otra = categoria_repository.obtener_categoria_por_nombre(db, nuevo_nombre)
        if otra and otra.id != categoria.id:
            raise CategoriaYaExisteError(
                mensaje=f"Ya existe otra categoría con el nombre '{nuevo_nombre}'"
            )

    categoria_actualizada = categoria_repository.actualizar_categoria(
        db=db,
        categoria=categoria,
        nombre=nuevo_nombre,
        estado=datos.estado,
    )
    preguntas_count = categoria_repository.contar_preguntas_asociadas(db, categoria_actualizada.id)

    return CategoriaAdminResponse(
        id=categoria_actualizada.id,
        nombre=categoria_actualizada.nombre,
        estado=categoria_actualizada.estado,
        preguntas_count=preguntas_count,
    )


def cambiar_estado_categoria(
    db: Session,
    categoria_id: int,
    nuevo_estado: EstadoCategoria,
) -> CategoriaAdminResponse:
    """Permite el toggle o cambio directo de estado de una categoría."""
    categoria = categoria_repository.obtener_categoria_por_id(db, categoria_id)
    if not categoria:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La categoría con ID {categoria_id} no fue encontrada"
        )

    categoria_actualizada = categoria_repository.actualizar_categoria(
        db=db,
        categoria=categoria,
        estado=nuevo_estado,
    )
    preguntas_count = categoria_repository.contar_preguntas_asociadas(db, categoria_actualizada.id)

    return CategoriaAdminResponse(
        id=categoria_actualizada.id,
        nombre=categoria_actualizada.nombre,
        estado=categoria_actualizada.estado,
        preguntas_count=preguntas_count,
    )


def eliminar_categoria(db: Session, categoria_id: int) -> None:
    """Elimina físicamente una categoría si no posee preguntas asociadas."""
    categoria = categoria_repository.obtener_categoria_por_id(db, categoria_id)
    if not categoria:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La categoría con ID {categoria_id} no fue encontrada"
        )

    if categoria_repository.tiene_preguntas_asociadas(db, categoria_id):
        raise CategoriaConPreguntasError(
            mensaje="No se puede eliminar la categoría porque contiene preguntas asociadas"
        )

    categoria_repository.eliminar_categoria(db, categoria)
