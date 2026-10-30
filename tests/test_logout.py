"""Pruebas unitarias y de integración para el endpoint de logout (POST /api/auth/logout)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.core.excepciones import TokenInvalidoError
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.models.token_revocado import TokenRevocado
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, usuario_service


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
    return autenticacion_service.generar_token_jwt(usuario_autenticado)


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


def test_token_revocado_no_puede_leer_ni_modificar_perfil(
    cliente: TestClient, token_valido: str, usuario_autenticado: Usuario, sesion_db: Session
) -> None:
    encabezados = {"Authorization": f"Bearer {token_valido}"}
    assert cliente.get("/api/usuarios/me", headers=encabezados).status_code == 200
    assert cliente.post("/api/auth/logout", headers=encabezados).status_code == 200

    assert cliente.get("/api/usuarios/me", headers=encabezados).status_code == 401
    respuesta = cliente.patch(
        "/api/usuarios/me", headers=encabezados, json={"nombre": "Cambio no autorizado"}
    )
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "TOKEN_INVALIDO"
    sesion_db.refresh(usuario_autenticado)
    assert usuario_autenticado.nombre == "Angel Di Maria"
    assert cliente.get("/api/ranking", headers=encabezados).status_code == 401
    assert cliente.post("/api/auth/logout", headers=encabezados).status_code == 401


def test_logout_no_revoca_otra_sesion_y_permite_nuevo_login(
    cliente: TestClient, usuario_autenticado: Usuario, token_valido: str
) -> None:
    otro_token = autenticacion_service.generar_token_jwt(usuario_autenticado)
    assert otro_token != token_valido
    assert cliente.post(
        "/api/auth/logout", headers={"Authorization": f"Bearer {token_valido}"}
    ).status_code == 200
    assert cliente.get(
        "/api/usuarios/me", headers={"Authorization": f"Bearer {otro_token}"}
    ).status_code == 200

    respuesta = cliente.post(
        "/api/auth/login",
        json={"email": usuario_autenticado.email, "password": "passwordFideo11"},
    )
    assert respuesta.status_code == 200
    nuevo_token = respuesta.json()["access_token"]
    assert nuevo_token not in {token_valido, otro_token}
    assert cliente.get(
        "/api/usuarios/me", headers={"Authorization": f"Bearer {nuevo_token}"}
    ).status_code == 200


def test_logout_revoca_tokens_anteriores_sin_jti(
    cliente: TestClient, usuario_autenticado: Usuario
) -> None:
    payload = autenticacion_service.decodificar_token_jwt(
        autenticacion_service.generar_token_jwt(usuario_autenticado)
    )
    del payload["jti"]
    token = jwt.encode(payload, CONFIGURACION.JWT_SECRET, algorithm=CONFIGURACION.JWT_ALGORITMO)
    encabezados = {"Authorization": f"Bearer {token}"}
    assert cliente.post("/api/auth/logout", headers=encabezados).status_code == 200
    assert cliente.get("/api/usuarios/me", headers=encabezados).status_code == 401


def test_padding_de_firma_no_permite_evitar_revocacion(
    cliente: TestClient, token_valido: str
) -> None:
    variante = token_valido + "=" * (-len(token_valido.rsplit(".", 1)[1]) % 4)
    encabezados_variante = {"Authorization": f"Bearer {variante}"}
    # Algunas versiones de PyJWT ya rechazan codificaciones no canónicas.
    assert autenticacion_service.obtener_huella_token(variante) == (
        autenticacion_service.obtener_huella_token(token_valido)
    )
    assert cliente.post(
        "/api/auth/logout", headers={"Authorization": f"Bearer {token_valido}"}
    ).status_code == 200
    assert cliente.get("/api/usuarios/me", headers=encabezados_variante).status_code == 401


def test_token_sin_vencimiento_es_rechazado(
    cliente: TestClient, usuario_autenticado: Usuario
) -> None:
    token = jwt.encode(
        {"sub": str(usuario_autenticado.id)},
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )
    encabezados = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/api/usuarios/me", headers=encabezados).status_code == 401
    assert cliente.post("/api/auth/logout", headers=encabezados).status_code == 401


def test_logout_limpia_solo_revocaciones_vencidas(
    cliente: TestClient, sesion_db: Session, token_valido: str
) -> None:
    ahora = int(datetime.now(timezone.utc).timestamp())
    sesion_db.add_all([
        TokenRevocado(huella="a" * 64, expira_en=ahora - 10),
        TokenRevocado(huella="b" * 64, expira_en=ahora + 3600),
    ])
    sesion_db.commit()
    assert cliente.post(
        "/api/auth/logout", headers={"Authorization": f"Bearer {token_valido}"}
    ).status_code == 200
    sesion_db.expire_all()
    assert sesion_db.get(TokenRevocado, "a" * 64) is None
    assert sesion_db.get(TokenRevocado, "b" * 64) is not None
    revocacion = sesion_db.get(
        TokenRevocado, autenticacion_service.obtener_huella_token(token_valido)
    )
    assert revocacion is not None
    assert revocacion.expira_en == autenticacion_service.decodificar_token_jwt(token_valido)["exp"]


def test_revocacion_persiste_al_recrear_motor_de_base_de_datos(
    tmp_path: Path, token_valido: str
) -> None:
    """Simula otro proceso con conexiones nuevas a la misma base persistente."""
    url = f"sqlite:///{(tmp_path / 'revocaciones.db').as_posix()}"
    motor = create_engine(url)
    TokenRevocado.__table__.create(motor)
    with Session(motor) as sesion:
        autenticacion_service.revocar_token(sesion, token_valido)
        # Dos cierres concurrentes que ya validaron el token pueden guardar lo mismo.
        autenticacion_service.revocar_token(sesion, token_valido)
        assert sesion.query(TokenRevocado).count() == 1
    motor.dispose()

    nuevo_motor = create_engine(url)
    try:
        with Session(nuevo_motor) as sesion:
            with pytest.raises(TokenInvalidoError):
                autenticacion_service.validar_token_no_revocado(sesion, token_valido)
    finally:
        nuevo_motor.dispose()


def test_logout_no_confirma_si_no_puede_persistir_revocacion(
    cliente: TestClient, sesion_db: Session, token_valido: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fallar_commit() -> None:
        raise RuntimeError("Base no disponible")

    monkeypatch.setattr(sesion_db, "commit", fallar_commit)
    with pytest.raises(RuntimeError, match="Base no disponible"):
        cliente.post("/api/auth/logout", headers={"Authorization": f"Bearer {token_valido}"})
    assert sesion_db.query(TokenRevocado).count() == 0

