"""Transacción compartida para conservar al menos una categoría jugable."""

from functools import wraps

from sqlalchemy import text

from app.core.excepciones import ExcepcionBase
from app.repositories import categoria_repository

MENSAJE_ULTIMA_CATEGORIA = (
    "Esta acción dejaría al juego sin categorías con preguntas activas suficientes. "
    "Primero habilitá otra categoría con preguntas."
)


def proteger_disponibilidad(operacion):
    """Serializa escritores antes de leer, valida el resultado y confirma una vez.

    Las operaciones decoradas y sus repositorios no deben hacer commits internos.
    El bloqueo transaccional de PostgreSQL también funciona con el banco vacío y
    entre workers; un bloqueo solo de las filas existentes no cubriría ese caso.
    """
    @wraps(operacion)
    def protegida(db, *args, **kwargs):
        try:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(20261125, 2)"))
            habia_jugable = categoria_repository.hay_categoria_jugable(db)
            resultado = operacion(db, *args, **kwargs)
            db.flush()
            if habia_jugable and not categoria_repository.hay_categoria_jugable(db):
                raise ExcepcionBase(codigo="ULTIMA_CATEGORIA_JUGABLE",
                                    mensaje=MENSAJE_ULTIMA_CATEGORIA, codigo_estado=409)
            db.commit()
            return resultado
        except Exception:
            db.rollback()
            raise
    return protegida
