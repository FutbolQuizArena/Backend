"""Pruebas unitarias y de integración para el endpoint de login y servicios de JWT."""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import jwt

from app.core.config import CONFIGURACION
from app.core.exceptions import CredencialesInvalidasError, ExcepcionNoAutorizado
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioCreate
from app.services import auth_service, usuario_service


# ==============================================================================
# Fixtures auxiliares de prueba
# ==============================================================================


@pytest.fixture
def usuario_registrado(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario de prueba en la base de datos."""
    datos = UsuarioCreate(
        nombre="Lionel Messi",
        email="leo.messi@futbolquiz.com",
        password="passwordCampeon10",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


# ==============================================================================
# Pruebas de Integración (Endpoint POST /api/auth/login)
# ==============================================================================


def test_login_exitoso(cliente: TestClient, usuario_registrado: Usuario) -> None:
    """Verifica que un usuario existente pueda autenticarse exitosamente (HTTP 200)

    y reciba un access_token y token_type='bearer'.
    """
    payload = {
        "email": usuario_registrado.email,
        "password": "passwordCampeon10",
    }

    respuesta = cliente.post("/api/auth/login", json=payload)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert "access_token" in datos
    assert isinstance(datos["access_token"], str)
    assert len(datos["access_token"]) > 0
    assert datos["token_type"] == "bearer"


def test_login_email_inexistente(cliente: TestClient) -> None:
    """Verifica que un intento de login con email no registrado retorne 401 Unauthorized

    con la estructura estandarizada y mensaje genérico sin filtrar detalles.
    """
    payload = {
        "email": "noexiste@futbolquiz.com",
        "password": "passwordSeguro123",
    }

    respuesta = cliente.post("/api/auth/login", json=payload)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()

    assert cuerpo["code"] == "CREDENCIALES_INVALIDAS"
    assert cuerpo["message"] == "Credenciales inválidas"
    assert cuerpo["detail"] is None


def test_login_password_incorrecta(cliente: TestClient, usuario_registrado: Usuario) -> None:
    """Verifica que un intento de login con contraseña incorrecta retorne 401 Unauthorized

    con idéntico código y mensaje que ante un email inexistente (evita enumeración de usuarios).
    """
    payload = {
        "email": usuario_registrado.email,
        "password": "passwordTotalmenteEquivocada",
    }

    respuesta = cliente.post("/api/auth/login", json=payload)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()

    assert cuerpo["code"] == "CREDENCIALES_INVALIDAS"
    assert cuerpo["message"] == "Credenciales inválidas"
    assert cuerpo["detail"] is None


def test_login_token_contenido_y_decodificacion(
    cliente: TestClient,
    usuario_registrado: Usuario,
) -> None:
    """Verifica que el JWT devuelto en el login contenga al decodificarse

    el id y rol correctos del usuario, junto con email y fechas iat/exp.
    """
    payload = {
        "email": usuario_registrado.email,
        "password": "passwordCampeon10",
    }

    respuesta = cliente.post("/api/auth/login", json=payload)
    assert respuesta.status_code == 200

    token = respuesta.json()["access_token"]
    datos_token = auth_service.decodificar_token_jwt(token)

    # Verifica claims requeridos
    assert datos_token["id"] == usuario_registrado.id
    assert datos_token["sub"] == str(usuario_registrado.id)
    assert datos_token["rol"] == usuario_registrado.rol.value
    assert datos_token["email"] == usuario_registrado.email
    assert "iat" in datos_token
    assert "exp" in datos_token
    assert datos_token["exp"] > datos_token["iat"]


def test_login_body_invalido(cliente: TestClient) -> None:
    """Verifica que solicitudes con formato inválido o campos faltantes retornen 422."""
    # Email mal formado
    resp_email_invalido = cliente.post(
        "/api/auth/login",
        json={"email": "correo-sin-arroba", "password": "password123"},
    )
    assert resp_email_invalido.status_code == 422
    assert resp_email_invalido.json()["code"] == "ERROR_VALIDACION"

    # Falta el campo password
    resp_sin_password = cliente.post(
        "/api/auth/login",
        json={"email": "usuario@futbolquiz.com"},
    )
    assert resp_sin_password.status_code == 422
    assert resp_sin_password.json()["code"] == "ERROR_VALIDACION"

    # Falta el campo email
    resp_sin_email = cliente.post(
        "/api/auth/login",
        json={"password": "password123"},
    )
    assert resp_sin_email.status_code == 422
    assert resp_sin_email.json()["code"] == "ERROR_VALIDACION"

    # Contraseña vacía
    resp_password_vacio = cliente.post(
        "/api/auth/login",
        json={"email": "usuario@futbolquiz.com", "password": ""},
    )
    assert resp_password_vacio.status_code == 422
    assert resp_password_vacio.json()["code"] == "ERROR_VALIDACION"


# ==============================================================================
# Pruebas Unitarias del Servicio (auth_service)
# ==============================================================================


def test_usuario_metodo_autenticar(usuario_registrado: Usuario) -> None:
    """Prueba unitaria del método de instancia Usuario.autenticar() del modelo de dominio.

    Verifica que la contraseña correcta retorne True y que contraseñas incorrectas o vacías retornen False,
    encapsulando el acceso a password_hash según el diagrama de clases E4.
    """
    assert usuario_registrado.autenticar("passwordCampeon10") is True
    assert usuario_registrado.autenticar("otraClaveIncorrecta") is False
    assert usuario_registrado.autenticar("") is False


def test_auth_service_autenticar_usuario_exitoso(
    sesion_db: Session,
    usuario_registrado: Usuario,
) -> None:
    """Prueba unitaria de autenticar_usuario devolviendo el Usuario ante credenciales válidas."""
    usuario = auth_service.autenticar_usuario(
        sesion_db,
        email=usuario_registrado.email,
        password="passwordCampeon10",
    )
    assert usuario.id == usuario_registrado.id
    assert usuario.email == usuario_registrado.email


def test_auth_service_autenticar_usuario_fallido_lanza_excepcion(
    sesion_db: Session,
    usuario_registrado: Usuario,
) -> None:
    """Prueba unitaria de autenticar_usuario lanzando CredencialesInvalidasError."""
    # Email inexistente
    with pytest.raises(CredencialesInvalidasError) as exc_email:
        auth_service.autenticar_usuario(
            sesion_db,
            email="fantasma@futbolquiz.com",
            password="passwordCampeon10",
        )
    assert exc_email.value.codigo == "CREDENCIALES_INVALIDAS"
    assert exc_email.value.codigo_estado == 401

    # Contraseña incorrecta
    with pytest.raises(CredencialesInvalidasError) as exc_pass:
        auth_service.autenticar_usuario(
            sesion_db,
            email=usuario_registrado.email,
            password="claveIncorrecta",
        )
    assert exc_pass.value.codigo == "CREDENCIALES_INVALIDAS"
    assert exc_pass.value.codigo_estado == 401


def test_auth_service_token_expirado_lanza_excepcion() -> None:
    """Verifica que un token expirado lance ExcepcionNoAutorizado al decodificarse."""
    ahora = datetime.now(timezone.utc)
    payload_expirado = {
        "sub": "1",
        "id": 1,
        "email": "test@futbolquiz.com",
        "rol": "JUGADOR",
        "iat": ahora - timedelta(hours=2),
        "exp": ahora - timedelta(hours=1),
    }
    token_expirado = jwt.encode(
        payload_expirado,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )

    with pytest.raises(ExcepcionNoAutorizado) as exc_info:
        auth_service.decodificar_token_jwt(token_expirado)

    assert exc_info.value.codigo == "NO_AUTORIZADO"
    assert exc_info.value.codigo_estado == 401
    assert "expirado" in exc_info.value.mensaje.lower()


def test_auth_service_token_invalido_lanza_excepcion() -> None:
    """Verifica que un token corrupto o con firma incorrecta lance ExcepcionNoAutorizado."""
    token_firma_erronea = jwt.encode(
        {"sub": "1", "id": 1, "rol": "JUGADOR"},
        "clave_secreta_distinta_de_mas_de_32_bytes_para_test",
        algorithm="HS256",
    )

    with pytest.raises(ExcepcionNoAutorizado) as exc_info:
        auth_service.decodificar_token_jwt(token_firma_erronea)

    assert exc_info.value.codigo == "NO_AUTORIZADO"
    assert exc_info.value.codigo_estado == 401

    with pytest.raises(ExcepcionNoAutorizado):
        auth_service.decodificar_token_jwt("este-no-es-un-jwt-valido")
