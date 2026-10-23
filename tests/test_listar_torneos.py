"""Pruebas de integración y unitarias para el endpoint de listado de torneos (GET /api/torneos)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo, RolUsuario
from app.models.usuario import Usuario
from app.schemas.torneo_schema import TorneoCreate, TorneoUnirseRequest
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, torneo_service, usuario_service


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def usuario_a(sesion_db: Session) -> Usuario:
    """Crea y persiste el usuario A."""
    datos = UsuarioCreate(
        nombre="Usuario Alpha",
        email="alpha@futbolquiz.com",
        password="claveAlpha123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_b(sesion_db: Session) -> Usuario:
    """Crea y persiste el usuario B."""
    datos = UsuarioCreate(
        nombre="Usuario Beta",
        email="beta@futbolquiz.com",
        password="claveBeta123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_c(sesion_db: Session) -> Usuario:
    """Crea y persiste el usuario C."""
    datos = UsuarioCreate(
        nombre="Usuario Gamma",
        email="gamma@futbolquiz.com",
        password="claveGamma123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


def auth_header(usuario: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para un usuario dado."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas del Endpoint GET /api/torneos
# ==============================================================================


def test_listar_torneos_filtro_mios(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que filtro=mios retorne solo los torneos donde el usuario es participante."""
    # Usuario A crea Torneo 1 (queda inscripto)
    t1 = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Propio A", cantidad_participantes=4),
        usuario_a,
    )
    # Usuario B crea Torneo 2 (A no participa)
    t2 = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Solo B", cantidad_participantes=4),
        usuario_b,
    )
    # Usuario B crea Torneo 3 y Usuario A se une
    t3 = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Compartido", cantidad_participantes=4),
        usuario_b,
    )
    torneo_service.unirse_a_torneo(
        sesion_db,
        TorneoUnirseRequest(codigo_acceso=t3.codigo_acceso),
        usuario_a,
    )

    respuesta = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))

    assert respuesta.status_code == 200
    datos = respuesta.json()

    ids_obtenidos = [t["id"] for t in datos]
    assert t1.id in ids_obtenidos
    assert t3.id in ids_obtenidos
    assert t2.id not in ids_obtenidos


def test_listar_torneos_default_es_mios(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que si no se provee el query param ?filtro, el comportamiento por defecto sea 'mios'."""
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Default A", cantidad_participantes=4),
        usuario_a,
    )
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Default B", cantidad_participantes=4),
        usuario_b,
    )

    resp_sin_param = cliente.get("/api/torneos", headers=auth_header(usuario_a))
    resp_con_mios = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))

    assert resp_sin_param.status_code == 200
    assert resp_sin_param.json() == resp_con_mios.json()


def test_listar_torneos_filtro_disponibles(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que filtro=disponibles solo devuelva torneos ESPERANDO_JUGADORES donde el usuario NO participa."""
    # Torneo de A: A es participante -> NO debe aparecer en disponibles de A
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo de A", cantidad_participantes=4),
        usuario_a,
    )
    # Torneo disponible de B: A no participa -> SÍ debe aparecer
    t_disp = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Abierto de B", cantidad_participantes=4),
        usuario_b,
    )

    respuesta = cliente.get("/api/torneos?filtro=disponibles", headers=auth_header(usuario_a))

    assert respuesta.status_code == 200
    datos = respuesta.json()
    ids_disponibles = [t["id"] for t in datos]

    assert t_disp.id in ids_disponibles
    # No debe aparecer el propio torneo de A
    for item in datos:
        assert item["creador_id"] != usuario_a.id
        assert item["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value


def test_listar_torneos_filtro_finalizados(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que filtro=finalizados solo devuelva torneos FINALIZADO donde el usuario fue participante."""
    # Torneo de A que finaliza
    t_fin_a = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Finalizado de A", cantidad_participantes=4),
        usuario_a,
    )
    t_fin_a.estado = EstadoTorneo.FINALIZADO
    sesion_db.commit()

    # Torneo de B que finaliza (sin A)
    t_fin_b = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Finalizado de B", cantidad_participantes=4),
        usuario_b,
    )
    t_fin_b.estado = EstadoTorneo.FINALIZADO
    sesion_db.commit()

    # Torneo en espera de A (no finalizado)
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo En Espera de A", cantidad_participantes=4),
        usuario_a,
    )

    respuesta = cliente.get("/api/torneos?filtro=finalizados", headers=auth_header(usuario_a))

    assert respuesta.status_code == 200
    datos = respuesta.json()
    ids_finalizados = [t["id"] for t in datos]

    assert t_fin_a.id in ids_finalizados
    assert t_fin_b.id not in ids_finalizados
    for item in datos:
        assert item["estado"] == EstadoTorneo.FINALIZADO.value


def test_tiene_contrasena_flag_seguro(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que tiene_contrasena sea True o False sin exponer nunca contrasena_acceso."""
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Sin Clave", cantidad_participantes=4),
        usuario_b,
    )
    torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Con Clave", cantidad_participantes=4, contrasena_acceso="secreta123"),
        usuario_b,
    )

    respuesta = cliente.get("/api/torneos?filtro=disponibles", headers=auth_header(usuario_a))
    assert respuesta.status_code == 200
    datos = respuesta.json()

    mapa = {t["nombre"]: t for t in datos}
    assert mapa["Torneo Sin Clave"]["tiene_contrasena"] is False
    assert mapa["Torneo Con Clave"]["tiene_contrasena"] is True

    for t in datos:
        assert "contrasena_acceso" not in t
        assert "contrasena" not in t


