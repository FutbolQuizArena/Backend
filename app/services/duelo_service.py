"""Lógica de negocio y emparejamiento para Duelos (online y local)."""

from sqlalchemy.orm import Session

from app.core.excepciones import (
    ExcepcionNoAutorizado,
    ExcepcionRecursoNoEncontrado,
    ExcepcionValidacion,
    PartidaYaFinalizadaError,
    PreguntaYaRespondidaError,
)
from app.models.enumeraciones import EstadoPartida, ModalidadDuelo
from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.repositories import (
    categoria_repository,
    duelo_repository,
    partida_repository,
    pregunta_repository,
)
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA
from app.services.puntaje_service import calcular_puntaje


def _numero_de_jugador(duelo: PartidaDuelo, usuario_id: int) -> int:
    """Determina si el usuario es el jugador 1 o el jugador 2 del duelo."""
    if duelo.jugador1_id == usuario_id:
        return 1
    if duelo.jugador2_id == usuario_id:
        return 2
    raise ExcepcionNoAutorizado(mensaje="No formás parte de este duelo")


def buscar_o_crear_duelo_online(db: Session, usuario_actual: Usuario) -> PartidaDuelo:
    """Empareja al jugador con un duelo en línea (RF-05):

    - Si hay un duelo esperando rival (creado por otro jugador), se une a ese duelo,
      queda EN_CURSO y comparte las mismas 10 preguntas que el jugador 1.
    - Si no hay ninguno esperando, crea un duelo nuevo con categoría y preguntas
      al azar, y queda PENDIENTE_RIVAL hasta que otro jugador se sume.
    """
    duelo_pendiente = duelo_repository.buscar_duelo_pendiente_de_rival(
        db=db, jugador_id=usuario_actual.id
    )

    if duelo_pendiente is not None:
        duelo_pendiente.unirse_como_rival(jugador2_id=usuario_actual.id)
        duelo_pendiente.estado = EstadoPartida.EN_CURSO
        db.add(duelo_pendiente)
        db.commit()
        db.refresh(duelo_pendiente)

        preguntas_jugador1 = duelo_pendiente.preguntas_de_jugador(1)
        partida_repository.agregar_preguntas_a_partida(
            db=db,
            partida_id=duelo_pendiente.id,
            pregunta_ids=[pp.pregunta_id for pp in preguntas_jugador1],
            numero_jugador=2,
        )
        db.refresh(duelo_pendiente)
        return duelo_pendiente

    categoria = categoria_repository.obtener_categoria_aleatoria(db)
    if categoria is None:
        raise ExcepcionValidacion(mensaje="No hay categorías disponibles para jugar")

    preguntas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
        db=db, categoria_id=categoria.id, cantidad=CANTIDAD_PREGUNTAS_POR_PARTIDA
    )
    if not preguntas:
        raise ExcepcionValidacion(mensaje="La categoría seleccionada no tiene preguntas cargadas")

    duelo_nuevo = duelo_repository.crear_duelo(
        db=db,
        jugador1_id=usuario_actual.id,
        categoria_id=categoria.id,
        modalidad=ModalidadDuelo.ONLINE,
    )
    partida_repository.agregar_preguntas_a_partida(
        db=db,
        partida_id=duelo_nuevo.id,
        pregunta_ids=[pregunta.id for pregunta in preguntas],
        numero_jugador=1,
    )
    db.refresh(duelo_nuevo)
    return duelo_nuevo


def iniciar_duelo_local(db: Session, usuario_actual: Usuario, nombre_invitado: str) -> PartidaDuelo:
    """Inicia un duelo LOCAL (Tarea 2.1.8/2.3.4): ambos jugadores usan el mismo dispositivo

    por turnos, así que arranca directamente EN_CURSO, con las mismas 10 preguntas
    asignadas a ambos jugadores (jugador 2 es un invitado sin cuenta).
    """
    categoria = categoria_repository.obtener_categoria_aleatoria(db)
    if categoria is None:
        raise ExcepcionValidacion(mensaje="No hay categorías disponibles para jugar")

    preguntas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
        db=db, categoria_id=categoria.id, cantidad=CANTIDAD_PREGUNTAS_POR_PARTIDA
    )
    if not preguntas:
        raise ExcepcionValidacion(mensaje="La categoría seleccionada no tiene preguntas cargadas")

    duelo = duelo_repository.crear_duelo(
        db=db,
        jugador1_id=usuario_actual.id,
        categoria_id=categoria.id,
        modalidad=ModalidadDuelo.LOCAL,
    )
    duelo.nombre_invitado = nombre_invitado
    db.add(duelo)
    db.commit()

    pregunta_ids = [pregunta.id for pregunta in preguntas]
    partida_repository.agregar_preguntas_a_partida(
        db=db, partida_id=duelo.id, pregunta_ids=pregunta_ids, numero_jugador=1
    )
    partida_repository.agregar_preguntas_a_partida(
        db=db, partida_id=duelo.id, pregunta_ids=pregunta_ids, numero_jugador=2
    )
    db.refresh(duelo)
    return duelo


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
    """Si ambos jugadores respondieron todas sus preguntas, calcula los puntajes finales,

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