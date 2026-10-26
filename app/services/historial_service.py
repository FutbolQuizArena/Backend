"""Lógica de negocio del historial personal del jugador (Tareas 4.1.3 a 4.1.5, RF-15 y RF-17)."""

from sqlalchemy.orm import Session

from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.repositories import duelo_repository, partida_repository
from app.schemas.historial_schema import (
    HistorialDueloItem,
    HistorialDuelosResponse,
    HistorialPartidaIndividualItem,
    HistorialPartidasIndividualesResponse,
    ResultadoDuelo,
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


def _resultado_para_jugador(duelo: PartidaDuelo, numero_jugador: int) -> ResultadoDuelo:
    """Resultado del duelo visto desde el jugador indicado (1 o 2)."""
    if duelo.numero_ganador is None:
        return ResultadoDuelo.EMPATE
    if duelo.numero_ganador == numero_jugador:
        return ResultadoDuelo.VICTORIA
    return ResultadoDuelo.DERROTA


def _armar_item_duelo(duelo: PartidaDuelo, usuario_id: int) -> HistorialDueloItem:
    """Convierte un duelo en un item del historial, visto desde el lado de `usuario_id`."""
    es_jugador1 = duelo.jugador1_id == usuario_id
    numero_jugador = 1 if es_jugador1 else 2
    return HistorialDueloItem(
        duelo_id=duelo.id,
        modalidad=duelo.modalidad,
        categoria_nombre=duelo.categoria_nombre,
        rival_nombre=duelo.jugador2_nombre if es_jugador1 else duelo.jugador1_nombre,
        puntaje_propio=duelo.puntaje_jugador1 if es_jugador1 else duelo.puntaje_jugador2,
        puntaje_rival=duelo.puntaje_jugador2 if es_jugador1 else duelo.puntaje_jugador1,
        resultado=_resultado_para_jugador(duelo, numero_jugador),
        fecha_fin=duelo.fecha_fin or duelo.fecha_inicio,
    )


def obtener_historial_duelos(db: Session, usuario_actual: Usuario) -> HistorialDuelosResponse:
    """Arma el historial de duelos finalizados del usuario, visto desde su lado (Tarea 4.1.4).

    Incluye duelos online y locales. Cada jugador solo ve los duelos en los que participó.
    """
    duelos = duelo_repository.listar_finalizados_por_jugador(db, jugador_id=usuario_actual.id)
    items = [_armar_item_duelo(duelo, usuario_actual.id) for duelo in duelos]
    return HistorialDuelosResponse(duelos=items, total=len(items))