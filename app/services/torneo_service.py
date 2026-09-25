from datetime import datetime, timezone
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
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import (
    categoria_repository,
    duelo_repository,
    partida_repository,
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
from app.services.configuracion_partida import CANTIDAD_PREGUNTAS_POR_PARTIDA
from app.services.duelo_service import finalizar_duelo_si_corresponde
from app.services.usuario_service import hashear_password


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
    torneo_creado = torneo_repository.crear(db=db, torneo=torneo)

    # Inscripción automática del creador como primer participante (Paso 6 del diagrama)
    participante_creador = ParticipanteTorneo(
        torneo_id=torneo_creado.id,
        usuario_id=usuario_actual.id,
    )
    torneo_repository.agregar_participante(db=db, participante=participante_creador)

    return torneo_creado


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
    if torneo is None:
        raise TorneoNoDisponibleError(
            mensaje="El torneo no se encuentra disponible para unirse",
            detalle=None,
        )

    # Prevenir que el mismo usuario se una dos veces
    if torneo_repository.es_participante(db, torneo_id=torneo.id, usuario_id=usuario_actual.id):
        raise TorneoNoDisponibleError(
            mensaje="El torneo no se encuentra disponible para unirse",
            detalle=None,
        )

    # Validación encapsulada en el modelo de dominio según diagrama de clases E4
    if not torneo.unirse(usuario=usuario_actual, contrasena_ingresada=datos.contrasena):
        raise TorneoNoDisponibleError(
            mensaje="El torneo no se encuentra disponible para unirse",
            detalle=None,
        )

    # Registrar al nuevo participante
    nuevo_participante = ParticipanteTorneo(
        torneo_id=torneo.id,
        usuario_id=usuario_actual.id,
    )
    torneo_repository.agregar_participante(db=db, participante=nuevo_participante)

    # Refrescar la relación de participantes del torneo para validar cupo actual
    db.refresh(torneo)

    # Pasos 22 y 23 del diagrama de secuencia: si se completa el cupo, pasa a EN_CURSO
    # y dispara la generación automática de cruces para la Ronda 1 (Diagrama de Secuencia Nº4)
    if torneo.esta_completo():
        torneo = torneo_repository.actualizar_estado(
            db=db,
            torneo=torneo,
            nuevo_estado=EstadoTorneo.EN_CURSO,
        )
        generar_cruces_para_torneo(torneo=torneo, db=db)

    return torneo


def generar_cruces_para_torneo(
    torneo: Torneo | Session,
    db: Session | Torneo | None = None,
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
    torneo = torneo_repository.obtener_por_id(db, id=torneo_id)
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
        torneo_repository.eliminar_torneo(db, torneo=torneo)
        return "Torneo cancelado exitosamente al salir el creador"

    # accion == "participante_eliminado"
    torneo_repository.eliminar_participante(db, participante=participante)
    return "Has salido del torneo exitosamente"


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
    cuadro: list[CruceResponse] = []
    for c in cruces_db:
        jugador_a = participantes_dict.get(c.jugador_a_id)
        if not jugador_a and hasattr(c, "jugador_a") and c.jugador_a and c.jugador_a.usuario:
            jugador_a = ParticipanteDetalleResponse(
                id=c.jugador_a.id,
                usuario_id=c.jugador_a.usuario_id,
                nombre=c.jugador_a.usuario.nombre,
                es_creador=(c.jugador_a.usuario_id == torneo.creador_id),
            )

        jugador_b = participantes_dict.get(c.jugador_b_id)
        if not jugador_b and hasattr(c, "jugador_b") and c.jugador_b and c.jugador_b.usuario:
            jugador_b = ParticipanteDetalleResponse(
                id=c.jugador_b.id,
                usuario_id=c.jugador_b.usuario_id,
                nombre=c.jugador_b.usuario.nombre,
                es_creador=(c.jugador_b.usuario_id == torneo.creador_id),
            )

        ganador = None
        if c.ganador_id:
            ganador = participantes_dict.get(c.ganador_id)
            if not ganador and hasattr(c, "ganador") and c.ganador and c.ganador.usuario:
                ganador = ParticipanteDetalleResponse(
                    id=c.ganador.id,
                    usuario_id=c.ganador.usuario_id,
                    nombre=c.ganador.usuario.nombre,
                    es_creador=(c.ganador.usuario_id == torneo.creador_id),
                )

        cuadro.append(
            CruceResponse(
                id=c.id,
                torneo_id=c.torneo_id,
                ronda=c.ronda,
                jugador_a_id=c.jugador_a_id,
                jugador_b_id=c.jugador_b_id,
                ganador_id=c.ganador_id,
                estado=c.estado,
                jugador_a=jugador_a,
                jugador_b=jugador_b,
                ganador=ganador,
            )
        )

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


def iniciar_duelo_cruce(
    db: Session,
    torneo_id: int,
    cruce_id: int,
    usuario_actual: Usuario,
) -> CruceIniciarDueloResponse:
    """Inicia o recupera el duelo online para disputar un cruce de torneo (Tarea 3.2.2)."""
    torneo = torneo_repository.obtener_por_id(db, id=torneo_id)
    if torneo is None:
        raise TorneoNoDisponibleError(
            mensaje=f"No se encontró ningún torneo con el ID {torneo_id}",
            codigo_estado=404,
        )

    if torneo.estado != EstadoTorneo.EN_CURSO:
        raise TorneoNoDisponibleError(
            mensaje="El torneo debe estar en curso para disputar cruces",
            codigo_estado=400,
        )

    cruce = torneo_repository.obtener_cruce_por_id(db, cruce_id=cruce_id)
    if cruce is None:
        raise TorneoNoDisponibleError(
            mensaje=f"No se encontró ningún cruce con el ID {cruce_id}",
            codigo_estado=404,
        )

    if cruce.torneo_id != torneo.id:
        raise TorneoNoDisponibleError(
            mensaje="El cruce especificado no pertenece a este torneo",
            codigo_estado=400,
        )

    if cruce.estado != EstadoCruce.PENDIENTE:
        raise TorneoNoDisponibleError(
            mensaje="El cruce ya ha sido disputado y resuelto",
            codigo_estado=400,
        )

    usuario_a_id = cruce.jugador_a.usuario_id if (cruce.jugador_a and cruce.jugador_a.usuario_id) else None
    usuario_b_id = cruce.jugador_b.usuario_id if (cruce.jugador_b and cruce.jugador_b.usuario_id) else None

    if usuario_actual.id not in (usuario_a_id, usuario_b_id):
        raise TorneoAccesoDenegadoError(
            mensaje="No tienes permisos para disputar este cruce; no formas parte de él"
        )

    # Buscar si ya existe un duelo creado previamente para este cruce entre ambos usuarios
    u1, u2 = usuario_a_id, usuario_b_id
    duelo_existente = (
        db.query(PartidaDuelo)
        .filter(
            PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
            (
                ((PartidaDuelo.jugador1_id == u1) & (PartidaDuelo.jugador2_id == u2))
                | ((PartidaDuelo.jugador1_id == u2) & (PartidaDuelo.jugador2_id == u1))
            ),
            PartidaDuelo.estado.in_([EstadoPartida.EN_CURSO, EstadoPartida.FINALIZADA, EstadoPartida.PENDIENTE_RIVAL]),
        )
        .order_by(PartidaDuelo.id.desc())
        .first()
    )

    if duelo_existente is not None:
        return CruceIniciarDueloResponse(
            cruce_id=cruce.id,
            duelo_id=duelo_existente.id,
            torneo_id=torneo.id,
            ronda=cruce.ronda,
            mensaje="Duelo recuperado exitosamente para el cruce",
        )

    # Crear nuevo duelo para el cruce
    categoria = categoria_repository.obtener_categoria_aleatoria(db)
    if categoria is None:
        raise ExcepcionValidacion(mensaje="No hay categorías disponibles para disputar el cruce")

    preguntas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
        db=db, categoria_id=categoria.id, cantidad=CANTIDAD_PREGUNTAS_POR_PARTIDA
    )
    if not preguntas:
        raise ExcepcionValidacion(mensaje="La categoría seleccionada no tiene suficientes preguntas")

    duelo = duelo_repository.crear_duelo(
        db=db,
        jugador1_id=u1,
        categoria_id=categoria.id,
        modalidad=ModalidadDuelo.ONLINE,
    )
    duelo.jugador2_id = u2
    duelo.estado = EstadoPartida.EN_CURSO
    duelo.fecha_emparejamiento = datetime.now(timezone.utc)
    db.add(duelo)
    db.commit()
    db.refresh(duelo)

    pregunta_ids = [p.id for p in preguntas]
    partida_repository.agregar_preguntas_a_partida(
        db=db, partida_id=duelo.id, pregunta_ids=pregunta_ids, numero_jugador=1
    )
    partida_repository.agregar_preguntas_a_partida(
        db=db, partida_id=duelo.id, pregunta_ids=pregunta_ids, numero_jugador=2
    )
    db.refresh(duelo)

    return CruceIniciarDueloResponse(
        cruce_id=cruce.id,
        duelo_id=duelo.id,
        torneo_id=torneo.id,
        ronda=cruce.ronda,
        mensaje="Duelo iniciado y emparejado exitosamente para el cruce",
    )


def resolver_cruce(
    db: Session,
    torneo_id: int,
    cruce_id: int,
    usuario_actual: Usuario,
    datos: CruceResolverRequest,
) -> CruceResolucionResponse:
    """Resuelve el resultado de un cruce eliminatorio y evalúa el avance de ronda o finalización del torneo (Tarea 3.2.2)."""
    torneo = torneo_repository.obtener_por_id(db, id=torneo_id)
    if torneo is None:
        raise TorneoNoDisponibleError(
            mensaje=f"No se encontró ningún torneo con el ID {torneo_id}",
            codigo_estado=404,
        )

    if torneo.estado != EstadoTorneo.EN_CURSO:
        raise TorneoNoDisponibleError(
            mensaje="El torneo no se encuentra en curso para resolver cruces",
            codigo_estado=400,
        )

    cruce = torneo_repository.obtener_cruce_por_id(db, cruce_id=cruce_id)
    if cruce is None:
        raise TorneoNoDisponibleError(
            mensaje=f"No se encontró ningún cruce con el ID {cruce_id}",
            codigo_estado=404,
        )

    if cruce.torneo_id != torneo.id:
        raise TorneoNoDisponibleError(
            mensaje="El cruce no pertenece a este torneo",
            codigo_estado=400,
        )

    if cruce.estado == EstadoCruce.JUGADO:
        raise TorneoNoDisponibleError(
            mensaje="El cruce ya ha sido resuelto y disputado previamente",
            codigo_estado=400,
        )

    usuario_a_id = cruce.jugador_a.usuario_id if (cruce.jugador_a and cruce.jugador_a.usuario_id) else None
    usuario_b_id = cruce.jugador_b.usuario_id if (cruce.jugador_b and cruce.jugador_b.usuario_id) else None
    es_part_cruce = usuario_actual.id in (usuario_a_id, usuario_b_id)
    es_creador = usuario_actual.id == torneo.creador_id

    if not (es_part_cruce or es_creador):
        raise TorneoAccesoDenegadoError(
            mensaje="No tienes permisos para resolver este cruce"
        )

    ganador_participante: ParticipanteTorneo | None = None

    if datos.duelo_id is not None:
        duelo = duelo_repository.obtener_duelo_por_id(db, datos.duelo_id)
        if duelo is None:
            raise TorneoNoDisponibleError(
                mensaje=f"No se encontró ningún duelo con el ID {datos.duelo_id}",
                codigo_estado=404,
            )

        u_cruce = {usuario_a_id, usuario_b_id}
        u_duelo = {duelo.jugador1_id, duelo.jugador2_id}
        if u_cruce != u_duelo:
            raise TorneoNoDisponibleError(
                mensaje="El duelo indicado no corresponde a los participantes de este cruce",
                codigo_estado=400,
            )

        if duelo.estado != EstadoPartida.FINALIZADA:
            # Intento de finalización automática por si ambos terminaron
            duelo = finalizar_duelo_si_corresponde(db, duelo.id)
            if duelo.estado != EstadoPartida.FINALIZADA:
                raise TorneoNoDisponibleError(
                    mensaje="El duelo aún no ha finalizado; ambos jugadores deben completar sus preguntas",
                    codigo_estado=400,
                )

        # Determinar usuario ganador del duelo
        if duelo.numero_ganador == 1:
            ganador_usuario_id = duelo.jugador1_id
        elif duelo.numero_ganador == 2:
            ganador_usuario_id = duelo.jugador2_id
        else:
            # Desempate por menor tiempo de respuesta acumulado
            t1 = sum(p.tiempo_respuesta_segundos or 0 for p in duelo.preguntas_de_jugador(1))
            t2 = sum(p.tiempo_respuesta_segundos or 0 for p in duelo.preguntas_de_jugador(2))
            if t1 < t2:
                ganador_usuario_id = duelo.jugador1_id
            elif t2 < t1:
                ganador_usuario_id = duelo.jugador2_id
            else:
                ganador_usuario_id = duelo.jugador1_id

        if ganador_usuario_id == usuario_a_id:
            ganador_participante = cruce.jugador_a
        else:
            ganador_participante = cruce.jugador_b

    elif datos.ganador_participante_id is not None:
        if datos.ganador_participante_id not in (cruce.jugador_a_id, cruce.jugador_b_id):
            raise TorneoNoDisponibleError(
                mensaje=f"El participante {datos.ganador_participante_id} no pertenece a este cruce",
                codigo_estado=400,
            )
        if datos.ganador_participante_id == cruce.jugador_a_id:
            ganador_participante = cruce.jugador_a
        else:
            ganador_participante = cruce.jugador_b

    if ganador_participante is None:
        raise TorneoNoDisponibleError(
            mensaje="No se pudo determinar el participante ganador del cruce",
            codigo_estado=400,
        )

    # Invocación a método de dominio
    cruce.determinar_ganador(ganador_participante)
    torneo_repository.actualizar_cruce(db, cruce)

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
        nuevos_cruces = torneo.armar_cruces_siguiente_ronda(
            ganadores_ordenados=ganadores_ordenados,
            ronda_siguiente=ronda_siguiente,
        )
        torneo_repository.crear_cruces(db=db, cruces=nuevos_cruces)

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
    torneo.finalizar_torneo()
    campeon_participante = ganadores_ordenados[0]
    campeon_usuario = campeon_participante.usuario
    campeon_usuario.sumar_puntaje(1500)
    db.commit()
    db.refresh(torneo)
    db.refresh(campeon_usuario)

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
        puntos_otorgados_campeon=1500,
    )

