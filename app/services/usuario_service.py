"""Servicio de lógica de negocio para la gestión de usuarios y registro."""

import bcrypt
from sqlalchemy.orm import Session

from app.core.exceptions import CredencialesInvalidasError, EmailYaRegistradoError
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.schemas.usuario_schema import UsuarioCreate


def hashear_password(password: str) -> str:
    """Genera el hash seguro de una contraseña en texto plano utilizando bcrypt."""
    sal = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("utf-8")


def verificar_password(password_plana: str, password_hasheada: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con su hash almacenado."""
    return bcrypt.checkpw(
        password_plana.encode("utf-8"),
        password_hasheada.encode("utf-8"),
    )


def registrar_usuario(db: Session, datos: UsuarioCreate) -> Usuario:
    """Registra un nuevo usuario en la plataforma validando reglas de negocio.

    Flujo según diagrama de secuencia (pasos 3 a 7):
      1. Verifica que el email no se encuentre ya registrado en la base de datos.
      2. Si existe, lanza EmailYaRegistradoError (código 409).
      3. Hashea la contraseña provista mediante bcrypt (hashear_password).
      4. Instancia la entidad Usuario con rol JUGADOR.
      5. Persiste el usuario a través del repositorio y retorna la entidad persistida.
    """
    usuario_existente = usuario_repository.obtener_por_email(db, email=datos.email)
    if usuario_existente is not None:
        raise EmailYaRegistradoError(
            mensaje="El correo electrónico ya se encuentra registrado",
            detalle=None,
        )

    password_hasheada = hashear_password(datos.password)

    nuevo_usuario = Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=password_hasheada,
        rol=RolUsuario.JUGADOR,
    )

    return usuario_repository.crear(db, nuevo_usuario)


def actualizar_perfil_usuario(
    db: Session,
    usuario_actual: Usuario,
    nombre: str,
    email: str,
    password_actual: str | None = None,
    nueva_password: str | None = None,
) -> Usuario:
    """Actualiza el perfil de un usuario validando unicidad de correo y cambio opcional de contraseña.

    Flujo:
      1. Si se proporciona nueva_password:
         a. Valida que password_actual sea correcta mediante usuario_actual.autenticar().
         b. Si no coincide o falta, lanza CredencialesInvalidasError (HTTP 401).
         c. Hashea la nueva contraseña y delega la mutación en usuario_actual.cambiar_password().
      2. Si el nuevo email es distinto al actual, verifica que no esté en uso por otro usuario (HTTP 409).
      3. Invoca usuario_actual.actualizar_perfil(nombre, email).
      4. Persiste los cambios mediante usuario_repository.actualizar(db, usuario_actual).
      5. Retorna la entidad Usuario actualizada.
    """
    if nueva_password:
        if not password_actual or not usuario_actual.autenticar(password_actual):
            raise CredencialesInvalidasError(
                mensaje="La contraseña actual es incorrecta",
                detalle=None,
            )
        nuevo_hash = hashear_password(nueva_password)
        usuario_actual.cambiar_password(nuevo_hash)

    if email.lower() != usuario_actual.email.lower():
        usuario_existente = usuario_repository.obtener_por_email(db, email=email)
        if usuario_existente is not None and usuario_existente.id != usuario_actual.id:
            raise EmailYaRegistradoError(
                mensaje="El correo electrónico ya se encuentra registrado",
                detalle=None,
            )

    usuario_actual.actualizar_perfil(nombre=nombre, email=email)
    return usuario_repository.actualizar(db, usuario_actual)


def cambiar_password_usuario(
    db: Session,
    usuario_actual: Usuario,
    password_actual: str,
    nueva_password: str,
) -> Usuario:
    """Actualiza la contraseña del usuario validando la clave actual."""
    if not usuario_actual.autenticar(password_actual):
        raise CredencialesInvalidasError(
            mensaje="La contraseña actual es incorrecta",
            detalle=None,
        )
    nuevo_hash = hashear_password(nueva_password)
    usuario_actual.cambiar_password(nuevo_hash)
    return usuario_repository.actualizar(db, usuario_actual)

