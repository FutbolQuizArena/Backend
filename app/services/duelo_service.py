"""Lógica de negocio y emparejamiento para Duelos (online y local)."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import (
    AccesoDenegadoError,
    ExcepcionBase,
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
from app.services import ranking_service
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA
from app.services.puntaje_service import calcular_puntaje


MENSAJE_DUELO_NO_ENCONTRADO = "No se encontró el duelo"
PRESENCIA_MAX_SEGUNDOS = 60
PRESENCIA_AVISO_SEGUNDOS = 15


def estado_presencia(duelo: PartidaDuelo, ahora: datetime | None = None) -> dict:
    """La ausencia se mide en el servidor; completar preguntas exime del abandono."""
    ahora = ahora or datetime.now(timezone.utc)
    datos = {"motivo_finalizacion": duelo.motivo_finalizacion}
    for numero in (1, 2):
        ultima = getattr(duelo, f"ultima_presencia_jugador{numero}")
        ultima = ultima or duelo.fecha_emparejamiento or duelo.fecha_inicio
        if ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        preguntas = duelo.preguntas_de_jugador(numero)
        completo = bool(preguntas) and all(p.esta_respondida for p in preguntas)
        segundos = max(0, (ahora - ultima).total_seconds())
        datos[f"jugador{numero}_completo"] = completo
        datos[f"jugador{numero}_ausente"] = (
            duelo.es_duelo_online and duelo.estado == EstadoPartida.EN_CURSO
            and not completo and segundos >= PRESENCIA_AVISO_SEGUNDOS
        )
        datos[f"jugador{numero}_vencido"] = not completo and segundos >= PRESENCIA_MAX_SEGUNDOS
    return datos


def registrar_presencia(db: Session, duelo_id: int, usuario: Usuario) -> PartidaDuelo:
    """Comprueba el plazo antes de renovar; un heartbeat tardío no revive al jugador."""
    try:
        duelo = duelo_repository.obtener_duelo_por_id(db, duelo_id)
        if duelo is None:
            raise ExcepcionRecursoNoEncontrado(mensaje=MENSAJE_DUELO_NO_ENCONTRADO)
        numero = _numero_de_jugador(duelo, usuario.id)
        if not duelo.es_duelo_online:
            raise ExcepcionValidacion(mensaje="La presencia solo corresponde a duelos online")
        duelo = _finalizar_duelo(db, duelo_id)
        if duelo.estado == EstadoPartida.EN_CURSO:
            presencia = estado_presencia(duelo)
            if not presencia[f"jugador{numero}_vencido"]:
                setattr(duelo, f"ultima_presencia_jugador{numero}", datetime.now(timezone.utc))
                duelo = _finalizar_duelo(db, duelo_id)
        db.commit()
        return duelo
    except Exception:
        db.rollback()
        raise


def cerrar_duelos_desconectados(db: Session) -> None:
    """Barrido independiente de los clientes; cada duelo se confirma por separado."""
    ids = [fila[0] for fila in db.query(PartidaDuelo.id).filter(
        PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
        PartidaDuelo.estado == EstadoPartida.EN_CURSO,
    ).all()]
    for duelo_id in ids:
        finalizar_duelo_si_corresponde(db, duelo_id)


def _numero_de_jugador(duelo: PartidaDuelo, usuario_id: int) -> int:
    """Determina si el usuario es el jugador 1 o el jugador 2 del duelo."""
    if duelo.jugador1_id == usuario_id:
        return 1
    if duelo.jugador2_id == usuario_id:
        return 2
    raise ExcepcionNoAutorizado(mensaje="No formás parte de este duelo")


def _buscar_duelos_pendientes_del_jugador(db: Session, jugador_id: int) -> list[PartidaDuelo]:
    """Busca todas las partidas de duelo ONLINE pendientes creadas por el jugador indicado,
    ordenadas de la más reciente a la más antigua.
    """
    fn = getattr(duelo_repository, "buscar_duelos_pendientes_del_jugador", None)
    if fn is not None:
        return fn(db, jugador_id)
    return (
        db.query(PartidaDuelo)
        .filter(
            PartidaDuelo.estado == EstadoPartida.PENDIENTE_RIVAL,
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            PartidaDuelo.jugador1_id == jugador_id,
        )
        .order_by(PartidaDuelo.fecha_inicio.desc())
        .all()
    )


def buscar_o_crear_duelo_online(db: Session, usuario_actual: Usuario) -> PartidaDuelo:
    """Empareja o crea una espera en una única transacción, sin búsquedas simultáneas."""
    from app.models.cruce import Cruce

    try:
        duelo_repository.bloquear_cola_online(db)
        duelo_repository.cerrar_busquedas_vencidas(
            db, datetime.now(timezone.utc), CONFIGURACION.DUELO_ESPERA_MAX_SEGUNDOS,
        )
        # Una pestaña nueva puede retomar su duelo sin depender del sessionStorage anterior.
        activo = db.query(PartidaDuelo).filter(
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            PartidaDuelo.estado == EstadoPartida.EN_CURSO,
            (PartidaDuelo.jugador1_id == usuario_actual.id) | (PartidaDuelo.jugador2_id == usuario_actual.id),
            # Los duelos de torneo se retoman desde su cuadro, no desde la cola libre.
            ~db.query(Cruce.id).filter(Cruce.duelo_id == PartidaDuelo.id).exists(),
        ).order_by(PartidaDuelo.id.desc()).first()
        if activo is not None:
            activo = _finalizar_duelo(db, activo.id)
            if activo.estado == EstadoPartida.EN_CURSO:
                db.commit()
                return activo
        duelo = _buscar_o_crear_duelo_online(db, usuario_actual)
        db.commit()
        db.refresh(duelo)
        return duelo
    except Exception:
        db.rollback()
        raise


def cancelar_busqueda_online(db: Session, duelo_id: int, usuario_actual: Usuario) -> PartidaDuelo:
    """Cancela una espera propia sin competir con un emparejamiento simultáneo."""
    try:
        duelo_repository.bloquear_cola_online(db)
        duelo = (
            db.query(PartidaDuelo).filter(PartidaDuelo.id == duelo_id)
            .populate_existing().with_for_update().first()
        )
        if duelo is None:
            raise ExcepcionRecursoNoEncontrado(mensaje=MENSAJE_DUELO_NO_ENCONTRADO)
        if duelo.jugador1_id != usuario_actual.id:
            raise AccesoDenegadoError(mensaje="Solo quien inició la búsqueda puede cancelarla")
        if duelo.modalidad != ModalidadDuelo.ONLINE.value:
            raise ExcepcionValidacion(mensaje="Solo se pueden cancelar búsquedas de duelos online")
        if duelo.jugador2_id is not None or duelo.estado == EstadoPartida.EN_CURSO:
            raise ExcepcionBase(
                codigo="BUSQUEDA_YA_EMPAREJADA",
                mensaje="Ya se encontró un rival. No se puede cancelar la búsqueda.",
                codigo_estado=409,
            )
        if duelo.estado == EstadoPartida.PENDIENTE_RIVAL:
            duelo.estado = EstadoPartida.FINALIZADA
            duelo.fecha_fin = datetime.now(timezone.utc)
        db.commit()
        db.refresh(duelo)
        return duelo
    except Exception:
        db.rollback()
        raise


def _buscar_o_crear_duelo_online(db: Session, usuario_actual: Usuario) -> PartidaDuelo:
    """Modifica la cola con el bloqueo adquirido y sin confirmar parcialmente."""
    duelo_pendiente = duelo_repository.buscar_duelo_pendiente_de_rival(
        db=db, jugador_id=usuario_actual.id
    )

    if duelo_pendiente is not None:
        duelo_pendiente.unirse_como_rival(jugador2_id=usuario_actual.id)
        duelo_pendiente.estado = EstadoPartida.EN_CURSO
        db.add(duelo_pendiente)
        db.flush()  # aplica los cambios dentro de la transacción, sin cerrarla todavía

        preguntas_jugador1 = duelo_pendiente.preguntas_de_jugador(1)
        partida_repository.agregar_preguntas_a_partida(
            db=db,
            partida_id=duelo_pendiente.id,
            pregunta_ids=[pp.pregunta_id for pp in preguntas_jugador1],
            numero_jugador=2,
            confirmar=False,
        )

        # Si el jugador que se une tenía algún duelo propio previo en PENDIENTE_RIVAL, lo finalizamos
        duelos_propios_rival = _buscar_duelos_pendientes_del_jugador(
            db=db, jugador_id=usuario_actual.id
        )
        for d in duelos_propios_rival:
            d.estado = EstadoPartida.FINALIZADA
            d.fecha_fin = datetime.now(timezone.utc)
            db.add(d)

        return duelo_pendiente

    # Si no hay rival esperando, verificar si el usuario actual ya posee un duelo pendiente esperando rival
    # para evitar duplicaciones por StrictMode de React o recargas del navegador
    duelos_propios = _buscar_duelos_pendientes_del_jugador(
        db=db, jugador_id=usuario_actual.id
    )
    if duelos_propios:
        duelo_activo = duelos_propios[0]
        if len(duelos_propios) > 1:
            for sobrante in duelos_propios[1:]:
                sobrante.estado = EstadoPartida.FINALIZADA
                sobrante.fecha_fin = datetime.now(timezone.utc)
                db.add(sobrante)
        return duelo_activo

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
        confirmar=False,
    )
    partida_repository.agregar_preguntas_a_partida(
        db=db,
        partida_id=duelo_nuevo.id,
        pregunta_ids=[pregunta.id for pregunta in preguntas],
        numero_jugador=1,
        confirmar=False,
    )
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
    """Guarda una respuesta y el avance del torneo en una única transacción."""
    try:
        pregunta = _responder_pregunta_duelo(
            db, pregunta_partida_id, opcion_seleccionada, tiempo_respuesta_segundos, usuario_actual,
        )
        db.commit()
        return pregunta
    except Exception:
        db.rollback()
        raise


def _responder_pregunta_duelo(
    db: Session, pregunta_partida_id: int, opcion_seleccionada: str | None,
    tiempo_respuesta_segundos: int, usuario_actual: Usuario,
):
    """Registra la respuesta de un jugador a una de sus preguntas dentro de un duelo."""
    from app.models.cruce import Cruce
    from app.repositories import torneo_repository

    pregunta_partida = partida_repository.obtener_pregunta_partida_por_id(db, pregunta_partida_id)
    if pregunta_partida is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró la pregunta del duelo")

    duelo = duelo_repository.obtener_duelo_por_id(db, pregunta_partida.partida_id)
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje=MENSAJE_DUELO_NO_ENCONTRADO)

    cruce = db.query(Cruce).filter(Cruce.duelo_id == duelo.id).first()
    if cruce:
        torneo_repository.bloquear_torneo(db, cruce.torneo_id)
    duelo = (db.query(PartidaDuelo).filter(PartidaDuelo.id == duelo.id)
             .populate_existing().with_for_update().first())
    db.refresh(pregunta_partida)

    numero_jugador = _numero_de_jugador(duelo, usuario_actual.id)
    if pregunta_partida.numero_jugador != numero_jugador:
        raise ExcepcionNoAutorizado(mensaje="Esta pregunta no te pertenece en este duelo")

    duelo = _finalizar_duelo(db, duelo.id)
    if duelo.estado == EstadoPartida.FINALIZADA:
        # Persistir un cierre vencido incluso cuando esta respuesta se rechaza.
        db.commit()
        raise PartidaYaFinalizadaError()

    if duelo.es_duelo_online and estado_presencia(duelo)[f"jugador{numero_jugador}_vencido"]:
        raise ExcepcionBase(codigo="DUELO_PRESENCIA_VENCIDA", codigo_estado=409,
                           mensaje="Venció el plazo de reconexión. Esperando el cierre del duelo.")

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
    db.flush()
    if cruce:
        _finalizar_duelo(db, duelo.id)
    return pregunta_partida


def finalizar_duelo_si_corresponde(db: Session, duelo_id: int, confirmar: bool = True) -> PartidaDuelo:
    """Finaliza duelo, puntajes y cruce en una sola transacción, sin duplicar premios."""
    try:
        actual = duelo_repository.obtener_duelo_por_id(db, duelo_id)
        if actual is not None and actual.estado == EstadoPartida.PENDIENTE_RIVAL:
            duelo_repository.bloquear_cola_online(db)
            duelo_repository.cerrar_busquedas_vencidas(
                db, datetime.now(timezone.utc), CONFIGURACION.DUELO_ESPERA_MAX_SEGUNDOS,
            )
        duelo = _finalizar_duelo(db, duelo_id)
        if confirmar:
            db.commit()
        return duelo
    except Exception:
        db.rollback()
        raise


def _finalizar_duelo(db: Session, duelo_id: int) -> PartidaDuelo:
    from app.models.cruce import Cruce
    from app.models.enumeraciones import EstadoCruce
    from app.repositories import torneo_repository
    from app.services.torneo_service import resolver_cruce_desde_duelo, _obtener_usuario_ganador_duelo

    db.flush()
    cruce = db.query(Cruce).filter(Cruce.duelo_id == duelo_id).first()
    # Todas las escrituras toman los bloqueos en el mismo orden: torneo, duelo, usuarios.
    torneo = torneo_repository.bloquear_torneo(db, cruce.torneo_id) if cruce else None
    if cruce:
        db.refresh(cruce)
    duelo = (db.query(PartidaDuelo).filter(PartidaDuelo.id == duelo_id)
             .populate_existing().with_for_update().first())
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje=MENSAJE_DUELO_NO_ENCONTRADO)
    db.expire(duelo, ["preguntas"])
    if duelo.estado == EstadoPartida.FINALIZADA:
        if cruce and cruce.estado != EstadoCruce.JUGADO and duelo.motivo_finalizacion != "SIN_CONEXION":
            resolver_cruce_desde_duelo(db, torneo, cruce, duelo)
        return duelo

    preguntas1 = duelo.preguntas_de_jugador(1)
    preguntas2 = duelo.preguntas_de_jugador(2)
    completas = (len(preguntas1) == CANTIDAD_PREGUNTAS_POR_PARTIDA
                 and len(preguntas2) == CANTIDAD_PREGUNTAS_POR_PARTIDA
                 and all(p.esta_respondida for p in preguntas1 + preguntas2))
    abandono = None
    sin_conexion = False
    if not completas and duelo.es_duelo_online and duelo.estado == EstadoPartida.EN_CURSO and duelo.jugador2_id:
        presencia = estado_presencia(duelo)
        if presencia["jugador1_vencido"] and presencia["jugador2_vencido"]:
            sin_conexion = True
        elif presencia["jugador1_vencido"] and not presencia["jugador2_ausente"]:
            abandono = 2
        elif presencia["jugador2_vencido"] and not presencia["jugador1_ausente"]:
            abandono = 1
    if not completas and abandono is None and not sin_conexion:
        return duelo

    duelo.puntaje_jugador1 = sum(p.puntaje_obtenido for p in preguntas1)
    duelo.puntaje_jugador2 = sum(p.puntaje_obtenido for p in preguntas2)
    if sin_conexion:
        duelo.numero_ganador = None
        duelo.motivo_finalizacion = "SIN_CONEXION"
        # Sin ganador no se avanza el cuadro: el cruce permite crear otro duelo.
        if cruce:
            cruce.duelo_id = None
    elif abandono:
        duelo.numero_ganador = abandono
        duelo.motivo_finalizacion = "ABANDONO"
    else:
        duelo.determinar_ganador()
    if cruce and duelo.numero_ganador is None and not sin_conexion:
        ganador_id = _obtener_usuario_ganador_duelo(duelo)
        duelo.numero_ganador = 1 if ganador_id == duelo.jugador1_id else 2
    duelo.estado = EstadoPartida.FINALIZADA
    duelo.fecha_fin = datetime.now(timezone.utc)
    db.flush()
    if not sin_conexion:
        _acumular_puntajes_duelo(db, duelo)
    if cruce and not sin_conexion:
        resolver_cruce_desde_duelo(db, torneo, cruce, duelo)
    return duelo


def _acumular_puntajes_duelo(db: Session, duelo: PartidaDuelo) -> None:
    """Acumula puntos sin confirmar la transacción y bloqueando usuarios por ID."""
    puntos = {duelo.jugador1_id: duelo.puntaje_jugador1}
    if duelo.jugador2_id is not None:
        puntos[duelo.jugador2_id] = duelo.puntaje_jugador2
    for usuario_id in sorted(puntos):
        ranking_service.acumular_puntaje(db, usuario_id, puntos[usuario_id], confirmar=False)
