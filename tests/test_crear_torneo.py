"""Pruebas de integración y unitarias para el endpoint de creación de torneo (POST /api/torneos)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import EstadoTorneo, RolUsuario
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, usuario_service
from app.services.usuario_service import verificar_password


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario creador de torneos."""
    datos = UsuarioCreate(
        nombre="Lionel Scaloni",
        email="scaloni.dt@futbolquiz.com",
        password="claveSeguraDT123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def headers_autorizacion(usuario_creador: Usuario) -> dict[str, str]:
    """Genera encabezados con token Bearer válido para el usuario creador."""
    token = autenticacion_service.generar_token_jwt(usuario_creador)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas del Endpoint POST /api/torneos
# ==============================================================================


def test_crear_torneo_sin_contrasena_exitoso(
    cliente: TestClient,
    usuario_creador: Usuario,
    headers_autorizacion: dict[str, str],
) -> None:
    """Verifica la creación exitosa de un torneo abierto sin contraseña (HTTP 201)."""
    payload = {
        "nombre": "Copa del Mundo Trivia",
        "cantidad_participantes": 8,
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)

    assert respuesta.status_code == 201
    datos = respuesta.json()

    assert datos["id"] is not None
    assert datos["nombre"] == "Copa del Mundo Trivia"
    assert datos["cantidad_participantes"] == 8
    assert datos["estado"] == EstadoTorneo.ESPERANDO_JUGADORES.value
    assert datos["creador_id"] == usuario_creador.id
    assert "fecha_creacion" in datos

    # Verificación del código de acceso
    codigo = datos["codigo_acceso"]
    assert isinstance(codigo, str)
    assert len(codigo) == 6
    assert codigo.isalnum()
    assert codigo.isupper()

    # Seguridad: nunca debe exponerse contrasena_acceso
    assert "contrasena_acceso" not in datos
    assert "contrasena" not in datos


def test_crear_torneo_con_contrasena_exitoso_y_seguro(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    headers_autorizacion: dict[str, str],
) -> None:
    """Verifica creación de torneo privado con contraseña: no se expone en response y se hashea en BD."""
    payload = {
        "nombre": "Torneo Privado Amigos",
        "cantidad_participantes": 4,
        "contrasena_acceso": "claveSuperSecreta2026",
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)

    assert respuesta.status_code == 201
    datos = respuesta.json()

    # Seguridad: no se expone en la respuesta ni en texto plano ni hasheada
    assert "contrasena_acceso" not in datos
    assert "contrasena" not in datos

    # Verificación en BD: debe estar persistida y hasheada con bcrypt
    torneo_en_bd = sesion_db.query(Torneo).filter_by(id=datos["id"]).first()
    assert torneo_en_bd is not None
    assert torneo_en_bd.contrasena_acceso is not None
    assert torneo_en_bd.contrasena_acceso != "claveSuperSecreta2026"
    assert verificar_password("claveSuperSecreta2026", torneo_en_bd.contrasena_acceso) is True


def test_creador_queda_automaticamente_como_participante(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    headers_autorizacion: dict[str, str],
) -> None:
    """Verifica que el creador quede automáticamente registrado en participantes_torneo (Paso 6 diagrama)."""
    payload = {
        "nombre": "Torneo Relampago",
        "cantidad_participantes": 16,
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)
    assert respuesta.status_code == 201
    torneo_id = respuesta.json()["id"]

    # Consulta directa en BD
    participacion = (
        sesion_db.query(ParticipanteTorneo)
        .filter_by(torneo_id=torneo_id, usuario_id=usuario_creador.id)
        .first()
    )

    assert participacion is not None
    assert participacion.usuario_id == usuario_creador.id
    assert participacion.torneo_id == torneo_id
    assert participacion.fecha_ingreso is not None


@pytest.mark.parametrize("cantidad_invalida", [2, 3, 5, 6, 7, 9, 10, 15, 32, 0, -1])
def test_crear_torneo_cantidad_participantes_invalida_retorna_422(
    cliente: TestClient,
    headers_autorizacion: dict[str, str],
    cantidad_invalida: int,
) -> None:
    """Verifica que cantidades de participantes fuera del conjunto {4, 8, 16} retornen 422."""
    payload = {
        "nombre": "Torneo Invalido",
        "cantidad_participantes": cantidad_invalida,
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)
    assert respuesta.status_code == 422


@pytest.mark.parametrize("nombre_invalido", ["", "   ", "   \t  \n  "])
def test_crear_torneo_nombre_vacio_retorna_422(
    cliente: TestClient,
    headers_autorizacion: dict[str, str],
    nombre_invalido: str,
) -> None:
    """Verifica que un nombre vacío o compuesto solo por espacios en blanco retorne 422."""
    payload = {
        "nombre": nombre_invalido,
        "cantidad_participantes": 4,
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)
    assert respuesta.status_code == 422


def test_crear_torneo_nombre_ausente_retorna_422(
    cliente: TestClient,
    headers_autorizacion: dict[str, str],
) -> None:
    """Verifica que omitir el campo obligatorio 'nombre' retorne 422."""
    payload = {
        "cantidad_participantes": 4,
    }

    respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)
    assert respuesta.status_code == 422


def test_crear_torneo_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica que intentar crear un torneo sin credenciales Bearer retorne 401 Unauthorized."""
    payload = {
        "nombre": "Torneo Sin Autenticacion",
        "cantidad_participantes": 8,
    }

    respuesta = cliente.post("/api/torneos", json=payload)
    assert respuesta.status_code == 401


def test_unicidad_codigo_acceso_torneos_consecutivos(
    cliente: TestClient,
    headers_autorizacion: dict[str, str],
) -> None:
    """Verifica que múltiples torneos creados consecutivamente generen códigos de acceso distintos."""
    codigos = set()
    for i in range(3):
        payload = {
            "nombre": f"Torneo de Prueba {i}",
            "cantidad_participantes": 4,
        }
        respuesta = cliente.post("/api/torneos", json=payload, headers=headers_autorizacion)
        assert respuesta.status_code == 201
        codigo = respuesta.json()["codigo_acceso"]
        codigos.add(codigo)

    assert len(codigos) == 3

