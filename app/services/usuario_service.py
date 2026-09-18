"""Servicio de lógica de negocio para la gestión de usuarios y registro."""

import bcrypt
from sqlalchemy.orm import Session

from app.core.exceptions import EmailYaRegistradoError
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
) -> Usuario:
    """Actualiza el perfil de un usuario validando que el correo no esté ocupado por otro usuario.

    Flujo:
      1. Si el nuevo email es distinto al actual, verifica en la base de datos que ningún
         otro usuario lo esté utilizando (distinto id). Si está ocupado, lanza EmailYaRegistradoError (HTTP 409).
      2. Invoca usuario_actual.actualizar_perfil(nombre, email) para delegar la mutación en el modelo.
      3. Persiste las modificaciones mediante usuario_repository.actualizar(db, usuario_actual).
      4. Retorna la entidad Usuario actualizada.
    """
    if email.lower() != usuario_actual.email.lower():
        usuario_existente = usuario_repository.obtener_por_email(db, email=email)
        if usuario_existente is not None and usuario_existente.id != usuario_actual.id:
            raise EmailYaRegistradoError(
                mensaje="El correo electrónico ya se encuentra registrado",
                detalle=None,
            )

    usuario_actual.actualizar_perfil(nombre=nombre, email=email)
    return usuario_repository.actualizar(db, usuario_actual)

