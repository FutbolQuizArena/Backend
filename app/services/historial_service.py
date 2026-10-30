"""Lógica de negocio del historial personal del jugador (Tareas 4.1.3 a 4.1.5, RF-15 y RF-17)."""

from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.repositories import duelo_repository, partida_repository, torneo_repository
from app.schemas.historial_schema import (
    HistorialDueloItem,
    HistorialDuelosResponse,
    HistorialPartidaIndividualItem,
    HistorialPartidasIndividualesResponse,
    HistorialTorneoItem,
    HistorialTorneosResponse,
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


def _armar_item_torneo(
    participacion: ParticipanteTorneo,
    ronda_alcanzada: int | None,
    es_campeon: bool,
) -> HistorialTorneoItem:
    """Convierte una participación en un item del historial de torneos."""
    torneo = participacion.torneo
    return HistorialTorneoItem(
        torneo_id=torneo.id,
        nombre=torneo.nombre,
        estado=torneo.estado,
        ronda_alcanzada=ronda_alcanzada,
        es_campeon=es_campeon,
        fecha_creacion=torneo.fecha_creacion,
    )


def obtener_historial_torneos(db: Session, usuario_actual: Usuario) -> HistorialTorneosResponse:
    """Arma el historial de torneos del usuario con la ronda alcanzada en cada uno
    (Tarea 4.1.5, RF-15 y RF-17).

    La ronda alcanzada es la última ronda en la que el jugador tuvo un cruce. Es campeón
    quien ganó el cruce de la última ronda de un torneo ya finalizado. Los datos se leen
    con tres consultas en total, sin importar cuántos torneos haya jugado.
    """
    participaciones = torneo_repository.listar_participaciones_de_usuario(
        db, usuario_id=usuario_actual.id
    )
    ids_participaciones = {participacion.id for participacion in participaciones}
    cruces = torneo_repository.obtener_cruces_de_participantes(db, list(ids_participaciones))
    ultima_ronda_por_torneo = torneo_repository.obtener_ultima_ronda_por_torneo(
        db, [participacion.torneo_id for participacion in participaciones]
    )

    ronda_por_participacion: dict[int, int] = {}
    finales_ganadas: set[int] = set()
    for cruce in cruces:
        for participacion_id in (cruce.jugador_a_id, cruce.jugador_b_id):
            if participacion_id in ids_participaciones:
                ronda_por_participacion[participacion_id] = max(
                    ronda_por_participacion.get(participacion_id, 0), cruce.ronda
                )
        es_ultima_ronda = cruce.ronda == ultima_ronda_por_torneo.get(cruce.torneo_id)
        if es_ultima_ronda and cruce.ganador_id in ids_participaciones:
            finales_ganadas.add(cruce.ganador_id)

    items = [
        _armar_item_torneo(
            participacion,
            ronda_alcanzada=ronda_por_participacion.get(participacion.id),
            es_campeon=(
                participacion.torneo.estado == EstadoTorneo.FINALIZADO
                and participacion.id in finales_ganadas
            ),
        )
        for participacion in participaciones
    ]
    return HistorialTorneosResponse(torneos=items, total=len(items))