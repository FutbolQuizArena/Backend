"""Migración con partidas existentes: gracia inicial y reversibilidad."""

from pathlib import Path
from runpy import run_path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_migracion_presencia_upgrade_y_downgrade():
    archivo = Path(__file__).resolve().parents[1] / "alembic/versions/2026_11_25_1200-a12c91de5501_presencia_duelos.py"
    migracion = run_path(str(archivo))
    motor = create_engine("sqlite:///:memory:")
    with motor.begin() as conexion:
        conexion.exec_driver_sql("CREATE TABLE partidas_duelo (id INTEGER PRIMARY KEY, modalidad VARCHAR(20))")
        conexion.exec_driver_sql("INSERT INTO partidas_duelo VALUES (1, 'ONLINE'), (2, 'LOCAL')")
        with Operations.context(MigrationContext.configure(conexion)):
            migracion["upgrade"]()
            filas = conexion.execute(text("SELECT ultima_presencia_jugador1, ultima_presencia_jugador2, motivo_finalizacion FROM partidas_duelo ORDER BY id")).all()
            assert filas[0][0] is not None and filas[0][1] is not None
            assert tuple(filas[1]) == (None, None, None)
            migracion["downgrade"]()
        assert {c["name"] for c in inspect(conexion).get_columns("partidas_duelo")} == {"id", "modalidad"}
    motor.dispose()
