"""Funciones de acceso a datos para Partida individual y sus preguntas (Tarea 2.1.6)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enumeraciones_partida import EstadoPartida, TipoPartida
from app.models.partida import PartidaIndividual, PreguntaPartida
from app.models.usuario import Usuario


def crear_partida_individual(db: Session, jugador_id: int, categoria_id: int) -> PartidaIndividual:
    """Crea una partida individual nueva, en curso, para un jugador y categoría."""
    partida = PartidaIndividual(
        tipo=TipoPartida.INDIVIDUAL,
        categoria_id=categoria_id,
        estado=EstadoPartida.EN_CURSO,
        jugador_id=jugador_id,
        puntaje_final=0,
    )
    db.add(partida)
    db.commit()
    db.refresh(partida)
    return partida


def obtener_partida_individual_por_id(db: Session, partida_id: int) -> PartidaIndividual | None:
    """Busca una partida individual por su ID."""
    return db.query(PartidaIndividual).filter(PartidaIndividual.id == partida_id).first()


def agregar_preguntas_a_partida(
    db: Session, partida_id: int, pregunta_ids: list[int], numero_jugador: int = 1
) -> list[PreguntaPartida]:
    """Crea las filas PreguntaPartida asociadas a una partida, en el orden dado."""
    preguntas_partida = []
    for orden, pregunta_id in enumerate(pregunta_ids, start=1):
        pregunta_partida = PreguntaPartida(
            partida_id=partida_id,
            pregunta_id=pregunta_id,
            orden=orden,
            numero_jugador=numero_jugador,
        )
        db.add(pregunta_partida)
        preguntas_partida.append(pregunta_partida)
    db.commit()
    return preguntas_partida


def obtener_pregunta_partida_por_id(db: Session, pregunta_partida_id: int) -> PreguntaPartida | None:
    """Busca una fila PreguntaPartida (una pregunta asignada dentro de una partida) por su ID."""
    return db.query(PreguntaPartida).filter(PreguntaPartida.id == pregunta_partida_id).first()


def guardar_respuesta(db: Session, pregunta_partida: PreguntaPartida) -> PreguntaPartida:
    """Persiste los cambios hechos sobre una PreguntaPartida (después de registrar_respuesta)."""
    db.add(pregunta_partida)
    db.commit()
    db.refresh(pregunta_partida)
    return pregunta_partida


def finalizar_partida_individual(
    db: Session, partida: PartidaIndividual, puntaje_final: int
) -> PartidaIndividual:
    """Marca la partida como finalizada y guarda su puntaje total."""
    partida.estado = EstadoPartida.FINALIZADA
    partida.fecha_fin = datetime.now(timezone.utc)
    partida.puntaje_final = puntaje_final
    db.add(partida)
    db.commit()
    db.refresh(partida)
    return partida


def sumar_puntaje_a_usuario(db: Session, usuario_id: int, puntos: int) -> Usuario | None:
    """Suma puntos al puntaje_total acumulado del usuario."""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        return None
    usuario.puntaje_total = (usuario.puntaje_total or 0) + puntos
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario