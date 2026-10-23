"""Funciones de acceso a datos para la entidad Pregunta (Tareas 2.1.2, 2.1.3 y 5.1.1)."""

from datetime import datetime, timezone
import random
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.excepciones import ExcepcionValidacion
from app.models.enumeraciones import EstadoPregunta
from app.models.pregunta import Pregunta


def listar_preguntas_por_categoria(db: Session, categoria_id: int) -> list[Pregunta]:
    """
    Devuelve todas las preguntas activas y no eliminadas de una categoría (Módulo 2).
    Ajuste 5.1.1: excluye preguntas en estado BORRADOR o con eliminada_en seteado.
    """
    return (
        db.query(Pregunta)
        .filter(
            Pregunta.categoria_id == categoria_id,
            Pregunta.estado == EstadoPregunta.ACTIVA,
            Pregunta.eliminada_en.is_(None),
        )
        .all()
    )


def obtener_preguntas_aleatorias_sin_repeticion(
    db: Session, categoria_id: int, cantidad: int = 10
) -> list[Pregunta]:
    """
    Selecciona `cantidad` preguntas al azar de una categoría, sin repetir ninguna
    (Tarea 2.1.3). Si la categoría no tiene al menos `cantidad` preguntas activas cargadas,
    lanza una excepción en vez de iniciar una partida incompleta.
    """
    preguntas = listar_preguntas_por_categoria(db, categoria_id)
    if len(preguntas) < cantidad:
        raise ExcepcionValidacion(
            mensaje="La categoría seleccionada no cuenta con suficientes preguntas para iniciar una partida"
        )
    return random.sample(preguntas, cantidad)


def crear(db: Session, pregunta: Pregunta) -> Pregunta:
    """Persiste una nueva pregunta en la base de datos."""
    db.add(pregunta)
    db.commit()
    db.refresh(pregunta)
    return pregunta


def obtener_por_id(
    db: Session, pregunta_id: int, incluir_eliminadas: bool = False
) -> Optional[Pregunta]:
    """
    Busca una pregunta por su ID con su categoría cargada.
    Por defecto no retorna preguntas marcadas con soft-delete.
    """
    query = (
        db.query(Pregunta)
        .options(joinedload(Pregunta.categoria))
        .filter(Pregunta.id == pregunta_id)
    )
    if not incluir_eliminadas:
        query = query.filter(Pregunta.eliminada_en.is_(None))
    return query.first()


def actualizar(db: Session, pregunta: Pregunta) -> Pregunta:
    """Actualiza y refresca los cambios de una pregunta."""
    db.commit()
    db.refresh(pregunta)
    return pregunta


def marcar_eliminada(db: Session, pregunta: Pregunta) -> Pregunta:
    """
    Aplica soft-delete registrando la fecha/hora actual en eliminada_en.
    Conserva la fila física para asegurar integridad referencial en partidas pasadas.
    """
    pregunta.eliminada_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pregunta)
    return pregunta


def duplicar(
    db: Session,
    pregunta: Pregunta,
    estado_duplicada: EstadoPregunta = EstadoPregunta.BORRADOR,
) -> Pregunta:
    """
    Clona una pregunta existente. Por diseño de seguridad editorial,
    la copia queda en estado BORRADOR para que el administrador la revise antes de activarla.
    """
    copia = Pregunta(
        enunciado=pregunta.enunciado,
        categoria_id=pregunta.categoria_id,
        opcion_a=pregunta.opcion_a,
        opcion_b=pregunta.opcion_b,
        opcion_c=pregunta.opcion_c,
        opcion_d=pregunta.opcion_d,
        respuesta_correcta=pregunta.respuesta_correcta,
        dificultad=pregunta.dificultad,
        estado=estado_duplicada,
        eliminada_en=None,
    )
    db.add(copia)
    db.commit()
    db.refresh(copia)
    return copia


def listar_paginado(
    db: Session,
    page: int = 1,
    page_size: int = 6,
    buscar: Optional[str] = None,
    categoria_id: Optional[int] = None,
    estado: Optional[EstadoPregunta] = None,
) -> tuple[list[Pregunta], int]:
    """
    Devuelve la lista paginada de preguntas no eliminadas aplicando filtros combinables.
    Retorna una tupla (items, total_count).
    """
    query = db.query(Pregunta).filter(Pregunta.eliminada_en.is_(None))

    if buscar and buscar.strip():
        termino = f"%{buscar.strip()}%"
        query = query.filter(Pregunta.enunciado.ilike(termino))

    if categoria_id is not None:
        query = query.filter(Pregunta.categoria_id == categoria_id)

    if estado is not None:
        query = query.filter(Pregunta.estado == estado)

    total = query.count()
    offset = max(0, (page - 1) * page_size)
    items = (
        query.options(joinedload(Pregunta.categoria))
        .order_by(Pregunta.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return items, total