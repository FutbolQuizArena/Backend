"""Pruebas para la gestión de usuarios en el panel de administración (Tarea 5.1.3 - Módulo 5)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.services import autenticacion_service, usuario_service


@pytest.fixture
def usuario_admin(sesion_db: Session) -> Usuario:
    """Crea un usuario administrador principal."""
    admin = Usuario(
        nombre="Admin Principal",
        email="admin.principal@futbolquiz.com",
        password_hash=usuario_service.hashear_password("adminSecret123"),
        rol=RolUsuario.ADMINISTRADOR,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def otro_admin(sesion_db: Session) -> Usuario:
    """Crea un segundo usuario con rol ADMINISTRADOR."""
    admin2 = Usuario(
        nombre="Segundo Admin",
        email="admin2@futbolquiz.com",
        password_hash=usuario_service.hashear_password("admin2Secret123"),
        rol=RolUsuario.ADMINISTRADOR,
    )
    return usuario_repository.crear(sesion_db, admin2)


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea un usuario regular con rol JUGADOR."""
    jugador = Usuario(
        nombre="Lionel Messi",
        email="messi@futbolquiz.com",
        password_hash=usuario_service.hashear_password("jugadorSecret123"),
        rol=RolUsuario.JUGADOR,
        puntaje_total=250,
    )
    return usuario_repository.crear(sesion_db, jugador)


