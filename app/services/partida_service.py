"""Lógica de negocio del flujo de partida individual (Tareas 2.1.4, 2.1.5, 2.1.6)."""

from app.core.excepciones import (
    ExcepcionRecursoNoEncontrado,
    ExcepcionValidacion,
    PartidaYaFinalizadaError,
    PreguntaYaRespondidaError,
)
from app.models.enumeraciones import EstadoPartida
from app.models.partida import PartidaIndividual
from app.models.usuario import Usuario
from app.repositories import categoria_repository, partida_repository, pregunta_repository
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA
from app.services.puntaje_service import calcular_puntaje
from sqlalchemy.orm import Session


def iniciar_partida_individual(db: Session, usuario_actual: Usuario) -> PartidaIndividual:
    """
    Inicia una partida individual nueva (RF-04):
    - Elige una categoría al azar (Tarea 2.1.2).
    - Selecciona 10 preguntas de esa categoría sin repetir (Tarea 2.1.3).
    - Crea la partida y le asigna esas preguntas.
    """
    categoria = categoria_repository.obtener_categoria_aleatoria(db)
    if categoria is None:
        raise ExcepcionValidacion(mensaje="No hay categorías disponibles para jugar")

    preguntas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
        db=db, categoria_id=categoria.id, cantidad=CANTIDAD_PREGUNTAS_POR_PARTIDA
    )
    if not preguntas:
        raise ExcepcionValidacion(mensaje="La categoría seleccionada no tiene preguntas cargadas")

    partida = partida_repository.crear_partida_individual(
        db=db, jugador_id=usuario_actual.id, categoria_id=categoria.id
    )
    partida_repository.agregar_preguntas_a_partida(
        db=db,
        partida_id=partida.id,
        pregunta_ids=[pregunta.id for pregunta in preguntas],
        numero_jugador=1,
    )
    db.refresh(partida)
    return partida


def responder_pregunta_partida(
    db: Session,
    pregunta_partida_id: int,
    opcion_seleccionada: str | None,
    tiempo_respuesta_segundos: int,
    usuario_actual: Usuario,
):
    """Registra la respuesta de un jugador a una pregunta de su partida (Tareas 2.1.4/2.1.5)."""
    pregunta_partida = partida_repository.obtener_pregunta_partida_por_id(db, pregunta_partida_id)
    if pregunta_partida is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró la pregunta de la partida")

    partida = partida_repository.obtener_partida_individual_por_id(db, pregunta_partida.partida_id)
    if partida is None or partida.jugador_id != usuario_actual.id:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró la partida")

    if partida.estado == EstadoPartida.FINALIZADA:
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


def finalizar_partida_individual(
    db: Session, partida_id: int, usuario_actual: Usuario
) -> PartidaIndividual:
    """
    Finaliza una partida individual y guarda su resultado (Tarea 2.1.6):
    suma el puntaje de todas las preguntas respondidas y lo guarda en la
    partida y en el puntaje acumulado del usuario.
    """
    partida = partida_repository.obtener_partida_individual_por_id(db, partida_id)
    if partida is None or partida.jugador_id != usuario_actual.id:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró la partida")

    if partida.estado == EstadoPartida.FINALIZADA:
        raise PartidaYaFinalizadaError()

    puntaje_total = sum(pregunta.puntaje_obtenido for pregunta in partida.preguntas)

    partida = partida_repository.finalizar_partida_individual(
        db=db, partida=partida, puntaje_final=puntaje_total
    )
    partida_repository.sumar_puntaje_a_usuario(
        db=db, usuario_id=usuario_actual.id, puntos=puntaje_total
    )
    return partida