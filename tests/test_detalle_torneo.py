"""Pruebas unitarias y de integración para el detalle, participantes y cuadro del torneo (GET /api/torneos/{torneo_id})."""

import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoCruce, EstadoTorneo, RolUsuario
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.schemas.torneo_schema import TorneoCreate, TorneoUnirseRequest
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, torneo_service, usuario_service


@pytest.mark.parametrize("origen", ["cache", "relaciones", "sin_usuario", "sin_relacion"])
def test_detalle_cuadro_con_ganador_y_datos_incompletos(monkeypatch: pytest.MonkeyPatch, origen: str) -> None:
    """Conserva jugadores, ganador y orden, incluso sin datos en la lista de participantes."""
    jugador_a = SimpleNamespace(id=10, usuario_id=1, usuario=SimpleNamespace(nombre="Creador"))
    jugador_b = SimpleNamespace(id=20, usuario_id=2, usuario=SimpleNamespace(nombre="Jugador"))
    torneo = SimpleNamespace(
        id=1, nombre="Copa", estado=EstadoTorneo.EN_CURSO, cantidad_participantes=4,
        creador_id=1, creador=jugador_a.usuario, codigo_acceso="COPA01",
        fecha_creacion=datetime.now(timezone.utc),
        participantes=[jugador_a, jugador_b] if origen == "cache" else [],
    )
    if origen == "sin_usuario":
        jugador_a.usuario = None
        jugador_b.usuario = None
    relacion_a = None if origen == "sin_relacion" else jugador_a
    relacion_b = None if origen == "sin_relacion" else jugador_b
    cruces = [
        SimpleNamespace(
            id=30, torneo_id=1, ronda=1, jugador_a_id=10, jugador_b_id=20,
            ganador_id=10, estado=EstadoCruce.JUGADO,
            jugador_a=relacion_a, jugador_b=relacion_b, ganador=relacion_a,
        ),
        SimpleNamespace(
            id=40, torneo_id=1, ronda=2, jugador_a_id=10, jugador_b_id=20,
            ganador_id=None, estado=EstadoCruce.PENDIENTE,
            jugador_a=relacion_a, jugador_b=relacion_b, ganador=None,
        ),
    ]
    repositorio = torneo_service.torneo_repository
    monkeypatch.setattr(repositorio, "obtener_por_id", lambda *args, **kwargs: torneo)
    monkeypatch.setattr(repositorio, "es_participante", lambda *args, **kwargs: False)
    monkeypatch.setattr(repositorio, "obtener_cruces_por_torneo", lambda *args, **kwargs: cruces)

    detalle = torneo_service.obtener_detalle_torneo(None, 1, SimpleNamespace(id=1))

    assert [cruce.id for cruce in detalle.cuadro] == [30, 40]
    assert detalle.cuadro[0].ganador_id == 10
    assert detalle.cuadro[1].ganador is None
    assert detalle.cantidad_participantes_actual == len(torneo.participantes)
    if origen in ("sin_usuario", "sin_relacion"):
        assert detalle.cuadro[0].jugador_a is None
        assert detalle.cuadro[0].jugador_b is None
        assert detalle.cuadro[0].ganador is None
    else:
        assert detalle.cuadro[0].jugador_a.nombre == "Creador"
        assert detalle.cuadro[0].jugador_a.es_creador is True
        assert detalle.cuadro[0].jugador_b.nombre == "Jugador"
        assert detalle.cuadro[0].jugador_b.es_creador is False
        assert detalle.cuadro[0].ganador == detalle.cuadro[0].jugador_a


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario creador del torneo."""
    datos = UsuarioCreate(
        nombre="Scaloni Creador",
        email="scaloni.detalle@futbolquiz.com",
        password="passwordScaloni123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_participante(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario que participará del torneo."""
    datos = UsuarioCreate(
        nombre="Messi Participante",
        email="messi.detalle@futbolquiz.com",
        password="passwordMessi123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_ajeno(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario que no es ni creador ni participante del torneo."""
    datos = UsuarioCreate(
        nombre="Usuario Ajeno",
        email="ajeno.detalle@futbolquiz.com",
        password="passwordAjeno123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


def auth_header(usuario: Usuario) -> dict[str, str]:
    """Genera el encabezado Authorization con Bearer JWT para un usuario."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


def crear_usuarios_adicionales(sesion_db: Session, cantidad: int, prefijo: str = "jugador") -> list[Usuario]:
    """Crea usuarios adicionales para completar los cupos del torneo."""
    usuarios = []
    for i in range(1, cantidad + 1):
        datos = UsuarioCreate(
            nombre=f"{prefijo}_{i}",
            email=f"{prefijo}_{i}@futbolquiz.com",
            password=f"passwordExtra{i}",
            rol=RolUsuario.JUGADOR,
        )
        usuarios.append(usuario_service.registrar_usuario(sesion_db, datos))
    return usuarios


# ==============================================================================
# Pruebas de Integración HTTP (GET /api/torneos/{torneo_id})
# ==============================================================================


def test_creador_consulta_torneo_esperando_jugadores_exitoso(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que el creador consulte su torneo en ESPERANDO_JUGADORES (200).

    El cuadro viene vacío, codigo_acceso presente, participantes correctos y es_creador True.
    """
    datos_crear = TorneoCreate(nombre="Copa America 2026", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    headers = auth_header(usuario_creador)
    respuesta = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["id"] == torneo.id
    assert datos["nombre"] == "Copa America 2026"
    assert datos["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value
    assert datos["cantidad_participantes"] == 4
    assert datos["cantidad_participantes_actual"] == 1
    assert datos["creador_id"] == usuario_creador.id
    assert datos["creador_nombre"] == usuario_creador.nombre
    assert datos["codigo_acceso"] == torneo.codigo_acceso
    assert "fecha_creacion" in datos

    # Cuadro vacío antes de completarse el cupo
    assert datos["cuadro"] == []

    # Lista de participantes contiene al creador
    assert len(datos["participantes"]) == 1
    part_0 = datos["participantes"][0]
    assert part_0["usuario_id"] == usuario_creador.id
    assert part_0["nombre"] == usuario_creador.nombre
    assert part_0["es_creador"] is True


def test_participante_consulta_torneo_esperando_jugadores(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    usuario_participante: Usuario,
) -> None:
    """Verifica que un participante regular consulte el torneo en ESPERANDO_JUGADORES con acceso concedido."""
    datos_crear = TorneoCreate(nombre="Torneo Relampago", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    # Inscribir al participante regular
    torneo_service.unirse_a_torneo(
        db=sesion_db,
        datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
        usuario_actual=usuario_participante,
    )

    headers = auth_header(usuario_participante)
    respuesta = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["cantidad_participantes_actual"] == 2
    assert datos["cuadro"] == []
    assert len(datos["participantes"]) == 2

    # Verificar que es_creador esté marcado correctamente para cada uno
    part_creador = next(p for p in datos["participantes"] if p["usuario_id"] == usuario_creador.id)
    assert part_creador["es_creador"] is True

    part_regular = next(p for p in datos["participantes"] if p["usuario_id"] == usuario_participante.id)
    assert part_regular["es_creador"] is False


def test_consulta_torneo_en_curso_trae_cuadro_con_cruces_y_ganador_null(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que un torneo EN_CURSO incluya el cuadro con cruces de ronda 1, ganador=null y PENDIENTE."""
    datos_crear = TorneoCreate(nombre="Torneo 4 Completo", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    # Inscribir 3 jugadores adicionales para completar cupo (4/4 -> EN_CURSO y cruces automáticos)
    otros_jugadores = crear_usuarios_adicionales(sesion_db, 3, prefijo="detalle_part")
    for jugador in otros_jugadores:
        torneo_service.unirse_a_torneo(
            db=sesion_db,
            datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            usuario_actual=jugador,
        )

    headers = auth_header(usuario_creador)
    respuesta = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert datos["estado"] == EstadoTorneo.EN_CURSO.value
    assert datos["cantidad_participantes_actual"] == 4

    # Cuadro contiene 2 cruces para cupo de 4
    cuadro = datos["cuadro"]
    assert len(cuadro) == 2

    # Validar atributos de cada cruce en el cuadro
    for cruce in cuadro:
        assert cruce["ronda"] == 1
        assert cruce["estado"] == EstadoCruce.PENDIENTE.value
        assert cruce["ganador"] is None
        assert cruce["ganador_id"] is None
        assert cruce["torneo_id"] == torneo.id

        # jugador_a y jugador_b deben tener estructura con datos de usuario
        assert cruce["jugador_a"] is not None
        assert "usuario_id" in cruce["jugador_a"]
        assert "nombre" in cruce["jugador_a"]

        assert cruce["jugador_b"] is not None
        assert "usuario_id" in cruce["jugador_b"]
        assert "nombre" in cruce["jugador_b"]


def test_usuario_no_participante_ni_creador_retorna_403(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    usuario_ajeno: Usuario,
) -> None:
    """Verifica que un usuario que no es creador ni participante reciba 403 Forbidden."""
    datos_crear = TorneoCreate(nombre="Torneo Privado", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    headers = auth_header(usuario_ajeno)
    respuesta = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)

    assert respuesta.status_code == 403
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "ACCESO_DENEGADO"
    assert "No tienes permisos" in cuerpo["message"]


def test_torneo_inexistente_retorna_404(
    cliente: TestClient,
    usuario_creador: Usuario,
) -> None:
    """Verifica que solicitar un torneo con ID inexistente retorne 404 Not Found."""
    headers = auth_header(usuario_creador)
    respuesta = cliente.get("/api/torneos/999999", headers=headers)

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["code"] in ["TORNEO_NO_DISPONIBLE", "RECURSO_NO_ENCONTRADO"]


def test_consulta_detalle_torneo_sin_token_retorna_401(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que consultar el detalle sin token de autenticación retorne 401 Unauthorized."""
    datos_crear = TorneoCreate(nombre="Torneo Sin Token", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    respuesta = cliente.get(f"/api/torneos/{torneo.id}")
    assert respuesta.status_code == 401


def test_consulta_detalle_torneo_token_invalido_retorna_401(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que un token inválido o corrupto retorne 401."""
    datos_crear = TorneoCreate(nombre="Torneo Token Falso", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    headers = {"Authorization": "Bearer token_completamente_invalido_xyz"}
    respuesta = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)
    assert respuesta.status_code == 401


def test_cantidad_participantes_actual_conteo_exacto_progresivo(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que cantidad_participantes_actual refleje el conteo real a medida que se inscriben."""
    datos_crear = TorneoCreate(nombre="Torneo Progresivo 8", cantidad_participantes=8)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)
    headers = auth_header(usuario_creador)

    # 1 participante (el creador)
    r1 = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)
    assert r1.json()["cantidad_participantes_actual"] == 1
    assert len(r1.json()["participantes"]) == 1

    # Inscribir 2 jugadores más
    jugadores = crear_usuarios_adicionales(sesion_db, 2, prefijo="prog")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            db=sesion_db,
            datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            usuario_actual=j,
        )

    # 3 participantes
    r2 = cliente.get(f"/api/torneos/{torneo.id}", headers=headers)
    assert r2.json()["cantidad_participantes_actual"] == 3
    assert len(r2.json()["participantes"]) == 3


def test_swagger_documentacion_detalle_torneo(cliente: TestClient) -> None:
    """Verifica que GET /api/torneos/{torneo_id} esté documentado en OpenAPI con 200, 401, 403, 404 y BearerAuth."""
    respuesta = cliente.get("/openapi.json")
    assert respuesta.status_code == 200
    schema = respuesta.json()

    assert "/api/torneos/{torneo_id}" in schema["paths"]
    op_get = schema["paths"]["/api/torneos/{torneo_id}"]["get"]

    assert op_get["summary"] == "Obtener estado, participantes y cuadro de un torneo"
    assert "200" in op_get["responses"]
    assert "401" in op_get["responses"]
    assert "403" in op_get["responses"]
    assert "404" in op_get["responses"]
    assert op_get["security"] == [{"BearerAuth": []}]
