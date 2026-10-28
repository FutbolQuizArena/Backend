from datetime import datetime, timezone
from functools import wraps
from sqlalchemy.orm import Session

from app.core.excepciones import (
    ExcepcionRecursoNoEncontrado,
    ExcepcionValidacion,
    TorneoAccesoDenegadoError,
    TorneoNoDisponibleError,
)
from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoPartida, EstadoTorneo, ModalidadDuelo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.partida_duelo import PartidaDuelo
from app.models.partida import PreguntaPartida
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import (
    categoria_repository,
    duelo_repository,
    pregunta_repository,
    torneo_repository,
)
from app.schemas.torneo_schema import (
    CruceIniciarDueloResponse,
    CruceResolucionResponse,
    CruceResolverRequest,
    CruceResponse,
    FiltroTorneoEnum,
    ParticipanteDetalleResponse,
    TorneoCreate,
    TorneoDetalleResponse,
    TorneoListItemResponse,
    TorneoUnirseRequest,
)
from app.schemas.duelo_schema import DueloJuegoResponse
from app.services import ranking_service
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA
from app.services.ranking_service import PUNTOS_CAMPEON_TORNEO
from app.services.usuario_service import hashear_password

MENSAJE_TORNEO_NO_DISPONIBLE = "El torneo no se encuentra disponible para unirse"


def _transaccion_torneo(funcion):
    """Confirma cada operación completa o revierte todos sus cambios."""
    @wraps(funcion)
    def ejecutar(db: Session, *args, **kwargs):
        try:
            resultado = funcion(db, *args, **kwargs)
            db.commit()
            return resultado
        except Exception:
            db.rollback()
            raise
    return ejecutar


@_transaccion_torneo
def crear_torneo(
    db: Session,
    datos: TorneoCreate,
    usuario_actual: Usuario,
) -> Torneo:
    """Crea un nuevo torneo y registra automáticamente al creador como participante.

    Flujo según Diagrama de Secuencia Nº3 (pasos 1 a 7):
      1. Si se especificó contraseña de acceso, genera su hash seguro con bcrypt.
      2. Instancia la entidad Torneo con estado ESPERANDO_JUGADORES y creador_id.
      3. Invoca torneo.generar_codigo_acceso() para obtener un código alfanumérico único.
      4. Persiste el torneo en la base de datos vía torneo_repository.crear().
      5. Instancia y persiste a ParticipanteTorneo asociando al usuario_actual con el torneo.
      6. Retorna el torneo creado con su ID y código asignados.
    """
    contrasena_hash = None
    if datos.contrasena_acceso and datos.contrasena_acceso.strip():
        contrasena_hash = hashear_password(datos.contrasena_acceso.strip())

    torneo = Torneo(
        nombre=datos.nombre,
        cantidad_participantes=datos.cantidad_participantes,
        contrasena_acceso=contrasena_hash,
        estado=EstadoTorneo.ESPERANDO_JUGADORES,
        creador_id=usuario_actual.id,
    )

    # Invoca el método de instancia ya implementado en el modelo
    torneo.codigo_acceso = torneo.generar_codigo_acceso()

    # Verificación preventiva de colisión de código único
    while torneo_repository.obtener_por_codigo_acceso(db, torneo.codigo_acceso) is not None:
        torneo.codigo_acceso = torneo.generar_codigo_acceso()

    # Persistir torneo
    db.add(torneo)
    db.flush()
    torneo_creado = torneo

    # Inscripción automática del creador como primer participante (Paso 6 del diagrama)
    participante_creador = ParticipanteTorneo(
        torneo_id=torneo_creado.id,
        usuario_id=usuario_actual.id,
    )
    db.add(participante_creador)
    db.flush()

    return torneo_creado


