"""Pruebas unitarias y de integración para la edición de perfil de usuario (PATCH /api/usuarios/me)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import EmailYaRegistradoError
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioCreate
from app.services import auth_service, usuario_service


# ==============================================================================
# Fixtures auxiliares de prueba
# ==============================================================================


@pytest.fixture
def usuario_principal(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario principal de prueba."""
    datos = UsuarioCreate(
        nombre="Lionel Messi",
        email="messi.perfil@futbolquiz.com",
        password="passwordMessi10",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_secundario(sesion_db: Session) -> Usuario:
    """Crea y persiste un segundo usuario para verificar conflictos de email."""
    datos = UsuarioCreate(
        nombre="Angel Di Maria",
        email="dimaria.perfil@futbolquiz.com",
        password="passwordFideo11",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


# ==============================================================================
# Pruebas Unitarias del Modelo y Servicio
# ==============================================================================


def test_modelo_usuario_actualizar_perfil() -> None:
    """Verifica que el método de instancia Usuario.actualizar_perfil() actualice nombre y email in-place."""
    usuario = Usuario(
        nombre="Nombre Original",
        email="original@futbolquiz.com",
        password_hash="hash_mock",
        rol=RolUsuario.JUGADOR,
    )

    usuario.actualizar_perfil(nombre="Nombre Nuevo", email="nuevo@futbolquiz.com")

    assert usuario.nombre == "Nombre Nuevo"
    assert usuario.email == "nuevo@futbolquiz.com"


def test_servicio_actualizar_perfil_exitoso(
    sesion_db: Session,
    usuario_principal: Usuario,
) -> None:
    """Verifica que actualizar_perfil_usuario persista los cambios en la base de datos."""
    usuario_modificado = usuario_service.actualizar_perfil_usuario(
        db=sesion_db,
        usuario_actual=usuario_principal,
        nombre="Lionel Andres Messi",
        email="leo.messi.nuevo@futbolquiz.com",
    )

    assert usuario_modificado.id == usuario_principal.id
    assert usuario_modificado.nombre == "Lionel Andres Messi"
    assert usuario_modificado.email == "leo.messi.nuevo@futbolquiz.com"


def test_servicio_actualizar_perfil_email_duplicado_lanza_excepcion(
    sesion_db: Session,
    usuario_principal: Usuario,
    usuario_secundario: Usuario,
) -> None:
    """Verifica que el servicio lance EmailYaRegistradoError si el email nuevo ya pertenece a otro usuario."""
    with pytest.raises(EmailYaRegistradoError) as exc_info:
        usuario_service.actualizar_perfil_usuario(
            db=sesion_db,
            usuario_actual=usuario_principal,
            nombre="Lionel Messi",
            email=usuario_secundario.email,
        )

    assert exc_info.value.codigo == "EMAIL_YA_REGISTRADO"
    assert exc_info.value.codigo_estado == 409


# ==============================================================================
# Pruebas de Integración (Endpoint PATCH /api/usuarios/me)
# ==============================================================================


def test_edicion_perfil_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica que intentar editar el perfil sin token Bearer retorne 401 Unauthorized."""
    payload = {
        "nombre": "Nombre Sin Token",
        "email": "sin.token@futbolquiz.com",
    }

    respuesta = cliente.patch("/api/usuarios/me", json=payload)

    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert "code" in cuerpo
    assert cuerpo["code"] in ["TOKEN_INVALIDO", "ERROR_HTTP_401"]


def test_edicion_perfil_con_token_valido_exitoso(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica que un usuario autenticado actualice su perfil correctamente (HTTP 200).

    Verifica que la respuesta contenga nombre y email modificados y que NO exponga password_hash ni password.
    """
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Leo Messi Capitán",
        "email": "capitan10@futbolquiz.com",
    }

    respuesta = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json=payload,
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["id"] == usuario_principal.id
    assert datos["nombre"] == "Leo Messi Capitán"
    assert datos["email"] == "capitan10@futbolquiz.com"
    assert datos["rol"] == "JUGADOR"
    assert "password_hash" not in datos
    assert "password" not in datos


def test_edicion_perfil_mismo_email_propio_exitoso(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica que modificar solo el nombre manteniendo el mismo email no cause conflicto (HTTP 200)."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Lionel Messi Solo Nombre",
        "email": usuario_principal.email,
    }

    respuesta = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json=payload,
    )

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["nombre"] == "Lionel Messi Solo Nombre"
    assert datos["email"] == usuario_principal.email


