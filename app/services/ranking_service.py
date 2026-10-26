"""Lógica de negocio del ranking general (Tarea 4.1.1, RF-11)."""

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories import usuario_repository

PUNTOS_CAMPEON_TORNEO = 1500


def acumular_puntaje(db: Session, usuario_id: int, puntos: int) -> Usuario | None:
    """
    Suma al puntaje acumulado de un usuario los puntos ganados al finalizar una partida
    individual, un duelo o un torneo (RF-11). El ranking general se ordena por ese puntaje.

    Es el único punto del sistema que modifica el puntaje acumulado: así todas las
    formas de ganar puntos se actualizan de la misma manera.
    - Si los puntos son 0 o negativos no se modifica nada: el puntaje acumulado nunca baja.
    - Si el usuario no existe retorna None.
    """
    if puntos <= 0:
        return usuario_repository.obtener_por_id(db, id=usuario_id)
    return usuario_repository.acumular_puntaje(db, usuario_id=usuario_id, puntos=puntos)