@_transaccion_torneo
def unirse_a_torneo(
    db: Session,
    datos: TorneoUnirseRequest,
    usuario_actual: Usuario,
) -> Torneo:
    """Permite a un usuario unirse a un torneo mediante su código de acceso.

    Flujo según Diagrama de Secuencia Nº3 (pasos 10 a 24):
      1. Busca el torneo por su código de acceso único. Si no existe -> TorneoNoDisponibleError.
      2. Valida que el usuario no esté previamente inscripto en el torneo.
      3. Delega la validación de reglas de dominio en torneo.unirse() (estado, cupo y contraseña).
      4. Si es válido, crea y persiste la entidad ParticipanteTorneo en la base de datos.
      5. Evalúa si el torneo completó su cupo mediante torneo.esta_completo().
      6. Si está completo, transiciona el estado a EN_CURSO y actualiza en BD (pasos 22-23).
      7. Retorna la entidad Torneo actualizada.
    """
    torneo = torneo_repository.obtener_por_codigo_acceso(db, codigo=datos.codigo_acceso)
    if torneo is not None:
        torneo = torneo_repository.bloquear_torneo(db, torneo.id)
    if torneo is None:
        raise TorneoNoDisponibleError(
            mensaje=MENSAJE_TORNEO_NO_DISPONIBLE,
            detalle=None,
        )

    # Prevenir que el mismo usuario se una dos veces
    if torneo_repository.es_participante(db, torneo_id=torneo.id, usuario_id=usuario_actual.id):
        raise TorneoNoDisponibleError(
            mensaje=MENSAJE_TORNEO_NO_DISPONIBLE,
            detalle=None,
        )

    # Validación encapsulada en el modelo de dominio según diagrama de clases E4
    if not torneo.unirse(usuario=usuario_actual, contrasena_ingresada=datos.contrasena):
        raise TorneoNoDisponibleError(
            mensaje=MENSAJE_TORNEO_NO_DISPONIBLE,
            detalle=None,
        )

    # Registrar al nuevo participante
    nuevo_participante = ParticipanteTorneo(
        torneo_id=torneo.id,
        usuario_id=usuario_actual.id,
    )
    db.add(nuevo_participante)
    db.flush()

    # Refrescar la relación de participantes del torneo para validar cupo actual
    db.refresh(torneo)

    # Pasos 22 y 23 del diagrama de secuencia: si se completa el cupo, pasa a EN_CURSO
    # y dispara la generación automática de cruces para la Ronda 1 (Diagrama de Secuencia Nº4)
    if torneo.esta_completo():
        torneo.estado = EstadoTorneo.EN_CURSO
        generar_cruces_para_torneo(torneo=torneo, db=db, confirmar=False)

    return torneo


def generar_cruces_para_torneo(
    torneo: Torneo | Session,
    db: Session | Torneo | None = None,
    confirmar: bool = True,
) -> list[Cruce]:
    """Genera y persiste los cruces iniciales (Ronda 1) de un torneo al completarse el cupo.

    Flujo según Diagrama de Secuencia Nº4 (pasos 1 a 6):
      1. Obtiene los pares de emparejamiento aleatorio invocando torneo.generar_cruces().
      2. Instancia una entidad Cruce por cada par (ronda=1, estado=PENDIENTE, ganador_id=None).
      3. Persiste la lista de cruces en la base de datos vía torneo_repository.crear_cruces().
      4. Retorna la lista de cruces creados.
    """
    if isinstance(torneo, Session):
        sesion = torneo
        torneo_instancia = db
    else:
        torneo_instancia = torneo
        sesion = db

    if sesion is None:
        from sqlalchemy.orm import object_session
        sesion = object_session(torneo_instancia)

    pares = torneo_instancia.generar_cruces()
    cruces: list[Cruce] = []
    for jugador_a, jugador_b in pares:
        cruce = Cruce(
            torneo_id=torneo_instancia.id,
            torneo=torneo_instancia,
            ronda=1,
            jugador_a_id=jugador_a.id,
            jugador_b_id=jugador_b.id,
            estado=EstadoCruce.PENDIENTE,
            ganador_id=None,
        )
        cruces.append(cruce)

    if sesion is not None:
        if not confirmar:
            sesion.add_all(cruces)
            sesion.flush()
            return cruces
        return torneo_repository.crear_cruces(db=sesion, cruces=cruces)
    return torneo_repository.crear_cruces(cruces)


