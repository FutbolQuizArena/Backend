"""Funciones de acceso a datos para la entidad Categoria (Tarea 2.1.2 y 5.1.2)."""

import secrets
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta
from app.models.pregunta import Pregunta
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA


def listar_categorias(db: Session) -> list[Categoria]:
    """Devuelve todas las categorías disponibles."""
    return db.query(Categoria).all()


def listar_categorias_activas(db: Session) -> list[Categoria]:
    """Lista pública: solo categorías que permiten completar una partida."""
    return consulta_categorias_jugables(db).order_by(Categoria.id.asc()).all()


def consulta_categorias_jugables(db: Session, cantidad: int = CANTIDAD_PREGUNTAS_POR_PARTIDA):
    """Criterio compartido por ruleta, partidas, duelos y protección del banco."""
    return (
        db.query(Categoria).join(Pregunta, Pregunta.categoria_id == Categoria.id)
        .filter(Categoria.estado == EstadoCategoria.ACTIVA,
                Pregunta.estado == EstadoPregunta.ACTIVA, Pregunta.eliminada_en.is_(None))
        .group_by(Categoria.id).having(func.count(Pregunta.id) >= cantidad)
    )


def hay_categoria_jugable(db: Session) -> bool:
    return db.query(consulta_categorias_jugables(db).exists()).scalar()


def obtener_categoria_jugable_por_id(db: Session, categoria_id: int) -> Categoria | None:
    return consulta_categorias_jugables(db).filter(Categoria.id == categoria_id).first()


def obtener_categoria_por_id(db: Session, categoria_id: int) -> Categoria | None:
    """Busca una categoría por su ID."""
    return db.query(Categoria).filter(Categoria.id == categoria_id).populate_existing().first()


def obtener_categoria_por_nombre(db: Session, nombre: str) -> Categoria | None:
    """Busca una categoría por su nombre exacto (insensible a mayúsculas y minúsculas)."""
    return (
        db.query(Categoria)
        .filter(func.lower(Categoria.nombre) == nombre.strip().lower())
        .first()
    )


def obtener_categoria_aleatoria(db: Session) -> Categoria | None:
    """Selecciona únicamente categorías con el mínimo de preguntas jugables."""
    return obtener_categoria_jugable(db, CANTIDAD_PREGUNTAS_POR_PARTIDA)


def obtener_categoria_jugable(db: Session, cantidad: int) -> Categoria | None:
    """Elige solo categorías activas con suficientes preguntas activas sin eliminar."""
    categorias = consulta_categorias_jugables(db, cantidad).all()
    return secrets.choice(categorias) if categorias else None


def crear_categoria(
    db: Session,
    nombre: str,
    estado: EstadoCategoria = EstadoCategoria.ACTIVA,
    confirmar: bool = True,
) -> Categoria:
    """Crea y persiste una nueva categoría en la base de datos."""
    categoria = Categoria(nombre=nombre.strip(), estado=estado)
    db.add(categoria)
    if confirmar:
        db.commit()
    else:
        db.flush()
    db.refresh(categoria)
    return categoria


def listar_categorias_admin(
    db: Session,
    buscar: Optional[str] = None,
    estado: Optional[EstadoCategoria] = None,
) -> list[tuple[Categoria, int]]:
    """Devuelve el listado de categorías para administración junto con la cantidad de preguntas vinculadas.
    
    Excluye preguntas eliminadas lógicamente en el cómputo de preguntas activas en el banco.
    """
    conteo_subquery = (
        db.query(func.count(Pregunta.id))
        .filter(
            Pregunta.categoria_id == Categoria.id,
            Pregunta.eliminada_en.is_(None),
        )
        .correlate(Categoria)
        .scalar_subquery()
    )

    query = db.query(Categoria, conteo_subquery.label("preguntas_count"))

    if buscar:
        termino = f"%{buscar.strip()}%"
        query = query.filter(Categoria.nombre.ilike(termino))

    if estado:
        query = query.filter(Categoria.estado == estado)

    query = query.order_by(Categoria.id.asc())
    resultados = query.all()

    return [(cat, count or 0) for cat, count in resultados]


def contar_preguntas_asociadas(db: Session, categoria_id: int) -> int:
    """Cuenta la cantidad de preguntas no eliminadas vinculadas a la categoría."""
    return (
        db.query(func.count(Pregunta.id))
        .filter(
            Pregunta.categoria_id == categoria_id,
            Pregunta.eliminada_en.is_(None),
        )
        .scalar()
        or 0
    )


def tiene_preguntas_asociadas(db: Session, categoria_id: int) -> bool:
    """Verifica si existen preguntas (activas o eliminadas) vinculadas a la categoría en base de datos.
    
    Se utiliza para evitar violaciones de clave foránea al intentar eliminar una categoría.
    """
    return db.query(Pregunta.id).filter(Pregunta.categoria_id == categoria_id).first() is not None


def actualizar_categoria(
    db: Session,
    categoria: Categoria,
    nombre: Optional[str] = None,
    estado: Optional[EstadoCategoria] = None,
    confirmar: bool = True,
) -> Categoria:
    """Actualiza los campos de una categoría existente."""
    if nombre is not None:
        categoria.nombre = nombre.strip()
    if estado is not None:
        categoria.estado = estado
    if confirmar:
        db.commit()
    else:
        db.flush()
    db.refresh(categoria)
    return categoria


def eliminar_categoria(db: Session, categoria: Categoria, confirmar: bool = True) -> None:
    """Elimina físicamente una categoría de la base de datos."""
    db.delete(categoria)
    if confirmar:
        db.commit()
    else:
        db.flush()
