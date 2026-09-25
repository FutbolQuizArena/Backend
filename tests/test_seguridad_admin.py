"""Pruebas de auditoría y restricción de endpoints administrativos (Tarea 5.1.4 - Módulo 5).

Audita el cumplimiento del Requerimiento No Funcional RNF-002:
'El acceso a los endpoints de administración debe estar restringido mediante
autenticación y autorización por rol (JWT).'
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
import jwt
from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.main import app
from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.services import autenticacion_service, usuario_service


# ==============================================================================
# Fixtures de Usuarios y Encabezados de Autenticación
# ==============================================================================


@pytest.fixture
def usuario_admin(sesion_db: Session) -> Usuario:
    """Crea un usuario administrador activo."""
    admin = Usuario(
        nombre="Super Admin Auditoria",
        email="super.admin.auditoria@futbolquiz.com",
        password_hash=usuario_service.hashear_password("superSecretAdmin123"),
        rol=RolUsuario.ADMINISTRADOR,
        esta_habilitado=True,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def admin_deshabilitado(sesion_db: Session) -> Usuario:
    """Crea un usuario con rol ADMINISTRADOR pero suspendido (esta_habilitado=False)."""
    admin_suspendido = Usuario(
        nombre="Admin Suspendido",
        email="admin.suspendido@futbolquiz.com",
        password_hash=usuario_service.hashear_password("passSuspendido123"),
        rol=RolUsuario.ADMINISTRADOR,
        esta_habilitado=False,
    )
    return usuario_repository.crear(sesion_db, admin_suspendido)


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea un usuario regular con rol JUGADOR activo."""
    jugador = Usuario(
        nombre="Jugador Regular Auditoria",
        email="jugador.auditoria@futbolquiz.com",
        password_hash=usuario_service.hashear_password("passJugador123"),
        rol=RolUsuario.JUGADOR,
        esta_habilitado=True,
    )
    return usuario_repository.crear(sesion_db, jugador)


@pytest.fixture
def headers_admin(usuario_admin: Usuario) -> dict[str, str]:
    """Genera encabezado Authorization con Bearer JWT de administrador activo."""
    token = autenticacion_service.generar_token_jwt(usuario_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_admin_deshabilitado(admin_deshabilitado: Usuario) -> dict[str, str]:
    """Genera encabezado Authorization con Bearer JWT de un administrador suspendido."""
    token = autenticacion_service.generar_token_jwt(admin_deshabilitado)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_jugador(usuario_jugador: Usuario) -> dict[str, str]:
    """Genera encabezado Authorization con Bearer JWT de un jugador regular."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_token_invalido() -> dict[str, str]:
    """Genera encabezado Authorization con token corrupto o con firma inválida."""
    return {"Authorization": "Bearer token_corrupto_invalido_firma_falsa_xyz"}


@pytest.fixture
def headers_token_expirado(usuario_admin: Usuario) -> dict[str, str]:
    """Genera encabezado Authorization con token JWT cuya fecha de expiración ya venció."""
    ahora = datetime.now(timezone.utc)
    payload_expirado = {
        "sub": str(usuario_admin.id),
        "id": usuario_admin.id,
        "email": usuario_admin.email,
        "rol": usuario_admin.rol.value,
        "iat": ahora - timedelta(hours=3),
        "exp": ahora - timedelta(hours=1),
    }
    token = jwt.encode(
        payload_expirado,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_usuario_inexistente() -> dict[str, str]:
    """Genera encabezado Authorization con token JWT válido pero cuyo ID no existe en BD."""
    ahora = datetime.now(timezone.utc)
    payload_fantasma = {
        "sub": "999999",
        "id": 999999,
        "email": "fantasma@futbolquiz.com",
        "rol": RolUsuario.ADMINISTRADOR.value,
        "iat": ahora,
        "exp": ahora + timedelta(hours=1),
    }
    token = jwt.encode(
        payload_fantasma,
        CONFIGURACION.JWT_SECRET,
        algorithm=CONFIGURACION.JWT_ALGORITMO,
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Helper para descubrir y resolver dinámicamente las rutas administrativas
# ==============================================================================


def obtener_operaciones_admin() -> list[tuple[str, str]]:
    """Extrae dinámicamente todas las combinaciones (metodo, path) registradas bajo /api/admin."""
    schema = app.openapi()
    operaciones = []
    for path, path_item in schema.get("paths", {}).items():
        if path.startswith("/api/admin"):
            for metodo in path_item.keys():
                if metodo.lower() in ("get", "post", "patch", "delete", "put"):
                    operaciones.append((metodo.upper(), path))
    return sorted(operaciones)


def resolver_path_admin(path: str) -> str:
    """Reemplaza parámetros de ruta dinámicos ({id}) por un valor numérico dummy para peticiones HTTP."""
    return (
        path.replace("{pregunta_id}", "1")
        .replace("{categoria_id}", "1")
        .replace("{usuario_id}", "1")
    )


# ==============================================================================
# Matriz de Seguridad Dinámica sobre todos los endpoints de administración
# ==============================================================================


def test_auditoria_total_operaciones_admin_registradas() -> None:
    """Verifica que el sistema exponga las 16 operaciones administrativas esperadas."""
    operaciones = obtener_operaciones_admin()
    assert len(operaciones) == 16, f"Se esperaban 16 operaciones admin, se encontraron {len(operaciones)}: {operaciones}"


def test_auditoria_endpoints_admin_sin_token_retorna_401(cliente: TestClient) -> None:
    """Regla: Toda petición a cualquier endpoint bajo /api/admin sin token debe responder 401."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url)
        assert resp.status_code == 401, f"Fallo en {metodo} {url}: esperaba 401 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "TOKEN_INVALIDO"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_token_invalido_retorna_401(
    cliente: TestClient, headers_token_invalido: dict[str, str]
) -> None:
    """Regla: Petición con token malformado o firma apócrifa debe responder 401 TOKEN_INVALIDO."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_token_invalido)
        assert resp.status_code == 401, f"Fallo en {metodo} {url}: esperaba 401 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "TOKEN_INVALIDO"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_token_expirado_retorna_401(
    cliente: TestClient, headers_token_expirado: dict[str, str]
) -> None:
    """Regla: Petición con token expirado debe responder 401 TOKEN_INVALIDO."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_token_expirado)
        assert resp.status_code == 401, f"Fallo en {metodo} {url}: esperaba 401 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "TOKEN_INVALIDO"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_usuario_inexistente_retorna_401(
    cliente: TestClient, headers_usuario_inexistente: dict[str, str]
) -> None:
    """Regla: Petición con token de usuario eliminado o inexistente en BD debe responder 401 TOKEN_INVALIDO."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_usuario_inexistente)
        assert resp.status_code == 401, f"Fallo en {metodo} {url}: esperaba 401 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "TOKEN_INVALIDO"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_administrador_deshabilitado_retorna_401(
    cliente: TestClient, headers_admin_deshabilitado: dict[str, str]
) -> None:
    """Regla crítica: Un usuario con rol ADMINISTRADOR pero suspendido (esta_habilitado=False) debe ser rechazado con 401."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_admin_deshabilitado)
        assert resp.status_code == 401, f"Fallo en {metodo} {url}: esperaba 401 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "TOKEN_INVALIDO"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_rol_jugador_retorna_403(
    cliente: TestClient, headers_jugador: dict[str, str]
) -> None:
    """Regla RBAC: Un usuario con rol JUGADOR autenticado debe recibir 403 ACCESO_DENEGADO en todos los endpoints admin."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_jugador)
        assert resp.status_code == 403, f"Fallo en {metodo} {url}: esperaba 403 y recibio {resp.status_code}"
        cuerpo = resp.json()
        assert cuerpo["code"] == "ACCESO_DENEGADO"
        assert cuerpo["message"] == "No tenés permisos para realizar esta acción"
        assert cuerpo["detail"] is None


def test_auditoria_endpoints_admin_administrador_activo_permite_acceso(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Regla: Un administrador activo autenticado supera la barrera RBAC (no recibe 401 ni 403)."""
    for metodo, path in obtener_operaciones_admin():
        url = resolver_path_admin(path)
        resp = cliente.request(metodo, url, headers=headers_admin)
        # Puede dar 200, 201, 400, 404 o 422 según parámetros/cuerpo, pero JAMÁS 401 ni 403
        assert resp.status_code not in (401, 403), (
            f"Fallo en {metodo} {url}: la barrera de seguridad bloqueo al administrador con {resp.status_code}"
        )