def listar_torneos(
    db: Session,
    filtro: FiltroTorneoEnum | str,
    usuario_actual: Usuario,
) -> list[TorneoListItemResponse]:
    """Lista torneos según el filtro especificado (mios, disponibles, finalizados).

    - 'mios': torneos donde el usuario es participante (cualquier estado).
    - 'disponibles': torneos en ESPERANDO_JUGADORES con cupo disponible donde el usuario aún NO participa.
    - 'finalizados': torneos con estado FINALIZADO en los que el usuario participó.

    Evita consultas N+1 calculando el cupo actual en una única consulta SQL.
    Solo expone codigo_acceso para aquellos torneos donde el usuario es el creador.
    """
    valor_filtro = filtro.value if isinstance(filtro, FiltroTorneoEnum) else str(filtro).lower()

    if valor_filtro == FiltroTorneoEnum.MIOS.value:
        resultados = torneo_repository.listar_por_participante(db, usuario_id=usuario_actual.id)
    elif valor_filtro == FiltroTorneoEnum.DISPONIBLES.value:
        resultados = torneo_repository.listar_disponibles(db, usuario_id=usuario_actual.id)
    elif valor_filtro == FiltroTorneoEnum.FINALIZADOS.value:
        resultados = torneo_repository.listar_finalizados_por_participante(db, usuario_id=usuario_actual.id)
    else:
        raise ExcepcionValidacion(
            mensaje=f"Filtro inválido '{filtro}'. Valores permitidos: mios, disponibles, finalizados",
            detalle=None,
        )

    items = []
    for torneo, conteo in resultados:
        item = TorneoListItemResponse(
            id=torneo.id,
            nombre=torneo.nombre,
            cantidad_participantes=torneo.cantidad_participantes,
            cantidad_participantes_actual=conteo or 0,
            tiene_contrasena=torneo.contrasena_acceso is not None,
            estado=torneo.estado,
            fecha_creacion=torneo.fecha_creacion,
            creador_id=torneo.creador_id,
            codigo_acceso=torneo.codigo_acceso if torneo.creador_id == usuario_actual.id else None,
        )
        items.append(item)

    return items


@_transaccion_torneo
def salir_de_torneo(
    db: Session,
    torneo_id: int,
    usuario_actual: Usuario,
) -> str:
    """Permite a un usuario abandonar un torneo antes de su inicio.

    Flujo y reglas de negocio:
      1. Busca el torneo por su ID. Si no existe -> ExcepcionRecursoNoEncontrado (HTTP 404).
      2. Verifica que el usuario sea participante activo del torneo. Si no lo es -> TorneoNoDisponibleError (HTTP 400).
      3. Invoca la lógica de dominio en torneo.salir(usuario_actual).
      4. Si el torneo ya no permite salidas (EN_CURSO o FINALIZADO) -> TorneoNoDisponibleError (HTTP 400).
      5. Si quien sale es el creador del torneo:
         - Elimina el torneo completo mediante torneo_repository.eliminar_torneo(db, torneo).
         - Las entidades hijas (participantes y cruces) se eliminan por cascada (delete-orphan).
         - Retorna mensaje informativo de cancelación del torneo.
      6. Si quien sale es un participante regular:
         - Elimina únicamente la inscripción del participante mediante torneo_repository.eliminar_participante(db, participante).
         - Retorna mensaje de confirmación de salida.
    """
    torneo = torneo_repository.bloquear_torneo(db, torneo_id)
    if torneo is None:
        raise ExcepcionRecursoNoEncontrado(
            mensaje=f"No se encontró ningún torneo con el ID {torneo_id}",
            detalle=None,
        )

    participante = torneo_repository.obtener_participante(
        db,
        torneo_id=torneo.id,
        usuario_id=usuario_actual.id,
    )
    if participante is None:
        raise TorneoNoDisponibleError(
            mensaje="No eres participante de este torneo",
            detalle=None,
        )

    accion = torneo.salir(usuario=usuario_actual)

    if accion == "no_permitido":
        raise TorneoNoDisponibleError(
            mensaje="No es posible salir de un torneo que ya ha comenzado o finalizado",
            detalle=None,
        )

    if accion == "torneo_cancelado":
        db.delete(torneo)
        return "Torneo cancelado exitosamente al salir el creador"

    # accion == "participante_eliminado"
    db.delete(participante)
    return "Has salido del torneo exitosamente"


