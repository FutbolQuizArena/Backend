"""Servicio de lógica de negocio para autenticación de usuarios y generación de tokens JWT."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict
from uuid import uuid4
import jwt
from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import CredencialesInvalidasError, ExcepcionNoAutorizado, TokenInvalidoError
from app.models.usuario import Usuario
from app.repositories import token_revocado_repository, usuario_repository


def generar_token_jwt(usuario: Usuario) -> str:
    """Genera un token JWT firmado para el usuario autenticado.

    Incluye en el payload el id (como sub e id numérico), email y rol del usuario,
    además de la fecha de emisión (iat), expiración (exp) e identificador único (jti).
    """
    ahora = datetime.now(timezone.utc)
    expiracion = ahora + timedelta(minutes=CONFIGURACION.JWT_EXPIRATION_MIN)

    rol_str = usuario.rol.value if hasattr(usuario.rol, "value") else str(usuario.rol)

    payload: Dict[str, Any] = {
        "sub": str(usuario.id),
        "id": usuario.id,
        "email": usuario.email,
        "rol": rol_str,
        "iat": ahora,
        "exp": expiracion,
        "jti": uuid4().hex,
    }

    token: str = jwt.encode(
        payload,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )
    return token


def decodificar_token_jwt(token: str) -> Dict[str, Any]:
    """Decodifica y valida la firma y expiración de un token JWT.

    Lanza ExcepcionNoAutorizado si el token está vencido o es inválido.
    Preparada para ser consumida por el middleware de autorización (1.1.4).
    """
    try:
        payload = jwt.decode(
            token,
            CONFIGURACION.JWT_SECRET,
            algorithms=[CONFIGURACION.JWT_ALGORITMO],
            options={"require": ["exp"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ExcepcionNoAutorizado(
            mensaje="El token de acceso ha expirado",
            detalle=None,
        )
    except jwt.InvalidTokenError:
        raise ExcepcionNoAutorizado(
            mensaje="Token de autenticación inválido",
            detalle=None,
        )


def obtener_huella_token(token: str) -> str:
    """Identifica una firma ya validada incluso con variantes de padding Base64.

    También permite revocar tokens anteriores que no contienen jti.
    """
    firma = jwt.utils.base64url_decode(token.rsplit(".", 1)[1].encode("ascii"))
    return sha256(firma).hexdigest()


def validar_token_no_revocado(db: Session, token: str) -> None:
    """Rechaza un token previamente validado si se cerró su sesión."""
    if token_revocado_repository.esta_revocado(db, obtener_huella_token(token)):
        raise TokenInvalidoError()


def revocar_token(db: Session, token: str) -> None:
    """Confirma el logout solo después de persistir la revocación."""
    payload = decodificar_token_jwt(token)
    token_revocado_repository.revocar(
        db,
        huella=obtener_huella_token(token),
        expira_en=int(payload["exp"]),
        ahora=int(datetime.now(timezone.utc).timestamp()),
    )


def autenticar_usuario(db: Session, email: str, password: str) -> Usuario:
    """Autentica a un usuario validando su correo electrónico y contraseña.

    Flujo según diagrama de secuencia (pasos 14 a 16):
      1. Busca al usuario por email utilizando usuario_repository.obtener_por_email.
      2. Si no existe, o si usuario.autenticar(password) devuelve False, lanza CredencialesInvalidasError
         con respuesta 401 uniforme, protegiendo contra enumeración de usuarios.
      3. Si las credenciales coinciden, retorna la entidad Usuario autenticada.
    """
    usuario = usuario_repository.obtener_por_email(db, email=email)

    if usuario is None or not usuario.autenticar(password):
        raise CredencialesInvalidasError(
            mensaje="Credenciales inválidas",
            detalle=None,
        )

    return usuario