# ==============================================================================
# Pruebas de Integridad de Respuestas y Documentación OpenAPI
# ==============================================================================


def test_auditoria_openapi_rutas_admin_poseen_bearer_auth(cliente: TestClient) -> None:
    """Verifica que todas las operaciones administrativas bajo /api/admin en OpenAPI expongan BearerAuth y el tag Administración."""
    resp = cliente.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()

    # Verificar componentes de seguridad
    components = schema.get("components", {})
    assert "securitySchemes" in components
    assert "BearerAuth" in components["securitySchemes"]
    assert components["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"

    paths = schema.get("paths", {})
    rutas_admin_encontradas = 0

    for path, path_item in paths.items():
        if path.startswith("/api/admin"):
            for metodo, operacion in path_item.items():
                if isinstance(operacion, dict):
                    rutas_admin_encontradas += 1
                    # Verificar BearerAuth
                    assert "security" in operacion, f"Falta security en {metodo.upper()} {path}"
                    assert operacion["security"] == [{"BearerAuth": []}], f"Security incorrecto en {metodo.upper()} {path}"

                    # Verificar tag Administración
                    assert "tags" in operacion, f"Faltan tags en {metodo.upper()} {path}"
                    assert "Administración" in operacion["tags"], f"Falta tag Administración en {metodo.upper()} {path}"

                    # Verificar respuestas 401 y 403 documentadas
                    responses = operacion.get("responses", {})
                    assert "401" in responses, f"Falta respuesta 401 en {metodo.upper()} {path}"
                    assert "403" in responses, f"Falta respuesta 403 en {metodo.upper()} {path}"

    assert rutas_admin_encontradas == 16


def test_auditoria_detalles_sensibles_no_expuestos(
    cliente: TestClient, headers_token_invalido: dict[str, str], headers_jugador: dict[str, str]
) -> None:
    """Verifica que ningún error de autorización o autenticación exponga stacktraces ni detalles internos."""
    url = "/api/admin/categorias"

    # Prueba 401
    resp_401 = cliente.get(url, headers=headers_token_invalido)
    assert resp_401.status_code == 401
    assert resp_401.json()["detail"] is None

    # Prueba 403
    resp_403 = cliente.get(url, headers=headers_jugador)
    assert resp_403.status_code == 403
    assert resp_403.json()["detail"] is None