def _obtener_detalle_participante_cruce(
    cruce: Cruce,
    relacion: str,
    participantes: dict[int, ParticipanteDetalleResponse],
    creador_id: int,
) -> ParticipanteDetalleResponse | None:
    """Reutiliza el participante mapeado o lo obtiene de la relación del cruce."""
    detalle = participantes.get(getattr(cruce, f"{relacion}_id"))
    if detalle:
        return detalle

    participante = getattr(cruce, relacion, None)
    if not participante or not participante.usuario:
        return None

    return ParticipanteDetalleResponse(
        id=participante.id,
        usuario_id=participante.usuario_id,
        nombre=participante.usuario.nombre,
        es_creador=(participante.usuario_id == creador_id),
    )


def _construir_cuadro_torneo(
    cruces: list[Cruce],
    participantes: dict[int, ParticipanteDetalleResponse],
    creador_id: int,
) -> list[CruceResponse]:
    """Construye el cuadro conservando el orden y los datos de cada cruce."""
    cuadro: list[CruceResponse] = []
    for cruce in cruces:
        jugador_a = _obtener_detalle_participante_cruce(cruce, "jugador_a", participantes, creador_id)
        jugador_b = _obtener_detalle_participante_cruce(cruce, "jugador_b", participantes, creador_id)
        ganador = None
        if cruce.ganador_id:
            ganador = _obtener_detalle_participante_cruce(cruce, "ganador", participantes, creador_id)
        cuadro.append(CruceResponse(
            id=cruce.id,
            torneo_id=cruce.torneo_id,
            ronda=cruce.ronda,
            duelo_id=cruce.duelo_id,
            jugador_a_id=cruce.jugador_a_id,
            jugador_b_id=cruce.jugador_b_id,
            ganador_id=cruce.ganador_id,
            estado=cruce.estado,
            jugador_a=jugador_a,
            jugador_b=jugador_b,
            ganador=ganador,
        ))
    return cuadro


