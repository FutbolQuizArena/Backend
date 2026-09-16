"""Servicio de lógica de negocio para autenticación de usuarios y generación de tokens JWT."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import jwt
from sqlalchemy.orm import Session

from app.core.config import CONFIGURACION
from app.core.exceptions import CredencialesInvalidasError, ExcepcionNoAutorizado
from app.models.usuario import Usuario
from app.repositories import usuario_repository


def generar_token_jwt(usuario: Usuario) -> str:
    """Genera un token JWT firmado para el usuario autenticado.

    Incluye en el payload el id (como sub e id numérico), email y rol del usuario,
    además de la fecha de emisión (iat) y expiración (exp).
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

