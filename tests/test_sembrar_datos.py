"""Pruebas para el mecanismo de siembra (seed) modular e idempotente (Tarea 5.1.5 - Módulo 5)."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.configuracion import CONFIGURACION
from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta, RolUsuario
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.repositories import categoria_repository, pregunta_repository, usuario_repository
from app.services import autenticacion_service, semilla_service, usuario_service


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def datos_semilla_muestra() -> list[dict]:
    """Conjunto de datos estructurados de prueba en memoria."""
    return [
        {
            "category": "Mundiales",
            "difficulty": "Fácil",
            "question": "¿Qué país ganó el Mundial de 1978?",
            "options": {
                "A": "Argentina",
                "B": "Brasil",
                "C": "Países Bajos",
                "D": "Italia",
            },
            "correct_option": "A",
        },
        {
            "category": "Mundiales",
            "difficulty": "Media",
            "question": "¿Quién fue el Balón de Oro en el Mundial 2014?",
            "options": {
                "A": "Lionel Messi",
                "B": "Thomas Müller",
                "C": "James Rodríguez",
                "D": "Manuel Neuer",
            },
            "correct_option": "A",
        },
        {
            "category": "Copa Libertadores",
            "difficulty": "Fácil",
            "question": "¿Qué club ganó la final de Madrid en 2018?",
            "options": {
                "A": "Boca Juniors",
                "B": "River Plate",
                "C": "Gremio",
                "D": "Palmeiras",
            },
            "correct_option": "B",
        },
    ]


@pytest.fixture
def usuario_admin(sesion_db: Session) -> Usuario:
    """Crea un usuario administrador activo para pruebas de endpoint."""
    admin = Usuario(
        nombre="Admin Semilla",
        email="admin.semilla@futbolquiz.com",
        password_hash=usuario_service.hashear_password("adminSecret123"),
        rol=RolUsuario.ADMINISTRADOR,
        esta_habilitado=True,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea un usuario jugador para verificar restricción 403."""
    jugador = Usuario(
        nombre="Jugador Semilla",
        email="jugador.semilla@futbolquiz.com",
        password_hash=usuario_service.hashear_password("jugadorSecret123"),
        rol=RolUsuario.JUGADOR,
        esta_habilitado=True,
    )
    return usuario_repository.crear(sesion_db, jugador)