def obtener_detalle_torneo(
    db: Session | int,
    torneo_id: int | Usuario,
    usuario_actual: Usuario | None = None,
) -> TorneoDetalleResponse:
    """Obtiene los detalles completos de la sala del torneo, participantes y cuadro de llaves.

    Flujo y reglas de negocio:
      1. Busca el torneo por su ID. Si no existe -> TorneoNoDisponibleError (HTTP 404).
      2. Valida control de acceso: el usuario debe ser el creador o un participante inscripto.
         Si no cumple -> TorneoAccesoDenegadoError (HTTP 403).
      3. Construye la lista de participantes identificando al creador (es_creador=True).
      4. Obtiene los cruces mediante torneo_repository.obtener_cruces_por_torneo() (vacío si el torneo aún
         está ESPERANDO_JUGADORES).
      5. Construye y retorna la entidad TorneoDetalleResponse con el cuadro ordenado por ronda.
    """
    if isinstance(db, int):
        id_torneo = db
        usuario = torneo_id
        from sqlalchemy.orm import object_session
        sesion = object_session(usuario)
    else:
        sesion = db
        id_torneo = torneo_id
        usuario = usuario_actual

    torneo = torneo_repository.obtener_por_id(sesion, id=id_torneo)
    if torneo is None:
        raise TorneoNoDisponibleError(
            mensaje=f"No se encontró ningún torneo con el ID {id_torneo}",
            detalle=None,
            codigo_estado=404,
        )

    # Control de acceso: solo creador o participante
    es_creador = (usuario.id == torneo.creador_id)
    es_part = torneo_repository.es_participante(sesion, torneo_id=torneo.id, usuario_id=usuario.id)
    if not (es_creador or es_part):
        raise TorneoAccesoDenegadoError(
            mensaje="No tienes permisos para acceder a este torneo",
            detalle=None,
        )

    # Mapear participantes
    participantes_detalle: list[ParticipanteDetalleResponse] = []
    participantes_dict: dict[int, ParticipanteDetalleResponse] = {}
    for p in (torneo.participantes or []):
        nombre = p.usuario.nombre if (hasattr(p, "usuario") and p.usuario) else "Participante"
        part_es_creador = (p.usuario_id == torneo.creador_id)
        detalle_p = ParticipanteDetalleResponse(
            id=p.id,
            usuario_id=p.usuario_id,
            nombre=nombre,
            es_creador=part_es_creador,
        )
        participantes_detalle.append(detalle_p)
        participantes_dict[p.id] = detalle_p

    # Obtener cruces
    cruces_db = torneo_repository.obtener_cruces_por_torneo(sesion, torneo_id=torneo.id)
    cuadro = _construir_cuadro_torneo(cruces_db, participantes_dict, torneo.creador_id)

    creador_nombre = torneo.creador.nombre if (hasattr(torneo, "creador") and torneo.creador) else "Organizador"

    return TorneoDetalleResponse(
        id=torneo.id,
        nombre=torneo.nombre,
        estado=torneo.estado,
        cantidad_participantes=torneo.cantidad_participantes,
        cantidad_participantes_actual=len(torneo.participantes or []),
        creador_id=torneo.creador_id,
        creador_nombre=creador_nombre,
        codigo_acceso=torneo.codigo_acceso,
        fecha_creacion=torneo.fecha_creacion,
        participantes=participantes_detalle,
        cuadro=cuadro,
    )


@_transaccion_torneo
def iniciar_duelo_cruce(
    db: Session, torneo_id: int, cruce_id: int, usuario_actual: Usuario,
) -> CruceIniciarDueloResponse:
    """Crea atómicamente un duelo exclusivo del cruce o recupera el ya asignado."""
    torneo, cruce = _obtener_torneo_y_cruce(db, torneo_id, cruce_id)
    _validar_acceso_cruce(torneo, cruce, usuario_actual, permitir_creador=False)
    if cruce.duelo_id is None:
        if torneo.estado != EstadoTorneo.EN_CURSO or cruce.estado != EstadoCruce.PENDIENTE:
            raise TorneoNoDisponibleError(mensaje="El torneo o el cruce no está disponible para jugar")
        categoria = categoria_repository.obtener_categoria_jugable(db, CANTIDAD_PREGUNTAS_POR_PARTIDA)
        if categoria is None:
            raise ExcepcionValidacion(mensaje="No hay categorías activas con 10 preguntas disponibles para disputar el cruce")
        preguntas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
            db, categoria.id, CANTIDAD_PREGUNTAS_POR_PARTIDA,
        )
        duelo = PartidaDuelo(
            categoria_id=categoria.id, modalidad=ModalidadDuelo.ONLINE.value,
            jugador1_id=cruce.jugador_a.usuario_id, jugador2_id=cruce.jugador_b.usuario_id,
            estado=EstadoPartida.EN_CURSO, fecha_emparejamiento=datetime.now(timezone.utc),
        )
        db.add(duelo)
        db.flush()
        cruce.duelo_id = duelo.id
        db.add_all([
            PreguntaPartida(partida_id=duelo.id, pregunta_id=pregunta.id, orden=orden, numero_jugador=numero)
            for numero in (1, 2) for orden, pregunta in enumerate(preguntas, start=1)
        ])
        db.flush()
    else:
        duelo = duelo_repository.obtener_duelo_por_id(db, cruce.duelo_id)
    numero = 1 if duelo.jugador1_id == usuario_actual.id else 2
    return CruceIniciarDueloResponse(
        cruce_id=cruce.id, duelo_id=duelo.id, torneo_id=torneo.id, ronda=cruce.ronda,
        mensaje="Duelo del cruce disponible", duelo=DueloJuegoResponse.desde_duelo(duelo, numero),
    )


