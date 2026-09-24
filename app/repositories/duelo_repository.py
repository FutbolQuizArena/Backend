"""Funciones de acceso a datos para PartidaDuelo (Tarea 2.1.8)."""

from sqlalchemy.orm import Session

from app.models.enumeraciones_partida import EstadoPartida, ModalidadDuelo, TipoPartida
from app.models.partida_duelo import PartidaDuelo


def crear_duelo(
    db: Session, jugador1_id: int, categoria_id: int, modalidad: ModalidadDuelo
) -> PartidaDuelo:
    """
    Crea un duelo nuevo.
    - Si es ONLINE: queda PENDIENTE_RIVAL hasta que otro jugador se una (Tarea 2.1.9).
    - Si es LOCAL: arranca directamente EN_CURSO (los dos juegan en el mismo dispositivo).
    """
    esta_esperando_rival = modalidad == ModalidadDuelo.ONLINE
    duelo = PartidaDuelo(
        tipo=TipoPartida.DUELO,
        categoria_id=categoria_id,
        estado=EstadoPartida.PENDIENTE_RIVAL if esta_esperando_rival else EstadoPartida.EN_CURSO,
        modalidad=modalidad.value,
        jugador1_id=jugador1_id,
    )
    db.add(duelo)
    db.commit()
    db.refresh(duelo)
    return duelo


def obtener_duelo_por_id(db: Session, duelo_id: int) -> PartidaDuelo | None:
    """Busca un duelo por su ID."""
    return db.query(PartidaDuelo).filter(PartidaDuelo.id == duelo_id).first()


def buscar_duelo_pendiente_de_rival(db: Session, jugador_id: int) -> PartidaDuelo | None:
    """
    Busca un duelo ONLINE que esté esperando rival (Tarea 2.1.9), excluyendo los
    duelos creados por el propio jugador que busca (no puede emparejarse consigo mismo).
    Devuelve el más antiguo esperando, para emparejar en orden de llegada.
    """
    return (
        db.query(PartidaDuelo)
        .filter(
            PartidaDuelo.estado == EstadoPartida.PENDIENTE_RIVAL,
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            PartidaDuelo.jugador1_id != jugador_id,
        )
        .order_by(PartidaDuelo.fecha_inicio.asc())
        .first()
    )