"""Pruebas de integración y unitarias para el endpoint de ingreso a torneo (POST /api/torneos/unirse)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo, RolUsuario
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.schemas.torneo_schema import TorneoCreate
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, torneo_service, usuario_service


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario creador del torneo."""
    datos = UsuarioCreate(
        nombre="Creador Torneo",
        email="creador@futbolquiz.com",
        password="claveCreador123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def jugador_1(sesion_db: Session) -> Usuario:
    """Crea y persiste el primer jugador que intentará unirse."""
    datos = UsuarioCreate(
        nombre="Julian Alvarez",
        email="julian@futbolquiz.com",
        password="claveJulian123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def jugador_2(sesion_db: Session) -> Usuario:
    """Crea y persiste un segundo jugador que intentará unirse."""
    datos = UsuarioCreate(
        nombre="Enzo Fernandez",
        email="enzo@futbolquiz.com",
        password="claveEnzo123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def jugador_3(sesion_db: Session) -> Usuario:
    """Crea y persiste un tercer jugador que intentará unirse."""
    datos = UsuarioCreate(
        nombre="Alexis Mac Allister",
        email="alexis@futbolquiz.com",
        password="claveAlexis123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


def auth_header(usuario: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para un usuario dado."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas del Endpoint POST /api/torneos/unirse
# ==============================================================================


def test_unirse_torneo_sin_contrasena_exitoso(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que un usuario se una exitosamente a un torneo abierto sin contraseña (HTTP 200)."""
    datos_crear = TorneoCreate(
        nombre="Copa Abierta",
        cantidad_participantes=4,
    )
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {"codigo_acceso": torneo.codigo_acceso}
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["id"] == torneo.id
    assert datos["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value

    # Verificar persistencia en base de datos
    participacion = (
        sesion_db.query(ParticipanteTorneo)
        .filter_by(torneo_id=torneo.id, usuario_id=jugador_1.id)
        .first()
    )
    assert participacion is not None
    assert participacion.usuario_id == jugador_1.id
    assert participacion.torneo_id == torneo.id


def test_unirse_torneo_con_contrasena_correcta_exitoso(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que un usuario se una a un torneo privado proporcionando la contraseña correcta (HTTP 200)."""
    datos_crear = TorneoCreate(
        nombre="Copa Privada VIP",
        cantidad_participantes=4,
        contrasena_acceso="clavePrivada123",
    )
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {
        "codigo_acceso": torneo.codigo_acceso,
        "contrasena": "clavePrivada123",
    }
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["id"] == torneo.id
    assert "contrasena_acceso" not in datos


def test_unirse_torneo_con_contrasena_incorrecta_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que ingresar una contraseña errónea retorne HTTP 400 Bad Request."""
    datos_crear = TorneoCreate(
        nombre="Copa Secreta",
        cantidad_participantes=4,
        contrasena_acceso="claveReal456",
    )
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {
        "codigo_acceso": torneo.codigo_acceso,
        "contrasena": "claveCompletamenteErronea",
    }
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TORNEO_NO_DISPONIBLE"


def test_unirse_torneo_sin_contrasena_cuando_es_privado_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que no enviar contraseña en un torneo que sí la requiere retorne HTTP 400."""
    datos_crear = TorneoCreate(
        nombre="Copa con Clave",
        cantidad_participantes=4,
        contrasena_acceso="claveRequerida",
    )
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {"codigo_acceso": torneo.codigo_acceso}
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "TORNEO_NO_DISPONIBLE"


def test_unirse_torneo_codigo_inexistente_retorna_400(
    cliente: TestClient,
    jugador_1: Usuario,
) -> None:
    """Verifica que intentar unirse con un código que no existe en BD retorne HTTP 400."""
    payload = {"codigo_acceso": "CODNOEXISTE"}
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TORNEO_NO_DISPONIBLE"


def test_unirse_mismo_usuario_dos_veces_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que un usuario no pueda unirse dos veces al mismo torneo (retorna HTTP 400 controlado)."""
    datos_crear = TorneoCreate(nombre="Torneo Unicidad", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {"codigo_acceso": torneo.codigo_acceso}

    # Primera vez: exitoso
    resp1 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))
    assert resp1.status_code == 200

    # Segunda vez: rechazo 400
    resp2 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))
    assert resp2.status_code == 400
    assert resp2.json()["code"] == "TORNEO_NO_DISPONIBLE"


def test_creador_no_puede_reunirse_a_su_propio_torneo(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que el creador (que ya está inscripto automáticamente) reciba 400 si intenta unirse."""
    datos_crear = TorneoCreate(nombre="Torneo Creador Join", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    payload = {"codigo_acceso": torneo.codigo_acceso}
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(usuario_creador))

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "TORNEO_NO_DISPONIBLE"


def test_unirse_torneo_ya_completo_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
    jugador_2: Usuario,
    jugador_3: Usuario,
) -> None:
    """Verifica que cuando el torneo alcanzó su cupo, cualquier intento posterior retorne HTTP 400."""
    # Torneo de 4 participantes: creador + 3 jugadores
    datos_crear = TorneoCreate(nombre="Torneo Cupo Completo", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)
    payload = {"codigo_acceso": torneo.codigo_acceso}

    # Inscribir jugador 1 (2/4)
    r1 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))
    assert r1.status_code == 200

    # Inscribir jugador 2 (3/4)
    r2 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_2))
    assert r2.status_code == 200

    # Inscribir jugador 3 (4/4 -> torneo se completa)
    r3 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_3))
    assert r3.status_code == 200
    assert r3.json()["estado"] == EstadoTorneo.EN_CURSO.value

    # Intentar un quinto jugador (un cuarto usuario nuevo)
    datos_extra = UsuarioCreate(nombre="Extra", email="extra@futbolquiz.com", password="passwordExtra123")
    usuario_extra = usuario_service.registrar_usuario(sesion_db, datos_extra)

    r_extra = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(usuario_extra))
    assert r_extra.status_code == 400
    assert r_extra.json()["code"] == "TORNEO_NO_DISPONIBLE"


