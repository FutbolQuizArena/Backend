"""Funciones de acceso a datos para la entidad Categoria (Tarea 2.1.2)."""

import random

from sqlalchemy.orm import Session

from app.models.categoria import Categoria


def listar_categorias(db: Session) -> list[Categoria]:
    """Devuelve todas las categorías disponibles."""
    return db.query(Categoria).all()


def obtener_categoria_por_id(db: Session, categoria_id: int) -> Categoria | None:
    """Busca una categoría por su ID."""
    return db.query(Categoria).filter(Categoria.id == categoria_id).first()


def obtener_categoria_aleatoria(db: Session) -> Categoria | None:
    """Selecciona una categoría al azar entre todas las disponibles."""
    categorias = listar_categorias(db)
    if not categorias:
        return None
    return random.choice(categorias)