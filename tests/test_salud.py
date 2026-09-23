"""Pruebas unitarias para el endpoint de salud y el manejador global de excepciones."""

from unittest.mock import MagicMock
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.core.base_datos import obtener_db


def test_verificar_salud_exitoso(cliente: TestClient) -> None:
    """Verifica que GET /api/health responda 200 y confirme conexión a la base de datos."""
    respuesta = cliente.get("/api/health")
    assert respuesta.status_code == status.HTTP_200_OK
    assert respuesta.json() == {"status": "ok"}


def test_verificar_salud_falla_base_datos() -> None:
    """Verifica que un fallo en la base de datos devuelva la estructura de error estándar."""

    def _obtener_db_con_falla():
        sesion_mock = MagicMock()
        sesion_mock.execute.side_effect = Exception("Conexión perdida a PostgreSQL")
        yield sesion_mock

    app.dependency_overrides[obtener_db] = _obtener_db_con_falla

    with TestClient(app) as cliente_falla:
        respuesta = cliente_falla.get("/api/health")
        assert respuesta.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        datos = respuesta.json()
        assert "code" in datos
        assert "message" in datos
        assert "detail" in datos
        assert datos["code"] == "ERROR_BASE_DATOS"
        assert "Conexión perdida a PostgreSQL" in str(datos["detail"])

    app.dependency_overrides.clear()


def test_manejador_error_ruta_no_encontrada(cliente: TestClient) -> None:
    """Verifica que rutas inexistentes respeten la estructura fija de error {code, message, detail}."""
    respuesta = cliente.get("/api/ruta_que_no_existe")
    assert respuesta.status_code == status.HTTP_404_NOT_FOUND

    datos = respuesta.json()
    assert set(datos.keys()) == {"code", "message", "detail"}
    assert datos["code"] == "ERROR_HTTP_404"


def test_documentacion_openapi_disponible(cliente: TestClient) -> None:
    """Verifica que la documentación OpenAPI se configure con el título esperado."""
    respuesta = cliente.get("/openapi.json")
    assert respuesta.status_code == status.HTTP_200_OK

    datos = respuesta.json()
    assert datos["info"]["title"] == "FutbolQuiz Arena API"
    assert "/api/health" in datos["paths"]