def _obtener_torneo_y_cruce(db: Session, torneo_id: int, cruce_id: int) -> tuple[Torneo, Cruce]:
    torneo = torneo_repository.bloquear_torneo(db, torneo_id)
    if torneo is None:
        raise TorneoNoDisponibleError(mensaje=f"No se encontró ningún torneo con el ID {torneo_id}", codigo_estado=404)
    cruce = torneo_repository.obtener_cruce_por_id(db, cruce_id)
    if cruce is None:
        raise TorneoNoDisponibleError(mensaje=f"No se encontró ningún cruce con el ID {cruce_id}", codigo_estado=404)
    if cruce.torneo_id != torneo.id:
        raise TorneoNoDisponibleError(mensaje="El cruce no pertenece a este torneo")
    return torneo, cruce


def _validar_acceso_cruce(torneo: Torneo, cruce: Cruce, usuario: Usuario, permitir_creador: bool) -> None:
    participantes = (cruce.jugador_a.usuario_id, cruce.jugador_b.usuario_id)
    if usuario.id not in participantes and not (permitir_creador and usuario.id == torneo.creador_id):
        raise TorneoAccesoDenegadoError(mensaje="No tienes permisos para acceder a este cruce")


def _obtener_usuario_ganador_duelo(duelo: PartidaDuelo) -> int:
    """Obtiene el ganador y conserva el desempate por tiempo a favor del jugador 1 si igualan."""
    if duelo.numero_ganador == 1:
        return duelo.jugador1_id
    if duelo.numero_ganador == 2:
        return duelo.jugador2_id

    tiempo_jugador_1 = sum(p.tiempo_respuesta_segundos or 0 for p in duelo.preguntas_de_jugador(1))
    tiempo_jugador_2 = sum(p.tiempo_respuesta_segundos or 0 for p in duelo.preguntas_de_jugador(2))
    if tiempo_jugador_2 < tiempo_jugador_1:
        return duelo.jugador2_id
    return duelo.jugador1_id


@_transaccion_torneo
def resolver_cruce(
    db: Session, torneo_id: int, cruce_id: int, usuario_actual: Usuario, datos: CruceResolverRequest,
) -> CruceResolucionResponse:
    """Reintento seguro de resolución: solo acepta el duelo asignado y respuestas reales."""
    from app.services.duelo_service import finalizar_duelo_si_corresponde

    torneo, cruce = _obtener_torneo_y_cruce(db, torneo_id, cruce_id)
    _validar_acceso_cruce(torneo, cruce, usuario_actual, permitir_creador=True)
    if cruce.duelo_id is None or datos.duelo_id != cruce.duelo_id:
        raise TorneoNoDisponibleError(mensaje="El duelo indicado no está asignado a este cruce")
    duelo = finalizar_duelo_si_corresponde(db, datos.duelo_id, confirmar=False)
    if duelo.estado != EstadoPartida.FINALIZADA:
        raise TorneoNoDisponibleError(mensaje="El duelo aún no ha finalizado; ambos jugadores deben completar sus preguntas")
    return resolver_cruce_desde_duelo(db, torneo, cruce, duelo)


