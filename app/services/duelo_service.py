"""Lógica de emparejamiento de duelos en línea (Tarea 2.1.9)."""

from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionValidacion
from app.models.enumeraciones_partida import ModalidadDuelo
from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.repositories import categoria_repository, duelo_repository, partida_repository, pregunta_repository
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA


def buscar_o_crear_duelo_online(db: Session, usuario_actual: Usuario) -> PartidaDuelo:
    """
    Empareja al jugador con un duelo en línea (RF-05):
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
        duelo_pendiente.estado = duelo_pendiente.estado.EN_CURSO
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