def test_codigo_acceso_solo_visible_para_el_creador(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
) -> None:
    """Verifica que el código de acceso solo se exponga para los torneos donde el usuario es el creador."""
    # A es creador
    t_creado_por_a = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Creado Por A", cantidad_participantes=4),
        usuario_a,
    )
    # B es creador y A se une
    t_creado_por_b = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Creado Por B", cantidad_participantes=4),
        usuario_b,
    )
    torneo_service.unirse_a_torneo(
        sesion_db,
        TorneoUnirseRequest(codigo_acceso=t_creado_por_b.codigo_acceso),
        usuario_a,
    )

    # Consulta como Usuario A en "mios"
    respuesta = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))
    assert respuesta.status_code == 200
    datos = respuesta.json()

    mapa = {t["id"]: t for t in datos}
    # En el torneo que creó A: codigo_acceso presente
    assert mapa[t_creado_por_a.id]["codigo_acceso"] == t_creado_por_a.codigo_acceso
    # En el torneo donde A solo es participante (creador es B): codigo_acceso es None
    assert mapa[t_creado_por_b.id]["codigo_acceso"] is None


def test_cantidad_participantes_actual_conteo_exacto(
    cliente: TestClient,
    sesion_db: Session,
    usuario_a: Usuario,
    usuario_b: Usuario,
    usuario_c: Usuario,
) -> None:
    """Verifica que cantidad_participantes_actual refleje el número exacto de inscriptos sin N+1."""
    t = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Conteo Exacto", cantidad_participantes=8),
        usuario_a,
    )

    # Recién creado: solo el creador (1 participante)
    r1 = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))
    assert r1.status_code == 200
    item = [x for x in r1.json() if x["id"] == t.id][0]
    assert item["cantidad_participantes_actual"] == 1
    assert item["cantidad_participantes"] == 8

    # Se une usuario B: 2 participantes
    torneo_service.unirse_a_torneo(
        sesion_db,
        TorneoUnirseRequest(codigo_acceso=t.codigo_acceso),
        usuario_b,
    )
    r2 = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))
    assert r2.status_code == 200
    item2 = [x for x in r2.json() if x["id"] == t.id][0]
    assert item2["cantidad_participantes_actual"] == 2

    # Se une usuario C: 3 participantes
    torneo_service.unirse_a_torneo(
        sesion_db,
        TorneoUnirseRequest(codigo_acceso=t.codigo_acceso),
        usuario_c,
    )
    r3 = cliente.get("/api/torneos?filtro=mios", headers=auth_header(usuario_a))
    assert r3.status_code == 200
    item3 = [x for x in r3.json() if x["id"] == t.id][0]
    assert item3["cantidad_participantes_actual"] == 3


def test_filtro_invalido_retorna_422(
    cliente: TestClient,
    usuario_a: Usuario,
) -> None:
    """Verifica que un valor no reconocido en ?filtro retorne HTTP 422 Unprocessable Content."""
    respuesta = cliente.get("/api/torneos?filtro=cualquiera", headers=auth_header(usuario_a))
    assert respuesta.status_code == 422


def test_listar_torneos_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica que acceder a /api/torneos sin token Bearer retorne HTTP 401 Unauthorized."""
    respuesta = cliente.get("/api/torneos")
    assert respuesta.status_code == 401

