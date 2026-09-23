"""Pruebas unitarias y de integración para dependencias de seguridad y autorización (RBAC)."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
import jwt
from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import AccesoDenegadoError, TokenInvalidoError
from app.core.seguridad import obtener_usuario_actual, requiere_rol
from app.main import app
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, usuario_service

# Router de prueba para verificar dependencias vía HTTP
router_pruebas = APIRouter(prefix="/api/pruebas-seguridad", tags=["Pruebas Seguridad"])


@router_pruebas.get("/perfil")
def ruta_perfil_protegida(
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
) -> dict:
    """Endpoint de prueba protegido con obtener_usuario_actual."""
    return {
        "id": usuario_actual.id,
        "email": usuario_actual.email,
        "rol": usuario_actual.rol.value,
    }


@router_pruebas.get(
    "/solo-admin",
    dependencies=[Depends(requiere_rol(RolUsuario.ADMINISTRADOR))],
)
def ruta_solo_administrador() -> dict:
    """Endpoint de prueba protegido exclusivamente para administradores."""
    return {"mensaje": "Acceso concedido para administrador"}


@router_pruebas.get(
    "/ambos-roles",
    dependencies=[Depends(requiere_rol(RolUsuario.ADMINISTRADOR, RolUsuario.JUGADOR))],
)
def ruta_ambos_roles() -> dict:
    """Endpoint de prueba accesible tanto para jugador como para administrador."""
    return {"mensaje": "Acceso concedido para roles autorizados"}


# Registrar router de prueba en la aplicación de FastAPI
app.include_router(router_pruebas)


# ==============================================================================
# Fixtures auxiliares de prueba
# ==============================================================================


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario con rol JUGADOR."""
    datos = UsuarioCreate(
        nombre="Lionel Messi",
        email="jugador.test@futbolquiz.com",
        password="passwordJugador123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_administrador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario con rol ADMINISTRADOR."""
    admin = Usuario(
        nombre="Lionel Scaloni",
        email="admin.test@futbolquiz.com",
        password_hash=usuario_service.hashear_password("passwordAdmin123"),
        rol=RolUsuario.ADMINISTRADOR,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def token_expirado(usuario_jugador: Usuario) -> str:
    """Genera un token JWT con fecha de expiración en el pasado."""
    ahora = datetime.now(timezone.utc)
    payload_expirado = {
        "sub": str(usuario_jugador.id),
        "id": usuario_jugador.id,
        "email": usuario_jugador.email,
        "rol": usuario_jugador.rol.value,
        "iat": ahora - timedelta(hours=2),
        "exp": ahora - timedelta(hours=1),
    }
    return jwt.encode(
        payload_expirado,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )


# ==============================================================================
# Pruebas Unitarias de las Dependencias
# ==============================================================================


def test_obtener_usuario_actual_token_valido(
    sesion_db: Session,
    usuario_jugador: Usuario,
) -> None:
    """Verifica que obtener_usuario_actual retorne el Usuario correspondiente ante un token válido."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    usuario_obtenido = obtener_usuario_actual(token=token, db=sesion_db)

    assert usuario_obtenido.id == usuario_jugador.id
    assert usuario_obtenido.email == usuario_jugador.email
    assert usuario_obtenido.rol == RolUsuario.JUGADOR


def test_obtener_usuario_actual_token_invalido(sesion_db: Session) -> None:
    """Verifica que un token manipulado o con firma incorrecta lance TokenInvalidoError (401)."""
    with pytest.raises(TokenInvalidoError) as exc_info:
        obtener_usuario_actual(token="token_completamente_invalido_xyz", db=sesion_db)

    assert exc_info.value.codigo == "TOKEN_INVALIDO"
    assert exc_info.value.codigo_estado == 401


def test_obtener_usuario_actual_token_expirado(
    sesion_db: Session,
    token_expirado: str,
) -> None:
    """Verifica que un token expirado lance TokenInvalidoError (401)."""
    with pytest.raises(TokenInvalidoError) as exc_info:
        obtener_usuario_actual(token=token_expirado, db=sesion_db)

    assert exc_info.value.codigo == "TOKEN_INVALIDO"
    assert exc_info.value.codigo_estado == 401


def test_obtener_usuario_actual_usuario_inexistente(sesion_db: Session) -> None:
    """Verifica que un token con id que no existe en BD lance TokenInvalidoError (401)."""
    ahora = datetime.now(timezone.utc)
    payload_inexistente = {
        "sub": "99999",
        "id": 99999,
        "email": "inexistente@futbolquiz.com",
        "rol": "JUGADOR",
        "iat": ahora,
        "exp": ahora + timedelta(minutes=30),
    }
    token_inexistente = jwt.encode(
        payload_inexistente,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )

    with pytest.raises(TokenInvalidoError) as exc_info:
        obtener_usuario_actual(token=token_inexistente, db=sesion_db)

    assert exc_info.value.codigo == "TOKEN_INVALIDO"
    assert exc_info.value.codigo_estado == 401


def test_obtener_usuario_actual_usuario_deshabilitado(
    sesion_db: Session,
    usuario_jugador: Usuario,
) -> None:
    """Verifica que un usuario con esta_habilitado=False lance TokenInvalidoError (401)."""
    usuario_jugador.esta_habilitado = False
    sesion_db.commit()

    token = autenticacion_service.generar_token_jwt(usuario_jugador)

    with pytest.raises(TokenInvalidoError) as exc_info:
        obtener_usuario_actual(token=token, db=sesion_db)

    assert exc_info.value.codigo == "TOKEN_INVALIDO"
    assert exc_info.value.codigo_estado == 401


def test_requiere_rol_acceso_denegado_lanza_excepcion(
    usuario_jugador: Usuario,
) -> None:
    """Verifica que requiere_rol lance AccesoDenegadoError (403) si el rol no coincide."""
    verificador = requiere_rol(RolUsuario.ADMINISTRADOR)

    with pytest.raises(AccesoDenegadoError) as exc_info:
        verificador(usuario_actual=usuario_jugador)

    assert exc_info.value.codigo == "ACCESO_DENEGADO"
    assert exc_info.value.codigo_estado == 403
    assert exc_info.value.mensaje == "No tenés permisos para realizar esta acción"


def test_requiere_rol_acceso_permitido_retorna_usuario(
    usuario_administrador: Usuario,
) -> None:
    """Verifica que requiere_rol permita el acceso y retorne el usuario si el rol coincide."""
    verificador = requiere_rol(RolUsuario.ADMINISTRADOR)
    usuario_retornado = verificador(usuario_actual=usuario_administrador)

    assert usuario_retornado.id == usuario_administrador.id
    assert usuario_retornado.rol == RolUsuario.ADMINISTRADOR


# ==============================================================================
# Pruebas de Integración HTTP (Vía TestClient con Routers Protegidos)
# ==============================================================================


def test_http_endpoint_protegido_token_valido(
    cliente: TestClient,
    usuario_jugador: Usuario,
) -> None:
    """Verifica acceso exitoso (HTTP 200) al enviar token Bearer válido."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    encabezados = {"Authorization": f"Bearer {token}"}

    respuesta = cliente.get("/api/pruebas-seguridad/perfil", headers=encabezados)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["id"] == usuario_jugador.id
    assert datos["email"] == usuario_jugador.email
    assert datos["rol"] == "JUGADOR"


def test_http_endpoint_protegido_token_invalido(cliente: TestClient) -> None:
    """Verifica HTTP 401 y estructura estandarizada ante token corrupto/manipulado."""
    encabezados = {"Authorization": "Bearer token_falso_invalido"}

    respuesta = cliente.get("/api/pruebas-seguridad/perfil", headers=encabezados)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"
    assert "Token de autenticación inválido o expirado" in cuerpo["message"]
    assert cuerpo["detail"] is None


def test_http_endpoint_protegido_token_expirado(
    cliente: TestClient,
    token_expirado: str,
) -> None:
    """Verifica HTTP 401 y estructura estandarizada ante token con exp vencido."""
    encabezados = {"Authorization": f"Bearer {token_expirado}"}

    respuesta = cliente.get("/api/pruebas-seguridad/perfil", headers=encabezados)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"
    assert cuerpo["detail"] is None


def test_http_endpoint_protegido_usuario_deshabilitado(
    cliente: TestClient,
    sesion_db: Session,
    usuario_jugador: Usuario,
) -> None:
    """Verifica HTTP 401 si el usuario asociado al token fue deshabilitado."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)

    usuario_jugador.esta_habilitado = False
    sesion_db.commit()

    encabezados = {"Authorization": f"Bearer {token}"}
    respuesta = cliente.get("/api/pruebas-seguridad/perfil", headers=encabezados)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"
    assert cuerpo["detail"] is None


def test_http_requiere_rol_admin_con_usuario_jugador_retorna_403(
    cliente: TestClient,
    usuario_jugador: Usuario,
) -> None:
    """Verifica HTTP 403 y mensaje uniforme cuando un JUGADOR accede a ruta de ADMINISTRADOR."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    encabezados = {"Authorization": f"Bearer {token}"}

    respuesta = cliente.get("/api/pruebas-seguridad/solo-admin", headers=encabezados)

    assert respuesta.status_code == 403
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "ACCESO_DENEGADO"
    assert cuerpo["message"] == "No tenés permisos para realizar esta acción"
    assert cuerpo["detail"] is None


def test_http_requiere_rol_admin_con_usuario_administrador_retorna_200(
    cliente: TestClient,
    usuario_administrador: Usuario,
) -> None:
    """Verifica HTTP 200 cuando un ADMINISTRADOR accede a ruta protegida con requiere_rol."""
    token = autenticacion_service.generar_token_jwt(usuario_administrador)
    encabezados = {"Authorization": f"Bearer {token}"}

    respuesta = cliente.get("/api/pruebas-seguridad/solo-admin", headers=encabezados)

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"] == "Acceso concedido para administrador"


def test_http_requiere_rol_multiples_roles_autorizados(
    cliente: TestClient,
    usuario_jugador: Usuario,
    usuario_administrador: Usuario,
) -> None:
    """Verifica que ambos roles (JUGADOR y ADMINISTRADOR) tengan acceso si están en la lista."""
    token_jugador = autenticacion_service.generar_token_jwt(usuario_jugador)
    token_admin = autenticacion_service.generar_token_jwt(usuario_administrador)

    resp_jugador = cliente.get(
        "/api/pruebas-seguridad/ambos-roles",
        headers={"Authorization": f"Bearer {token_jugador}"},
    )
    assert resp_jugador.status_code == 200

    resp_admin = cliente.get(
        "/api/pruebas-seguridad/ambos-roles",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_admin.status_code == 200
