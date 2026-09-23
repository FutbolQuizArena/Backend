"""Pruebas unitarias y de integración para el endpoint de registro y servicios asociados."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import bcrypt
from app.core.excepciones import EmailYaRegistradoError
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.schemas.usuario_schema import UsuarioCreate
from app.services import usuario_service
from app.services.usuario_service import hashear_password, verificar_password


# ==============================================================================
# Pruebas de Integración (Endpoint POST /api/auth/registro)
# ==============================================================================


def test_registro_usuario_exitoso(cliente: TestClient) -> None:
    """Verifica el registro exitoso: retorna 201, rol JUGADOR por default y sin datos sensibles."""
    payload = {
        "nombre": "Enzo Fernandez",
        "email": "enzo.fernandez@futbolquiz.com",
        "password": "passwordSeguro123",
    }

    respuesta = cliente.post("/api/auth/registro", json=payload)

    assert respuesta.status_code == 201
    datos = respuesta.json()

    assert datos["id"] is not None
    assert datos["nombre"] == "Enzo Fernandez"
    assert datos["email"] == "enzo.fernandez@futbolquiz.com"
    assert datos["rol"] == RolUsuario.JUGADOR.value
    assert datos["puntaje_total"] == 0
    assert datos["esta_habilitado"] is True
    assert "fecha_alta" in datos

    # Seguridad: nunca exponer el hash ni el password
    assert "password" not in datos
    assert "password_hash" not in datos


def test_registro_email_ya_existente(cliente: TestClient) -> None:
    """Verifica que registrar un email existente retorne 409 con la estructura de error fijada."""
    payload = {
        "nombre": "Julian Alvarez",
        "email": "arana@futbolquiz.com",
        "password": "passwordSeguro123",
    }

    # Primer registro exitoso
    resp1 = cliente.post("/api/auth/registro", json=payload)
    assert resp1.status_code == 201

    # Segundo registro con el mismo email
    resp2 = cliente.post("/api/auth/registro", json=payload)
    assert resp2.status_code == 409

    error = resp2.json()
    assert error["code"] == "EMAIL_YA_REGISTRADO"
    assert error["message"] == "El correo electrónico ya se encuentra registrado"
    assert error["detail"] is None


def test_registro_email_invalido(cliente: TestClient) -> None:
    """Verifica que un email con formato inválido sea rechazado con 422 por validación de Pydantic."""
    payload = {
        "nombre": "Jugador Test",
        "email": "formato-invalido-sin-arroba",
        "password": "passwordSeguro123",
    }

    respuesta = cliente.post("/api/auth/registro", json=payload)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "ERROR_VALIDACION"
    assert "detail" in cuerpo


def test_registro_password_vacio_o_corto(cliente: TestClient) -> None:
    """Verifica que una contraseña vacía o menor a 6 caracteres retorne 422."""
    # Contraseña vacía
    resp_vacio = cliente.post(
        "/api/auth/registro",
        json={"nombre": "Lautaro Martinez", "email": "lautaro@futbolquiz.com", "password": ""},
    )
    assert resp_vacio.status_code == 422
    assert resp_vacio.json()["code"] == "ERROR_VALIDACION"

    # Contraseña de menos de 6 caracteres
    resp_corta = cliente.post(
        "/api/auth/registro",
        json={"nombre": "Lautaro Martinez", "email": "lautaro@futbolquiz.com", "password": "123"},
    )
    assert resp_corta.status_code == 422
    assert resp_corta.json()["code"] == "ERROR_VALIDACION"


def test_registro_campos_faltantes(cliente: TestClient) -> None:
    """Verifica que la omisión de campos requeridos devuelva 422."""
    # Falta el nombre
    resp_sin_nombre = cliente.post(
        "/api/auth/registro",
        json={"email": "sinnombre@futbolquiz.com", "password": "passwordSeguro123"},
    )
    assert resp_sin_nombre.status_code == 422

    # Falta el password
    resp_sin_password = cliente.post(
        "/api/auth/registro",
        json={"nombre": "Sin Password", "email": "sinpass@futbolquiz.com"},
    )
    assert resp_sin_password.status_code == 422


def test_registro_persistencia_password_hasheada(cliente: TestClient, sesion_db: Session) -> None:
    """Verifica en la base de datos que la contraseña se haya guardado hasheada y nunca en texto plano."""
    password_plana = "miClaveUltraSecreta_99!"
    payload = {
        "nombre": "Angel Di Maria",
        "email": "fideo@futbolquiz.com",
        "password": password_plana,
    }

    respuesta = cliente.post("/api/auth/registro", json=payload)
    assert respuesta.status_code == 201

    usuario_db = sesion_db.query(Usuario).filter(Usuario.email == "fideo@futbolquiz.com").first()
    assert usuario_db is not None
    assert usuario_db.password_hash != password_plana
    assert usuario_db.password_hash.startswith("$2b$")
    assert verificar_password(password_plana, usuario_db.password_hash)


# ==============================================================================
# Pruebas Unitarias (Repositorio y Servicio)
# ==============================================================================


def test_usuario_repository_obtener_por_email_y_crear(sesion_db: Session) -> None:
    """Verifica las operaciones básicas de persistencia en usuario_repository."""
    assert usuario_repository.obtener_por_email(sesion_db, "inexistente@futbolquiz.com") is None

    nuevo = Usuario(
        nombre="Emiliano Martinez",
        email="dibu@futbolquiz.com",
        password_hash=hashear_password("atajadas123"),
        rol=RolUsuario.JUGADOR,
    )
    creado = usuario_repository.crear(sesion_db, nuevo)
    assert creado.id is not None

    encontrado = usuario_repository.obtener_por_email(sesion_db, "dibu@futbolquiz.com")
    assert encontrado is not None
    assert encontrado.id == creado.id
    assert encontrado.nombre == "Emiliano Martinez"


def test_usuario_service_hashear_y_verificar_password() -> None:
    """Verifica el correcto funcionamiento de las funciones de hasheo con bcrypt."""
    password = "claveDePrueba456"
    hash_generado = hashear_password(password)

    assert hash_generado != password
    assert hash_generado.startswith("$2b$")
    assert verificar_password(password, hash_generado) is True
    assert verificar_password("otraClaveIncorrecta", hash_generado) is False


def test_usuario_service_email_duplicado_lanza_excepcion(sesion_db: Session) -> None:
    """Verifica que el servicio lance EmailYaRegistradoError ante un email duplicado."""
    datos = UsuarioCreate(
        nombre="Rodrigo De Paul",
        email="depaul@futbolquiz.com",
        password="motorcitoDePaul7",
    )

    # Primer registro
    usuario_service.registrar_usuario(sesion_db, datos)

    # Segundo registro con el mismo email
    with pytest.raises(EmailYaRegistradoError) as exc_info:
        usuario_service.registrar_usuario(sesion_db, datos)

    assert exc_info.value.codigo == "EMAIL_YA_REGISTRADO"
    assert exc_info.value.codigo_estado == 409

