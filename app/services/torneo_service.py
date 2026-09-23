"""Servicio de lógica de negocio para la gestión de torneos."""

from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import torneo_repository
from app.schemas.torneo_schema import TorneoCreate
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
    while torneo_repository.obtener_por_codigo(db, torneo.codigo_acceso) is not None:
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

