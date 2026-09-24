"""Servicio de lógica de negocio para la gestión de torneos."""

from sqlalchemy.orm import Session

from app.core.excepciones import (
    ExcepcionRecursoNoEncontrado,
    ExcepcionValidacion,
    TorneoAccesoDenegadoError,
    TorneoNoDisponibleError,
)
from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import torneo_repository
from app.schemas.torneo_schema import (
    CruceResponse,
    FiltroTorneoEnum,
    ParticipanteDetalleResponse,
    TorneoCreate,
    TorneoDetalleResponse,
    TorneoListItemResponse,
    TorneoUnirseRequest,
)
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