def resolver_cruce_desde_duelo(
    db: Session, torneo: Torneo, cruce: Cruce, duelo: PartidaDuelo,
) -> CruceResolucionResponse:
    """Se ejecuta bajo el bloqueo del torneo y dentro de la transacción del duelo."""
    usuarios = {cruce.jugador_a.usuario_id, cruce.jugador_b.usuario_id}
    if cruce.duelo_id != duelo.id or usuarios != {duelo.jugador1_id, duelo.jugador2_id}:
        raise TorneoNoDisponibleError(mensaje="El duelo indicado no corresponde al cruce")
    if duelo.estado != EstadoPartida.FINALIZADA:
        raise TorneoNoDisponibleError(mensaje="El duelo aún no ha finalizado")
    if cruce.estado != EstadoCruce.JUGADO:
        ganador_id = _obtener_usuario_ganador_duelo(duelo)
        ganador = cruce.jugador_a if ganador_id == cruce.jugador_a.usuario_id else cruce.jugador_b
        cruce.determinar_ganador(ganador)
        db.flush()
    return _evaluar_avance_ronda(db, torneo, cruce, cruce.ganador)


def _evaluar_avance_ronda(
    db: Session, torneo: Torneo, cruce: Cruce, ganador_participante: ParticipanteTorneo,
) -> CruceResolucionResponse:
    """Informa pendientes, genera la próxima ronda o finaliza y premia al campeón."""
    # Evaluar cruces de la ronda actual
    cruces_ronda = torneo_repository.obtener_cruces_por_ronda(db, torneo_id=torneo.id, ronda=cruce.ronda)
    quedan_pendientes = any(c.estado == EstadoCruce.PENDIENTE for c in cruces_ronda)

    nombre_ganador = (
        ganador_participante.usuario.nombre
        if (hasattr(ganador_participante, "usuario") and ganador_participante.usuario)
        else "Participante"
    )

    if quedan_pendientes:
        return CruceResolucionResponse(
            cruce_id=cruce.id,
            estado_cruce=cruce.estado,
            ganador_id=ganador_participante.id,
            ganador_nombre=nombre_ganador,
            ronda_completada=False,
            siguiente_ronda_generada=False,
            nueva_ronda=None,
            torneo_finalizado=False,
            campeon=None,
            puntos_otorgados_campeon=0,
        )

    # Toda la ronda actual ha sido completada
    ganadores_ordenados = [c.ganador for c in cruces_ronda]

    if len(ganadores_ordenados) > 1:
        # Generar siguiente ronda
        ronda_siguiente = cruce.ronda + 1
        existentes = torneo_repository.obtener_cruces_por_ronda(db, torneo.id, ronda_siguiente)
        if not existentes:
            nuevos_cruces = torneo.armar_cruces_siguiente_ronda(ganadores_ordenados, ronda_siguiente)
            db.add_all(nuevos_cruces)
            db.flush()

        return CruceResolucionResponse(
            cruce_id=cruce.id,
            estado_cruce=cruce.estado,
            ganador_id=ganador_participante.id,
            ganador_nombre=nombre_ganador,
            ronda_completada=True,
            siguiente_ronda_generada=True,
            nueva_ronda=ronda_siguiente,
            torneo_finalizado=False,
            campeon=None,
            puntos_otorgados_campeon=0,
        )

    # Queda exactamente 1 ganador -> Era la Final
    ya_finalizado = torneo.estado == EstadoTorneo.FINALIZADO
    torneo.finalizar_torneo()
    campeon_participante = ganadores_ordenados[0]
    campeon_usuario = campeon_participante.usuario
    if not ya_finalizado:
        ranking_service.acumular_puntaje(
            db, usuario_id=campeon_usuario.id, puntos=PUNTOS_CAMPEON_TORNEO, confirmar=False,
        )
    db.flush()

    campeon_detalle = ParticipanteDetalleResponse(
        id=campeon_participante.id,
        usuario_id=campeon_usuario.id,
        nombre=campeon_usuario.nombre,
        es_creador=(campeon_usuario.id == torneo.creador_id),
    )

    return CruceResolucionResponse(
        cruce_id=cruce.id,
        estado_cruce=cruce.estado,
        ganador_id=ganador_participante.id,
        ganador_nombre=nombre_ganador,
        ronda_completada=True,
        siguiente_ronda_generada=False,
        nueva_ronda=None,
        torneo_finalizado=True,
        campeon=campeon_detalle,
        puntos_otorgados_campeon=PUNTOS_CAMPEON_TORNEO,
    )
