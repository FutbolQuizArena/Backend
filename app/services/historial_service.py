"""Lógica de negocio del historial personal del jugador (Tareas 4.1.3 a 4.1.5, RF-15 y RF-17)."""

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories import partida_repository
from app.schemas.historial_schema import (
    HistorialPartidaIndividualItem,
    HistorialPartidasIndividualesResponse,
)


def obtener_historial_partidas_individuales(
    db: Session, usuario_actual: Usuario
) -> HistorialPartidasIndividualesResponse:
    """Arma el historial de partidas individuales finalizadas del usuario (Tarea 4.1.3, RF-17).

    Cada jugador solo puede ver sus propias partidas: la consulta se filtra siempre por
    el usuario autenticado, nunca por un identificador recibido desde afuera.
    """
    partidas = partida_repository.listar_individuales_finalizadas_por_jugador(
        db, jugador_id=usuario_actual.id
    )
    items = [
        HistorialPartidaIndividualItem(
            partida_id=partida.id,
            categoria_nombre=partida.categoria_nombre,
            puntaje_final=partida.puntaje_final,
            fecha_fin=partida.fecha_fin,
        )
        for partida in partidas
    ]
    return HistorialPartidasIndividualesResponse(partidas=items, total=len(items))