"""Lógica de negocio y servicios para la administración de preguntas (Tarea 5.1.1)."""

import math
from typing import Optional
from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionRecursoNoEncontrado
from app.models.enumeraciones import EstadoPregunta
from app.models.pregunta import Pregunta
from app.repositories import categoria_repository, pregunta_repository
from app.schemas.pregunta_schema import (
    PreguntaAdminResponse,
    PreguntaCreate,
    PreguntaListadoResponse,
    PreguntaUpdate,
)


def crear_pregunta(db: Session, datos: PreguntaCreate) -> Pregunta:
    """Crea una nueva pregunta validando previamente la existencia de la categoría."""
    categoria = categoria_repository.obtener_categoria_por_id(db, datos.categoria_id)
    if not categoria:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La categoría con ID {datos.categoria_id} no existe",
            detalle="No se puede asociar una pregunta a una categoría inexistente",
        )

    nueva_pregunta = Pregunta(
        enunciado=datos.enunciado,
        categoria_id=datos.categoria_id,
        opcion_a=datos.opcion_a,
        opcion_b=datos.opcion_b,
        opcion_c=datos.opcion_c,
        opcion_d=datos.opcion_d,
        respuesta_correcta=datos.respuesta_correcta,
        dificultad=datos.dificultad or "Media",
        estado=datos.estado or EstadoPregunta.ACTIVA,
        eliminada_en=None,
    )
    return pregunta_repository.crear(db, nueva_pregunta)


def obtener_pregunta(db: Session, pregunta_id: int) -> Pregunta:
    """
    Obtiene una pregunta por su ID. Lanza HTTP 404 si no existe
    o si fue marcada como eliminada (soft-delete).
    """
    pregunta = pregunta_repository.obtener_por_id(db, pregunta_id, incluir_eliminadas=False)
    if not pregunta:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"La pregunta con ID {pregunta_id} no fue encontrada",
            detalle="La pregunta no existe o fue eliminada del banco de contenido",
        )
    return pregunta


def actualizar_pregunta(db: Session, pregunta_id: int, datos: PreguntaUpdate) -> Pregunta:
    """Actualiza los campos provistos de una pregunta existente."""
    pregunta = obtener_pregunta(db, pregunta_id)

    if datos.categoria_id is not None and datos.categoria_id != pregunta.categoria_id:
        categoria = categoria_repository.obtener_categoria_por_id(db, datos.categoria_id)
        if not categoria:
            raise ExcepcionRecursoNoEncontrado(
                mensaje=f"La categoría con ID {datos.categoria_id} no existe",
                detalle="No se puede asociar una pregunta a una categoría inexistente",
            )
        pregunta.categoria_id = datos.categoria_id

    if datos.enunciado is not None:
        pregunta.enunciado = datos.enunciado
    if datos.opcion_a is not None:
        pregunta.opcion_a = datos.opcion_a
    if datos.opcion_b is not None:
        pregunta.opcion_b = datos.opcion_b
    if datos.opcion_c is not None:
        pregunta.opcion_c = datos.opcion_c
    if datos.opcion_d is not None:
        pregunta.opcion_d = datos.opcion_d
    if datos.respuesta_correcta is not None:
        pregunta.respuesta_correcta = datos.respuesta_correcta
    if datos.dificultad is not None:
        pregunta.dificultad = datos.dificultad
    if datos.estado is not None:
        pregunta.estado = datos.estado

    return pregunta_repository.actualizar(db, pregunta)


def cambiar_estado_pregunta(
    db: Session, pregunta_id: int, nuevo_estado: EstadoPregunta
) -> Pregunta:
    """Modifica el estado de una pregunta (toggle rápido ACTIVA <-> BORRADOR)."""
    pregunta = obtener_pregunta(db, pregunta_id)
    pregunta.estado = nuevo_estado
    return pregunta_repository.actualizar(db, pregunta)


def eliminar_pregunta(db: Session, pregunta_id: int) -> None:
    """
    Aplica soft-delete a la pregunta. Conserva la fila en la base de datos
    para asegurar la integridad referencial con partidas históricas que la hayan usado.
    """
    pregunta = obtener_pregunta(db, pregunta_id)
    pregunta_repository.marcar_eliminada(db, pregunta)


def duplicar_pregunta(db: Session, pregunta_id: int) -> Pregunta:
    """
    Clona una pregunta existente.
    Por seguridad editorial, la copia resultante se inicializa en estado BORRADOR.
    """
    pregunta = obtener_pregunta(db, pregunta_id)
    return pregunta_repository.duplicar(db, pregunta, estado_duplicada=EstadoPregunta.BORRADOR)


def listar_preguntas(
    db: Session,
    page: int = 1,
    page_size: int = 6,
    buscar: Optional[str] = None,
    categoria_id: Optional[int] = None,
    estado: Optional[EstadoPregunta] = None,
) -> PreguntaListadoResponse:
    """Devuelve el listado paginado de preguntas filtradas para el panel de administración."""
    if page < 1:
        page = 1

    items, total = pregunta_repository.listar_paginado(
        db=db,
        page=page,
        page_size=page_size,
        buscar=buscar,
        categoria_id=categoria_id,
        estado=estado,
    )

    total_paginas = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return PreguntaListadoResponse(
        items=[PreguntaAdminResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        total_paginas=total_paginas,
    )