def test_edicion_perfil_email_en_uso_por_otro_usuario_retorna_409(
    cliente: TestClient,
    usuario_principal: Usuario,
    usuario_secundario: Usuario,
) -> None:
    """Verifica que intentar cambiar el email a uno ya utilizado por otro usuario retorne 409 Conflict."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Lionel Messi",
        "email": usuario_secundario.email,
    }

    respuesta = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json=payload,
    )

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "EMAIL_YA_REGISTRADO"
    assert cuerpo["message"] == "El correo electrónico ya se encuentra registrado"
    assert cuerpo["detail"] is None


def test_edicion_perfil_body_invalido_retorna_422(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica que datos mal formados (email inválido, campos vacíos o faltantes) retornen 422."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    # Email sin formato válido
    resp_email_invalido = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json={"nombre": "Nuevo Nombre", "email": "formato-invalido-sin-arroba"},
    )
    assert resp_email_invalido.status_code == 422
    assert resp_email_invalido.json()["code"] == "ERROR_VALIDACION"

    # Nombre vacío
    resp_nombre_vacio = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json={"nombre": "", "email": "valido@futbolquiz.com"},
    )
    assert resp_nombre_vacio.status_code == 422
    assert resp_nombre_vacio.json()["code"] == "ERROR_VALIDACION"

    # Campo email faltante
    resp_sin_email = cliente.patch(
        "/api/usuarios/me",
        headers=encabezados,
        json={"nombre": "Solo Nombre"},
    )
    assert resp_sin_email.status_code == 422
    assert resp_sin_email.json()["code"] == "ERROR_VALIDACION"


def test_edicion_perfil_con_cambio_password_exitoso(
    cliente: TestClient,
    sesion_db: Session,
    usuario_principal: Usuario,
) -> None:
    """Verifica cambio de contraseña exitoso desde el formulario general (PATCH /api/usuarios/me)."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Lionel Messi",
        "email": usuario_principal.email,
        "password_actual": "passwordMessi10",
        "nueva_password": "nuevaPasswordSegura123",
    }

    respuesta = cliente.patch("/api/usuarios/me", headers=encabezados, json=payload)
    assert respuesta.status_code == 200

    sesion_db.refresh(usuario_principal)
    assert usuario_principal.autenticar("nuevaPasswordSegura123") is True
    assert usuario_principal.autenticar("passwordMessi10") is False


def test_edicion_perfil_con_password_actual_incorrecta_retorna_401(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica 401 si la contraseña actual provista es incorrecta en PATCH /api/usuarios/me."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Lionel Messi",
        "email": usuario_principal.email,
        "password_actual": "contraseñaTotalmenteErronea",
        "nueva_password": "nuevaPasswordSegura123",
    }

    respuesta = cliente.patch("/api/usuarios/me", headers=encabezados, json=payload)
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "CREDENCIALES_INVALIDAS"


def test_edicion_perfil_nueva_password_sin_password_actual_retorna_422(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica 422 si se envía nueva_password sin proporcionar password_actual."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "nombre": "Lionel Messi",
        "email": usuario_principal.email,
        "nueva_password": "nuevaPasswordSegura123",
    }

    respuesta = cliente.patch("/api/usuarios/me", headers=encabezados, json=payload)
    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "ERROR_VALIDACION"


def test_modal_cambio_password_exitoso(
    cliente: TestClient,
    sesion_db: Session,
    usuario_principal: Usuario,
) -> None:
    """Verifica cambio de contraseña exitoso desde el endpoint del modal (PATCH /api/usuarios/me/password)."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "password_actual": "passwordMessi10",
        "nueva_password": "passwordModalSuper123",
    }

    respuesta = cliente.patch("/api/usuarios/me/password", headers=encabezados, json=payload)
    assert respuesta.status_code == 200

    sesion_db.refresh(usuario_principal)
    assert usuario_principal.autenticar("passwordModalSuper123") is True


def test_modal_cambio_password_erroneo_retorna_401(
    cliente: TestClient,
    usuario_principal: Usuario,
) -> None:
    """Verifica 401 si la contraseña actual provista en el modal es incorrecta."""
    token = auth_service.generar_token_jwt(usuario_principal)
    encabezados = {"Authorization": f"Bearer {token}"}

    payload = {
        "password_actual": "claveIncorrecta",
        "nueva_password": "passwordModalSuper123",
    }

    respuesta = cliente.patch("/api/usuarios/me/password", headers=encabezados, json=payload)
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "CREDENCIALES_INVALIDAS"


def test_modal_cambio_password_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica 401 si se intenta llamar al endpoint del modal sin token."""
    payload = {
        "password_actual": "passwordMessi10",
        "nueva_password": "passwordModalSuper123",
    }

    respuesta = cliente.patch("/api/usuarios/me/password", json=payload)
    assert respuesta.status_code == 401

