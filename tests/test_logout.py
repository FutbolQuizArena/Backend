"""Pruebas unitarias y de integración para el endpoint de logout (POST /api/auth/logout)."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
import jwt
from sqlalchemy.orm import Session

from app.core.config import CONFIGURACION
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioCreate
from app.services import auth_service, usuario_service


# ==============================================================================
# Fixtures auxiliares de prueba
# ==============================================================================


@pytest.fixture
def usuario_autenticado(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario de prueba en la base de datos."""
    datos = UsuarioCreate(
        nombre="Angel Di Maria",
        email="fideo.logout@futbolquiz.com",
        password="passwordFideo11",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def token_valido(usuario_autenticado: Usuario) -> str:
    """Genera un token JWT válido para el usuario de prueba."""
    return auth_service.generar_token_jwt(usuario_autenticado)


@pytest.fixture
def token_expirado(usuario_autenticado: Usuario) -> str:
    """Genera un token JWT con fecha de expiración en el pasado."""
    ahora = datetime.now(timezone.utc)
    payload_expirado = {
        "sub": str(usuario_autenticado.id),
        "id": usuario_autenticado.id,
        "email": usuario_autenticado.email,
        "rol": usuario_autenticado.rol.value,
        "iat": ahora - timedelta(hours=2),
        "exp": ahora - timedelta(hours=1),
    }
    return jwt.encode(
        payload_expirado,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )


# ==============================================================================
# Pruebas de Integración (Endpoint POST /api/auth/logout)
# ==============================================================================


def test_cerrar_sesion_exitoso(
    cliente: TestClient,
    token_valido: str,
) -> None:
    """Verifica que un usuario con token válido pueda cerrar sesión exitosamente (HTTP 200).

    Valida la estructura de respuesta {"mensaje": ...} y que no exponga datos sensibles.
    """
    encabezados = {"Authorization": f"Bearer {token_valido}"}

    respuesta = cliente.post("/api/auth/logout", headers=encabezados)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert "mensaje" in datos
    assert datos["mensaje"] == "Sesión cerrada exitosamente"

    # Verificar que no expone datos sensibles del usuario
    assert "password" not in datos
    assert "password_hash" not in datos
    assert "access_token" not in datos
    assert "email" not in datos


def test_cerrar_sesion_sin_token(cliente: TestClient) -> None:
    """Verifica que una petición sin token en el header Authorization retorne 401 Unauthorized."""
    respuesta = cliente.post("/api/auth/logout")

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert "code" in cuerpo
    assert cuerpo["code"] in ["TOKEN_INVALIDO", "ERROR_HTTP_401"]


def test_cerrar_sesion_token_invalido(cliente: TestClient) -> None:
    """Verifica que una petición con token malformado o manipulado retorne 401 Unauthorized."""
    encabezados = {"Authorization": "Bearer token_completamente_invalido_12345"}

    respuesta = cliente.post("/api/auth/logout", headers=encabezados)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"
    assert "Token de autenticación inválido o expirado" in cuerpo["message"]
    assert cuerpo["detail"] is None


def test_cerrar_sesion_token_expirado(
    cliente: TestClient,
    token_expirado: str,
) -> None:
    """Verifica que una petición con token expirado retorne 401 Unauthorized."""
    encabezados = {"Authorization": f"Bearer {token_expirado}"}

    respuesta = cliente.post("/api/auth/logout", headers=encabezados)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"
    assert cuerpo["detail"] is None


def test_cerrar_sesion_flujo_login_y_logout(
    cliente: TestClient,
    usuario_autenticado: Usuario,
) -> None:
    """Verifica el flujo integral: iniciar sesión, recibir token y luego cerrar sesión con él."""
    # 1. Login
    resp_login = cliente.post(
        "/api/auth/login",
        json={
            "email": usuario_autenticado.email,
            "password": "passwordFideo11",
        },
    )
    assert resp_login.status_code == 200
    token = resp_login.json()["access_token"]

    # 2. Logout con el token obtenido
    resp_logout = cliente.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_logout.status_code == 200
    assert resp_logout.json() == {"mensaje": "Sesión cerrada exitosamente"}