@pytest.fixture
def headers_admin(usuario_admin: Usuario) -> dict[str, str]:
    token = autenticacion_service.generar_token_jwt(usuario_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_jugador(usuario_jugador: Usuario) -> dict[str, str]:
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Tests del servicio de carga y persistencia
# ==============================================================================


def test_cargar_preguntas_desde_json_archivo_defecto() -> None:
    """Verifica que el cargador lea correctamente el archivo seed por defecto."""
    preguntas = semilla_service.cargar_preguntas_desde_json()
    assert isinstance(preguntas, list)
    assert len(preguntas) >= 3
    primer_item = preguntas[0]
    assert "category" in primer_item
    assert "question" in primer_item
    assert "options" in primer_item
    assert "correct_option" in primer_item


def test_cargar_preguntas_desde_json_archivo_inexistente() -> None:
    """Verifica que se lance FileNotFoundError ante una ruta inexistente."""
    with pytest.raises(FileNotFoundError):
        semilla_service.cargar_preguntas_desde_json("ruta/falsa/inexistente.json")


def test_sembrar_preguntas_y_categorias_exitosa(
    sesion_db: Session, datos_semilla_muestra: list[dict]
) -> None:
    """Verifica que la siembra cree las categorías y preguntas con los atributos correctos."""
    resultado = semilla_service.sembrar_preguntas_y_categorias(sesion_db, datos_semilla_muestra)

    assert resultado["categorias_creadas"] == 2
    assert resultado["categorias_existentes"] == 0
    assert resultado["preguntas_creadas"] == 3
    assert resultado["preguntas_omitidas"] == 0
    assert resultado["total_procesadas"] == 3

    # Verificar categorías
    cat_mundiales = categoria_repository.obtener_categoria_por_nombre(sesion_db, "Mundiales")
    assert cat_mundiales is not None
    assert cat_mundiales.estado == EstadoCategoria.ACTIVA

    cat_libertadores = categoria_repository.obtener_categoria_por_nombre(sesion_db, "Copa Libertadores")
    assert cat_libertadores is not None
    assert cat_libertadores.estado == EstadoCategoria.ACTIVA

    # Verificar preguntas
    preguntas_mundiales = pregunta_repository.listar_preguntas_por_categoria(sesion_db, cat_mundiales.id)
    assert len(preguntas_mundiales) == 2
    for p in preguntas_mundiales:
        assert p.estado == EstadoPregunta.ACTIVA
        assert p.eliminada_en is None
        assert p.opcion_a != ""
        assert p.respuesta_correcta in ("A", "B", "C", "D")


def test_idempotencia_siembra_no_duplica(
    sesion_db: Session, datos_semilla_muestra: list[dict]
) -> None:
    """Verifica que ejecutar la siembra 2 veces no duplique categorías ni preguntas."""
    primera_ejecucion = semilla_service.sembrar_preguntas_y_categorias(
        sesion_db, datos_semilla_muestra
    )
    assert primera_ejecucion["categorias_creadas"] == 2
    assert primera_ejecucion["preguntas_creadas"] == 3

    # Segunda ejecución con los mismos datos
    segunda_ejecucion = semilla_service.sembrar_preguntas_y_categorias(
        sesion_db, datos_semilla_muestra
    )
    assert segunda_ejecucion["categorias_creadas"] == 0
    assert segunda_ejecucion["categorias_existentes"] == 2
    assert segunda_ejecucion["preguntas_creadas"] == 0
    assert segunda_ejecucion["preguntas_omitidas"] == 3
    assert segunda_ejecucion["total_procesadas"] == 3

    # El conteo físico en BD debe permanecer intacto
    total_cats = sesion_db.query(Categoria).count()
    total_pregs = sesion_db.query(Pregunta).count()
    assert total_cats == 2
    assert total_pregs == 3


def test_sembrar_tolera_datos_invalidos_u_omisiones(sesion_db: Session) -> None:
    """Verifica que preguntas con estructura defectuosa sean omitidas sin romper la transacción."""
    datos_con_errores = [
        # Pregunta válida
        {
            "category": "Historia",
            "difficulty": "Difícil",
            "question": "¿En qué año se fundó la FIFA?",
            "options": {"A": "1904", "B": "1910", "C": "1924", "D": "1930"},
            "correct_option": "A",
        },
        # Falta categoría
        {
            "category": "",
            "difficulty": "Media",
            "question": "Pregunta sin categoría",
            "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
            "correct_option": "A",
        },
        # Falta opción D
        {
            "category": "Historia",
            "difficulty": "Media",
            "question": "Pregunta incompleta",
            "options": {"A": "1", "B": "2", "C": "3"},
            "correct_option": "A",
        },
        # Opción correcta inválida (X)
        {
            "category": "Historia",
            "difficulty": "Media",
            "question": "Pregunta con letra errónea",
            "options": {"A": "1", "B": "2", "C": "3", "D": "4"},
            "correct_option": "X",
        },
    ]

    resultado = semilla_service.sembrar_preguntas_y_categorias(sesion_db, datos_con_errores)

    assert resultado["categorias_creadas"] == 1
    assert resultado["preguntas_creadas"] == 1
    assert resultado["preguntas_omitidas"] == 3
    assert resultado["total_procesadas"] == 4

    total_pregs = sesion_db.query(Pregunta).count()
    assert total_pregs == 1


def test_categoria_existente_inactiva_se_activa_al_sembrar(sesion_db: Session) -> None:
    """Verifica que si una categoría existía en BORRADOR, la siembra la actualice a ACTIVA."""
    categoria_borrador = Categoria(nombre="Reglas", estado=EstadoCategoria.BORRADOR)
    sesion_db.add(categoria_borrador)
    sesion_db.commit()

    datos = [
        {
            "category": "Reglas",
            "difficulty": "Fácil",
            "question": "¿Cuánto dura un tiempo suplementario de fútbol?",
            "options": {"A": "15 min", "B": "30 min", "C": "20 min", "D": "10 min"},
            "correct_option": "B",
        }
    ]

    resultado = semilla_service.sembrar_preguntas_y_categorias(sesion_db, datos)
    assert resultado["categorias_creadas"] == 0
    assert resultado["categorias_existentes"] == 1
    assert resultado["preguntas_creadas"] == 1

    cat_refrescada = categoria_repository.obtener_categoria_por_nombre(sesion_db, "Reglas")
    assert cat_refrescada is not None
    assert cat_refrescada.estado == EstadoCategoria.ACTIVA


# ==============================================================================
# Tests del endpoint administrativo POST /api/admin/sistema/sembrar
# ==============================================================================


def test_endpoint_sembrar_sin_token_retorna_401(cliente: TestClient) -> None:
    """Verifica que invocar la siembra sin autenticación responda 401."""
    resp = cliente.post("/api/admin/sistema/sembrar")
    assert resp.status_code == 401
    assert resp.json()["code"] == "TOKEN_INVALIDO"


def test_endpoint_sembrar_con_jugador_retorna_403(
    cliente: TestClient, headers_jugador: dict[str, str]
) -> None:
    """Verifica que un usuario con rol JUGADOR no pueda disparar la siembra (403)."""
    resp = cliente.post("/api/admin/sistema/sembrar", headers=headers_jugador)
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCESO_DENEGADO"


def test_endpoint_sembrar_con_admin_exitoso(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Verifica que un administrador pueda disparar la siembra vía API REST (200)."""
    resp = cliente.post("/api/admin/sistema/sembrar", headers=headers_admin)
    assert resp.status_code == 200
    datos = resp.json()
    assert "categorias_creadas" in datos
    assert "categorias_existentes" in datos
    assert "preguntas_creadas" in datos
    assert "preguntas_omitidas" in datos
    assert "total_procesadas" in datos
    assert datos["total_procesadas"] >= 3


def test_script_cli_ejecutar_siembra(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Verifica que la función del script CLI se ejecute correctamente."""
    from scripts.sembrar_datos import ejecutar_siembra

    # Ejecutar la siembra usando la BD configurada en el entorno
    ejecutar_siembra()
    capturado = capsys.readouterr()
    assert "FUTBOLQUIZ ARENA - SIEMBRA DE CATEGORÍAS Y PREGUNTAS" in capturado.out
    assert "RESULTADOS DE LA SIEMBRA:" in capturado.out
    assert "[ÉXITO] Proceso de siembra finalizado correctamente." in capturado.out
