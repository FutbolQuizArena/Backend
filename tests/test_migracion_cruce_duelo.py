"""Migración reversible con datos existentes y restricciones de identidad del duelo."""

from pathlib import Path
from runpy import run_path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_migracion_cruce_duelo_upgrade_y_downgrade():
    raiz = Path(__file__).resolve().parents[1]
    config = Config(str(raiz / "alembic.ini"))
    config.set_main_option("script_location", str(raiz / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["f23b48c091aa"]
    revision = scripts.get_revision("f23b48c091aa")
    assert revision.down_revision == "e11aa3222dc9"
    migracion = run_path(revision.path)
    motor = create_engine("sqlite:///:memory:")
    try:
        with motor.begin() as conexion:
            conexion.exec_driver_sql("PRAGMA foreign_keys=ON")
            conexion.exec_driver_sql("CREATE TABLE partidas_duelo (id INTEGER PRIMARY KEY)")
            conexion.exec_driver_sql("CREATE TABLE cruces_torneo (id INTEGER PRIMARY KEY)")
            conexion.exec_driver_sql("INSERT INTO cruces_torneo (id) VALUES (1), (2)")
            conexion.exec_driver_sql("INSERT INTO partidas_duelo (id) VALUES (10)")
            with Operations.context(MigrationContext.configure(conexion)):
                migracion["upgrade"]()
                assert conexion.execute(text("SELECT duelo_id FROM cruces_torneo WHERE id=1")).scalar() is None
                conexion.exec_driver_sql("UPDATE cruces_torneo SET duelo_id=10 WHERE id=1")
                with pytest.raises(IntegrityError):
                    conexion.exec_driver_sql("UPDATE cruces_torneo SET duelo_id=10 WHERE id=2")
                with pytest.raises(IntegrityError):
                    conexion.exec_driver_sql("DELETE FROM partidas_duelo WHERE id=10")
                migracion["downgrade"]()
                assert {c["name"] for c in inspect(conexion).get_columns("cruces_torneo")} == {"id"}
                assert conexion.execute(text("SELECT COUNT(*) FROM cruces_torneo")).scalar() == 2
    finally:
        motor.dispose()
