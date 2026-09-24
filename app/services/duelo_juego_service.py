"""Registro de respuestas y cálculo del resultado final de un duelo (Tarea 2.1.10)."""

from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionNoAutorizado, ExcepcionRecursoNoEncontrado
from app.core.excepciones_partida import PartidaYaFinalizadaError, PreguntaYaRespondidaError
from app.models.enumeraciones_partida import EstadoPartida
from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.repositories import duelo_repository, partida_repository
from app.services.puntaje_service import calcular_puntaje


def _numero_de_jugador(duelo: PartidaDuelo, usuario_id: int) -> int:
    """Determina si el usuario es el jugador 1 o el jugador 2 del duelo."""
    if duelo.jugador1_id == usuario_id:
        return 1
    if duelo.jugador2_id == usuario_id:
        return 2
    raise ExcepcionNoAutorizado(mensaje="No formás parte de este duelo")


def responder_pregunta_duelo(
    db: Session,
    pregunta_partida_id: int,
    opcion_seleccionada: str | None,
    tiempo_respuesta_segundos: int,
    usuario_actual: Usuario,
):
    """Registra la respuesta de un jugador a una de sus preguntas dentro de un duelo."""
    pregunta_partida = partida_repository.obtener_pregunta_partida_por_id(db, pregunta_partida_id)
    if pregunta_partida is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró la pregunta del duelo")

    duelo = duelo_repository.obtener_duelo_por_id(db, pregunta_partida.partida_id)
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró el duelo")

    numero_jugador = _numero_de_jugador(duelo, usuario_actual.id)
    if pregunta_partida.numero_jugador != numero_jugador:
        raise ExcepcionNoAutorizado(mensaje="Esta pregunta no te pertenece en este duelo")

    if duelo.estado == EstadoPartida.FINALIZADA:
        raise PartidaYaFinalizadaError()

    if pregunta_partida.esta_respondida:
        raise PreguntaYaRespondidaError()

    es_correcta = pregunta_partida.pregunta.es_correcta(opcion_seleccionada)
    puntaje = calcular_puntaje(
        es_correcta=es_correcta, tiempo_respuesta_segundos=tiempo_respuesta_segundos
    )
    pregunta_partida.registrar_respuesta(
        opcion=opcion_seleccionada,
        tiempo_segundos=tiempo_respuesta_segundos,
        es_correcta=es_correcta,
        puntaje=puntaje,
    )
    return partida_repository.guardar_respuesta(db, pregunta_partida)


def finalizar_duelo_si_corresponde(db: Session, duelo_id: int) -> PartidaDuelo:
    """
    Si ambos jugadores respondieron todas sus preguntas, calcula los puntajes finales,
    determina el ganador, marca el duelo como FINALIZADA y suma puntaje a ambos usuarios.
    Si todavía falta alguna respuesta, no hace nada y devuelve el duelo sin cambios.
    """
    duelo = duelo_repository.obtener_duelo_por_id(db, duelo_id)
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró el duelo")

    if duelo.estado == EstadoPartida.FINALIZADA:
        return duelo

    preguntas_jugador1 = duelo.preguntas_de_jugador(1)
    preguntas_jugador2 = duelo.preguntas_de_jugador(2)

    todas_respondidas = all(p.esta_respondida for p in preguntas_jugador1) and all(
        p.esta_respondida for p in preguntas_jugador2
    )
    if not todas_respondidas:
        return duelo

    duelo.puntaje_jugador1 = sum(p.puntaje_obtenido for p in preguntas_jugador1)
    duelo.puntaje_jugador2 = sum(p.puntaje_obtenido for p in preguntas_jugador2)
    duelo.determinar_ganador()
    duelo.estado = EstadoPartida.FINALIZADA

    db.add(duelo)
    db.commit()
    db.refresh(duelo)

    partida_repository.sumar_puntaje_a_usuario(
        db=db, usuario_id=duelo.jugador1_id, puntos=duelo.puntaje_jugador1
    )
    if duelo.jugador2_id is not None:
        partida_repository.sumar_puntaje_a_usuario(
            db=db, usuario_id=duelo.jugador2_id, puntos=duelo.puntaje_jugador2
        )

    return duelo