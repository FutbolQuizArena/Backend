"""Compatibilidad de la conexión con Psycopg y el pool de Supabase."""

from pathlib import Path
import runpy

import pytest
import sqlalchemy

from app.core.configuracion import CONFIGURACION


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://usuario:clave@localhost/base",
    "postgresql+psycopg2://usuario:clave@localhost/base",
    "postgres://usuario:clave@aws-0.pooler.supabase.com:5432/base",
    "sqlite:///:memory:",
])
def test_argumentos_conexion_segun_driver(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Psycopg 3 desactiva preparación; otros drivers no reciben ese argumento.

    Se construye el motor real sin conectarse a ninguna base de datos externa.
    """
    crear_motor = sqlalchemy.create_engine
    argumentos = {}

    def capturar_motor(url, **opciones):
        argumentos.update(opciones["connect_args"])
        return crear_motor(url, **opciones)

    monkeypatch.setattr(CONFIGURACION, "DATABASE_URL", url)
    monkeypatch.setattr(sqlalchemy, "create_engine", capturar_motor)
    ruta = Path(__file__).resolve().parents[1] / "app" / "core" / "base_datos.py"
    modulo = runpy.run_path(str(ruta))
    motor = modulo["motor_bd"]
    try:
        if motor.dialect.driver == "psycopg":
            assert "prepare_threshold" in argumentos
            assert argumentos["prepare_threshold"] is None
        else:
            assert "prepare_threshold" not in argumentos
        if url.startswith("postgres://"):
            assert motor.url.port == 6543
        if url.startswith("sqlite"):
            assert argumentos["check_same_thread"] is False
    finally:
        motor.dispose()