@pytest.fixture
def headers_admin(usuario_admin: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para el administrador principal."""
    token = autenticacion_service.generar_token_jwt(usuario_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_jugador(usuario_jugador: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para un jugador común."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas de Autorización y Seguridad (RBAC)
# ==============================================================================


def test_admin_usuarios_sin_token_retorna_401(cliente: TestClient) -> None:
    """Cualquier endpoint de administración de usuarios sin token debe rechazar con 401."""
    resp_listar = cliente.get("/api/admin/usuarios")
    assert resp_listar.status_code == 401

    resp_detalle = cliente.get("/api/admin/usuarios/1")
    assert resp_detalle.status_code == 401

    resp_estado = cliente.patch("/api/admin/usuarios/1/estado", json={"esta_habilitado": False})
    assert resp_estado.status_code == 401


def test_admin_usuarios_con_rol_jugador_retorna_403(
    cliente: TestClient, headers_jugador: dict[str, str]
) -> None:
    """Un usuario con rol JUGADOR debe ser rechazado con 403 Forbidden."""
    resp_listar = cliente.get("/api/admin/usuarios", headers=headers_jugador)
    assert resp_listar.status_code == 403
    assert resp_listar.json()["code"] == "ACCESO_DENEGADO"

    resp_detalle = cliente.get("/api/admin/usuarios/1", headers=headers_jugador)
    assert resp_detalle.status_code == 403
    assert resp_detalle.json()["code"] == "ACCESO_DENEGADO"

    resp_estado = cliente.patch(
        "/api/admin/usuarios/1/estado",
        json={"esta_habilitado": False},
        headers=headers_jugador,
    )
    assert resp_estado.status_code == 403
    assert resp_estado.json()["code"] == "ACCESO_DENEGADO"


# ==============================================================================
# Pruebas de Listado y Filtros (GET /api/admin/usuarios)
# ==============================================================================


def test_listar_usuarios_como_admin(
    cliente: TestClient,
    headers_admin: dict[str, str],
    usuario_admin: Usuario,
    usuario_jugador: Usuario,
) -> None:
    """Listar todos los usuarios como admin devuelve 200 y los campos esperados sin exponer contraseñas."""
    resp = cliente.get("/api/admin/usuarios", headers=headers_admin)
    assert resp.status_code == 200

    datos = resp.json()
    assert isinstance(datos, list)
    assert len(datos) >= 2

    emails = [u["email"] for u in datos]
    assert usuario_admin.email in emails
    assert usuario_jugador.email in emails

    for usuario_data in datos:
        assert "id" in usuario_data
        assert "nombre" in usuario_data
        assert "email" in usuario_data
        assert "rol" in usuario_data
        assert "puntaje_total" in usuario_data
        assert "esta_habilitado" in usuario_data
        assert "fecha_alta" in usuario_data
        assert "password" not in usuario_data
        assert "password_hash" not in usuario_data


def test_listar_usuarios_filtro_buscar_nombre_y_email(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Filtro de búsqueda insensible a mayúsculas sobre nombre o correo."""
    u1 = Usuario(
        nombre="Enzo Fernandez",
        email="chelsea_enzo@futbolquiz.com",
        password_hash=usuario_service.hashear_password("pwd1"),
        rol=RolUsuario.JUGADOR,
    )
    u2 = Usuario(
        nombre="Alexis Mac Allister",
        email="liverpool_mac@futbolquiz.com",
        password_hash=usuario_service.hashear_password("pwd2"),
        rol=RolUsuario.JUGADOR,
    )
    sesion_db.add_all([u1, u2])
    sesion_db.commit()

    # Búsqueda por parte del nombre insensible a mayúsculas
    resp_nombre = cliente.get(
        "/api/admin/usuarios",
        params={"buscar": "eNzO"},
        headers=headers_admin,
    )
    assert resp_nombre.status_code == 200
    datos_nombre = resp_nombre.json()
    assert len(datos_nombre) == 1
    assert datos_nombre[0]["nombre"] == "Enzo Fernandez"

    # Búsqueda por correo electrónico
    resp_email = cliente.get(
        "/api/admin/usuarios",
        params={"buscar": "liverpool_mac"},
        headers=headers_admin,
    )
    assert resp_email.status_code == 200
    datos_email = resp_email.json()
    assert len(datos_email) == 1
    assert datos_email[0]["email"] == "liverpool_mac@futbolquiz.com"

    # Búsqueda sin coincidencias
    resp_vacio = cliente.get(
        "/api/admin/usuarios",
        params={"buscar": "termino_inexistente_xyz"},
        headers=headers_admin,
    )
    assert resp_vacio.status_code == 200
    assert resp_vacio.json() == []


def test_listar_usuarios_filtro_rol(
    cliente: TestClient,
    headers_admin: dict[str, str],
    usuario_admin: Usuario,
    usuario_jugador: Usuario,
) -> None:
    """Filtro por rol exacto (ADMINISTRADOR vs JUGADOR)."""
    resp_admin = cliente.get(
        "/api/admin/usuarios",
        params={"rol": "ADMINISTRADOR"},
        headers=headers_admin,
    )
    assert resp_admin.status_code == 200
    datos_admin = resp_admin.json()
    assert all(u["rol"] == "ADMINISTRADOR" for u in datos_admin)
    assert any(u["id"] == usuario_admin.id for u in datos_admin)
    assert not any(u["id"] == usuario_jugador.id for u in datos_admin)

    resp_jugador = cliente.get(
        "/api/admin/usuarios",
        params={"rol": "JUGADOR"},
        headers=headers_admin,
    )
    assert resp_jugador.status_code == 200
    datos_jugador = resp_jugador.json()
    assert all(u["rol"] == "JUGADOR" for u in datos_jugador)
    assert any(u["id"] == usuario_jugador.id for u in datos_jugador)
    assert not any(u["id"] == usuario_admin.id for u in datos_jugador)


def test_listar_usuarios_filtro_esta_habilitado(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Filtro booleano por estado de habilitación."""
    u_habilitado = Usuario(
        nombre="Jugador Habilitado",
        email="hab@futbolquiz.com",
        password_hash=usuario_service.hashear_password("pwd"),
        esta_habilitado=True,
    )
    u_deshabilitado = Usuario(
        nombre="Jugador Deshabilitado",
        email="deshab@futbolquiz.com",
        password_hash=usuario_service.hashear_password("pwd"),
        esta_habilitado=False,
    )
    sesion_db.add_all([u_habilitado, u_deshabilitado])
    sesion_db.commit()

    resp_hab = cliente.get(
        "/api/admin/usuarios",
        params={"esta_habilitado": True},
        headers=headers_admin,
    )
    assert resp_hab.status_code == 200
    datos_hab = resp_hab.json()
    assert all(u["esta_habilitado"] is True for u in datos_hab)
    assert any(u["email"] == "hab@futbolquiz.com" for u in datos_hab)
    assert not any(u["email"] == "deshab@futbolquiz.com" for u in datos_hab)

    resp_deshab = cliente.get(
        "/api/admin/usuarios",
        params={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp_deshab.status_code == 200
    datos_deshab = resp_deshab.json()
    assert all(u["esta_habilitado"] is False for u in datos_deshab)
    assert any(u["email"] == "deshab@futbolquiz.com" for u in datos_deshab)
    assert not any(u["email"] == "hab@futbolquiz.com" for u in datos_deshab)


# ==============================================================================
# Pruebas de Consulta por ID (GET /api/admin/usuarios/{id})
# ==============================================================================


def test_obtener_usuario_admin_existente(
    cliente: TestClient, headers_admin: dict[str, str], usuario_jugador: Usuario
) -> None:
    """Obtener un usuario existente por su ID devuelve 200 y sus datos completos."""
    resp = cliente.get(
        f"/api/admin/usuarios/{usuario_jugador.id}",
        headers=headers_admin,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == usuario_jugador.id
    assert data["nombre"] == usuario_jugador.nombre
    assert data["email"] == usuario_jugador.email
    assert data["rol"] == "JUGADOR"
    assert data["puntaje_total"] == 250
    assert data["esta_habilitado"] is True
    assert "password_hash" not in data


def test_obtener_usuario_admin_inexistente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Consultar un ID inexistente devuelve 404 con estructura estándar de error."""
    resp = cliente.get("/api/admin/usuarios/999999", headers=headers_admin)
    assert resp.status_code == 404
    error = resp.json()
    assert error["code"] == "RECURSO_NO_ENCONTRADO"
    assert "no encontrado" in error["message"].lower()


# ==============================================================================
# Pruebas de Cambio de Estado (PATCH /api/admin/usuarios/{id}/estado)
# ==============================================================================


def test_deshabilitar_jugador_activo(
    cliente: TestClient,
    headers_admin: dict[str, str],
    usuario_jugador: Usuario,
    sesion_db: Session,
) -> None:
    """Deshabilitar un jugador activo devuelve 200 y actualiza la entidad en BD."""
    resp = cliente.patch(
        f"/api/admin/usuarios/{usuario_jugador.id}/estado",
        json={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == usuario_jugador.id
    assert data["esta_habilitado"] is False

    # Verificar en base de datos
    sesion_db.refresh(usuario_jugador)
    assert usuario_jugador.esta_habilitado is False


def test_habilitar_jugador_previamente_deshabilitado(
    cliente: TestClient,
    headers_admin: dict[str, str],
    usuario_jugador: Usuario,
    sesion_db: Session,
) -> None:
    """Habilitar un jugador previamente deshabilitado devuelve 200 y actualiza la entidad en BD."""
    usuario_jugador.deshabilitar()
    sesion_db.commit()
    sesion_db.refresh(usuario_jugador)
    assert usuario_jugador.esta_habilitado is False

    resp = cliente.patch(
        f"/api/admin/usuarios/{usuario_jugador.id}/estado",
        json={"esta_habilitado": True},
        headers=headers_admin,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == usuario_jugador.id
    assert data["esta_habilitado"] is True

    # Verificar en base de datos
    sesion_db.refresh(usuario_jugador)
    assert usuario_jugador.esta_habilitado is True


def test_admin_auto_deshabilitacion_rechazada_con_400(
    cliente: TestClient, headers_admin: dict[str, str], usuario_admin: Usuario
) -> None:
    """Regla de seguridad: un administrador no puede deshabilitar su propia cuenta."""
    resp = cliente.patch(
        f"/api/admin/usuarios/{usuario_admin.id}/estado",
        json={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp.status_code == 400
    error = resp.json()
    assert error["code"] == "AUTO_DESHABILITACION_NO_PERMITIDA"
    assert "no puede deshabilitar su propia cuenta" in error["message"]


def test_admin_puede_modificar_estado_de_otro_admin(
    cliente: TestClient,
    headers_admin: dict[str, str],
    otro_admin: Usuario,
    sesion_db: Session,
) -> None:
    """Un administrador sí puede modificar el estado de otra cuenta de administrador."""
    resp = cliente.patch(
        f"/api/admin/usuarios/{otro_admin.id}/estado",
        json={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp.status_code == 200
    assert resp.json()["esta_habilitado"] is False

    sesion_db.refresh(otro_admin)
    assert otro_admin.esta_habilitado is False


def test_cambiar_estado_usuario_inexistente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Intentar cambiar estado de un usuario que no existe devuelve 404."""
    resp = cliente.patch(
        "/api/admin/usuarios/999999/estado",
        json={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp.status_code == 404
    error = resp.json()
    assert error["code"] == "RECURSO_NO_ENCONTRADO"


# ==============================================================================
# Pruebas de Regresión e Integración de Seguridad
# ==============================================================================


def test_regresion_seguridad_jugador_deshabilitado_pierde_acceso_y_lo_recupera(
    cliente: TestClient,
    headers_admin: dict[str, str],
    usuario_jugador: Usuario,
    headers_jugador: dict[str, str],
) -> None:
    """Verifica que un jugador deshabilitado no pueda usar endpoints protegidos y al ser rehabilitado recupere acceso."""
    # 1. Jugador activo accede a /api/usuarios/me exitosamente (200)
    resp_activo = cliente.get("/api/usuarios/me", headers=headers_jugador)
    assert resp_activo.status_code == 200
    assert resp_activo.json()["email"] == usuario_jugador.email

    # 2. El administrador lo deshabilita
    resp_deshab = cliente.patch(
        f"/api/admin/usuarios/{usuario_jugador.id}/estado",
        json={"esta_habilitado": False},
        headers=headers_admin,
    )
    assert resp_deshab.status_code == 200
    assert resp_deshab.json()["esta_habilitado"] is False

    # 3. El jugador intenta realizar una petición con su token previo -> 401
    resp_bloqueado = cliente.get("/api/usuarios/me", headers=headers_jugador)
    assert resp_bloqueado.status_code == 401
    assert resp_bloqueado.json()["code"] == "TOKEN_INVALIDO"

    # 4. El administrador reactiva al jugador
    resp_hab = cliente.patch(
        f"/api/admin/usuarios/{usuario_jugador.id}/estado",
        json={"esta_habilitado": True},
        headers=headers_admin,
    )
    assert resp_hab.status_code == 200
    assert resp_hab.json()["esta_habilitado"] is True

    # 5. El jugador vuelve a acceder con su token -> 200 OK
    resp_recuperado = cliente.get("/api/usuarios/me", headers=headers_jugador)
    assert resp_recuperado.status_code == 200
    assert resp_recuperado.json()["email"] == usuario_jugador.email
    assert resp_recuperado.json()["esta_habilitado"] is True


def test_metodos_dominio_habilitar_y_deshabilitar() -> None:
    """Verifica la mutación de estado encapsulada en la entidad de dominio Usuario."""
    usuario = Usuario(
        nombre="Test Encapsulamiento",
        email="encapsulado@futbolquiz.com",
        password_hash="hash",
        esta_habilitado=True,
    )
    assert usuario.esta_habilitado is True

    usuario.deshabilitar()
    assert usuario.esta_habilitado is False

    usuario.habilitar()
    assert usuario.esta_habilitado is True
