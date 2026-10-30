"""Verifica la migración aislada sin conectarse a la base configurada en .env."""

from pathlib import Path
from runpy import run_path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models.token_revocado import TokenRevocado
from app.repositories import token_revocado_repository


def test_migracion_revocaciones_upgrade_y_downgrade() -> None:
    raiz = Path(__file__).resolve().parents[1]
    config = Config(str(raiz / "alembic.ini"))
    config.set_main_option("script_location", str(raiz / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    revision = scripts.get_revision("e11aa3222dc9")
    assert revision.down_revision == "d8f92144b20a"
    migracion = run_path(revision.path)

    motor = create_engine("sqlite:///:memory:")
    try:
        with motor.begin() as conexion:
            with Operations.context(MigrationContext.configure(conexion)):
                migracion["upgrade"]()
                columnas = inspect(conexion).get_columns("tokens_revocados")
                assert {columna["name"] for columna in columnas} == {"huella", "expira_en"}
                assert inspect(conexion).get_indexes("tokens_revocados")[0]["name"] == (
                    "ix_tokens_revocados_expira_en"
                )
                # El repositorio y el modelo deben funcionar con el esquema migrado.
                with Session(bind=conexion) as sesion:
                    token_revocado_repository.revocar(sesion, "a" * 64, 200, 100)
                    assert sesion.get(TokenRevocado, "a" * 64).expira_en == 200
                migracion["downgrade"]()
                assert "tokens_revocados" not in inspect(conexion).get_table_names()
    finally:
        motor.dispose()
