"""Configuración y fixtures para pruebas con Pytest."""

from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, obtener_db

# Motor SQLite en memoria para tests aislados sin dependencia de Supabase
motor_pruebas = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
# Configuración de la sesión de base de datos para pruebas
SesionPruebas = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=motor_pruebas,
)


@pytest.fixture(scope="session", autouse=True)
def preparar_base_datos_pruebas() -> Generator[None, None, None]:
    """Crea el esquema de base de datos en memoria para las pruebas."""
    Base.metadata.create_all(bind=motor_pruebas)
    yield
    Base.metadata.drop_all(bind=motor_pruebas)


@pytest.fixture
def sesion_db() -> Generator[Session, None, None]:
    """Provee una sesión de base de datos limpia para cada prueba."""
    conexion = motor_pruebas.connect()
    transaccion = conexion.begin()
    sesion = SesionPruebas(bind=conexion)

    yield sesion

    sesion.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def cliente(sesion_db: Session) -> Generator[TestClient, None, None]:
    """Cliente de pruebas HTTP con override de dependencia para base de datos."""

    def _sobrescribir_obtener_db() -> Generator[Session, None, None]:
        try:
            yield sesion_db
        finally:
            pass

    app.dependency_overrides[obtener_db] = _sobrescribir_obtener_db

    with TestClient(app) as cliente_prueba:
        yield cliente_prueba

    app.dependency_overrides.clear()

