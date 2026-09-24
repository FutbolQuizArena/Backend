"""Funciones de acceso a datos para la entidad Pregunta (Tarea 2.1.2 / 2.1.3)."""

import random

from sqlalchemy.orm import Session

from app.models.pregunta import Pregunta


def listar_preguntas_por_categoria(db: Session, categoria_id: int) -> list[Pregunta]:
    """Devuelve todas las preguntas de una categoría."""
    return db.query(Pregunta).filter(Pregunta.categoria_id == categoria_id).all()


def obtener_preguntas_aleatorias_sin_repeticion(
    db: Session, categoria_id: int, cantidad: int = 10
) -> list[Pregunta]:
    """
    Selecciona `cantidad` preguntas al azar de una categoría, sin repetir ninguna
    (Tarea 2.1.3). Si la categoría tiene menos preguntas que `cantidad`, devuelve
    todas las que haya.
    """
    preguntas = listar_preguntas_por_categoria(db, categoria_id)
    cantidad_final = min(cantidad, len(preguntas))
    return random.sample(preguntas, cantidad_final)