def test_unirse_torneo_no_esperando_jugadores_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
) -> None:
    """Verifica que intentar unirse a un torneo que ya está EN_CURSO o FINALIZADO retorne HTTP 400."""
    datos_crear = TorneoCreate(nombre="Torneo Ya En Curso", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    # Forzar estado EN_CURSO manualmente
    torneo.estado = EstadoTorneo.EN_CURSO
    sesion_db.commit()

    payload = {"codigo_acceso": torneo.codigo_acceso}
    respuesta = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))

    assert respuesta.status_code == 400
    assert respuesta.json()["code"] == "TORNEO_NO_DISPONIBLE"


def test_torneo_pasa_automaticamente_a_en_curso_al_completar_cupo(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    jugador_1: Usuario,
    jugador_2: Usuario,
    jugador_3: Usuario,
) -> None:
    """Verifica que el último participante en ingresar active la transición a EN_CURSO (Pasos 22-23)."""
    datos_crear = TorneoCreate(nombre="Torneo Transicion", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)
    payload = {"codigo_acceso": torneo.codigo_acceso}

    # Jugador 1: 2/4 participantes -> Sigue ESPERANDO_JUGADORES
    r1 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_1))
    assert r1.status_code == 200
    assert r1.json()["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value

    # Jugador 2: 3/4 participantes -> Sigue ESPERANDO_JUGADORES
    r2 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_2))
    assert r2.status_code == 200
    assert r2.json()["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value

    # Jugador 3: 4/4 participantes -> Transiciona automáticamente a EN_CURSO
    r3 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugador_3))
    assert r3.status_code == 200
    assert r3.json()["estado"] == EstadoTorneo.EN_CURSO.value

    # Verificar en base de datos
    torneo_en_bd = sesion_db.query(Torneo).filter_by(id=torneo.id).first()
    assert torneo_en_bd.estado == EstadoTorneo.EN_CURSO


def test_unirse_torneo_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica que intentar unirse sin encabezado Authorization retorne HTTP 401 Unauthorized."""
    payload = {"codigo_acceso": "ABC123"}
    respuesta = cliente.post("/api/torneos/unirse", json=payload)
    assert respuesta.status_code == 401

