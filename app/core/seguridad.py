"""Middleware y dependencias de seguridad y autorización para FastAPI."""

from typing import Any, Callable, Dict
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.base_datos import get_db
from app.core.excepciones import AccesoDenegadoError, TokenInvalidoError
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.services import autenticacion_service

# Configuración del esquema Bearer para Swagger UI con endpoint de login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def obtener_usuario_actual(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Extrae y valida el token JWT del encabezado Authorization, retornando el usuario autenticado.

    Flujo:
      1. Valida y decodifica el token mediante autenticacion_service.decodificar_token_jwt.
      2. Si el token es inválido o expiró, lanza TokenInvalidoError (HTTP 401).
      3. Obtiene el usuario de la base de datos a partir del id extraído del payload.
      4. Si el usuario no existe o se encuentra deshabilitado (esta_habilitado=False),
         lanza TokenInvalidoError (HTTP 401) sin revelar detalles.
      5. Retorna la entidad Usuario autenticada.
    """
    if not token:
        raise TokenInvalidoError()

    try:
        payload: Dict[str, Any] = autenticacion_service.decodificar_token_jwt(token)
    except Exception:
        raise TokenInvalidoError()

    id_usuario = payload.get("id") or payload.get("sub")
    if id_usuario is None:
        raise TokenInvalidoError()

    try:
        id_usuario_int = int(id_usuario)
    except (ValueError, TypeError):
        raise TokenInvalidoError()

    usuario = usuario_repository.obtener_por_id(db, id=id_usuario_int)
    if usuario is None or not usuario.esta_habilitado:
        raise TokenInvalidoError()

    return usuario


def requiere_rol(*roles_permitidos: RolUsuario) -> Callable[..., Usuario]:
    """Fábrica de dependencias para autorización basada en roles (RBAC).

    Retorna una función de dependencia que valida que el usuario autenticado
    posea alguno de los roles permitidos. Si no lo cumple, lanza AccesoDenegadoError (HTTP 403).

    Uso en routers:
      @router.get("/admin/algo", dependencies=[Depends(requiere_rol(RolUsuario.ADMINISTRADOR))])
      o inyectando el usuario:
      def endpoint(admin: Usuario = Depends(requiere_rol(RolUsuario.ADMINISTRADOR))): ...
    """
    roles_valores = {
        rol.value if hasattr(rol, "value") else str(rol)
        for rol in roles_permitidos
    }

    def _verificar_rol(
        usuario_actual: Usuario = Depends(obtener_usuario_actual),
    ) -> Usuario:
        rol_usuario = (
            usuario_actual.rol.value
            if hasattr(usuario_actual.rol, "value")
            else str(usuario_actual.rol)
        )
        if rol_usuario not in roles_valores:
            raise AccesoDenegadoError(
                mensaje="No tenés permisos para realizar esta acción",
                detalle=None,
            )
        return usuario_actual

    return _verificar_rol

