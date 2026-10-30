"""Funciones de acceso a datos para PartidaDuelo (Tarea 2.1.8)."""

from datetime import datetime, timedelta

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, joinedload

from app.models.enumeraciones import EstadoPartida, ModalidadDuelo, TipoPartida
from app.models.partida_duelo import PartidaDuelo


def bloquear_cola_online(db: Session) -> None:
    """Serializa el emparejamiento incluso cuando no hay filas para bloquear.

    PostgreSQL comparte este bloqueo entre procesos y lo libera al confirmar o
    revertir la transacción. SQLite se usa únicamente en las pruebas locales.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(20261029, 1)"))


def cerrar_busquedas_vencidas(db: Session, ahora: datetime, espera_segundos: int) -> None:
    """Cierra esperas antiguas en la transacción que ya tiene bloqueada la cola."""
    duelos = (
        db.query(PartidaDuelo)
        .filter(
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            PartidaDuelo.estado == EstadoPartida.PENDIENTE_RIVAL,
            PartidaDuelo.jugador2_id.is_(None),
            PartidaDuelo.fecha_inicio <= ahora - timedelta(seconds=espera_segundos),
        )
        .populate_existing().with_for_update().all()
    )
    for duelo in duelos:
        duelo.estado = EstadoPartida.FINALIZADA
        duelo.fecha_fin = ahora
    db.flush()


def crear_duelo(
    db: Session, jugador1_id: int, categoria_id: int, modalidad: ModalidadDuelo,
    confirmar: bool = True,
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
    if confirmar:
        db.commit()
        db.refresh(duelo)
    else:
        db.flush()
    return duelo


def obtener_duelo_por_id(db: Session, duelo_id: int) -> PartidaDuelo | None:
    """Busca un duelo por su ID."""
    return db.query(PartidaDuelo).filter(PartidaDuelo.id == duelo_id).first()


def buscar_duelo_pendiente_de_rival(db: Session, jugador_id: int) -> PartidaDuelo | None:
    """
    Busca un duelo ONLINE que esté esperando rival (Tarea 2.1.9), excluyendo los
    duelos creados por el propio jugador que busca (no puede emparejarse consigo mismo).
    Devuelve el más antiguo esperando, para emparejar en orden de llegada.

    Usa with_for_update() para bloquear la fila encontrada: así, si dos jugadores
    piden emparejarse casi al mismo tiempo, el segundo pedido espera a que el primero
    termine (commit o rollback) antes de leer el estado real del duelo, evitando que
    ambos se unan al mismo duelo pendiente a la vez (Tarea de corrección: race condition).
    """
    return (
        db.query(PartidaDuelo)
        .filter(
            PartidaDuelo.estado == EstadoPartida.PENDIENTE_RIVAL,
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            PartidaDuelo.jugador1_id != jugador_id,
        )
        .order_by(PartidaDuelo.fecha_inicio.asc())
        .with_for_update()
        .first()
    )


def listar_finalizados_por_jugador(db: Session, jugador_id: int) -> list[PartidaDuelo]:
    """Devuelve los duelos jugados y finalizados de un jugador, del más reciente al más antiguo
    (Tarea 4.1.4).

    Solo cuenta un duelo que se llegó a disputar: uno local, o uno online con rival. Los duelos
    online que se cerraron sin que nadie se uniera no forman parte del historial. Si un duelo
    no guardó fecha_fin, se ordena por su fecha_inicio.
    """
    fecha_de_cierre = func.coalesce(PartidaDuelo.fecha_fin, PartidaDuelo.fecha_inicio)
    return (
        db.query(PartidaDuelo)
        .options(
            joinedload(PartidaDuelo.categoria),
            joinedload(PartidaDuelo.jugador1),
            joinedload(PartidaDuelo.jugador2),
        )
        .filter(
            PartidaDuelo.estado == EstadoPartida.FINALIZADA,
            or_(PartidaDuelo.jugador1_id == jugador_id, PartidaDuelo.jugador2_id == jugador_id),
            or_(
                PartidaDuelo.modalidad == ModalidadDuelo.LOCAL.value,
                PartidaDuelo.jugador2_id.is_not(None),
            ),
        )
        .order_by(fecha_de_cierre.desc(), PartidaDuelo.id.desc())
        .all()
    )
