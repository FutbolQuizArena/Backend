"""Configuración del entorno de migraciones de Alembic."""

import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Agregar raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import CONFIGURACION
from app.core.database import Base
import app.models  # noqa: F401

# Configuración de loggers desde el archivo ini
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Asignar la URL dinámica desde la configuración del proyecto
url_db = CONFIGURACION.DATABASE_URL
if url_db.startswith("postgres://"):
    url_db = url_db.replace("postgres://", "postgresql://", 1)

config.set_main_option("sqlalchemy.url", url_db)

# Metadatos para generación automática de migraciones
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online' con conexión activa."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

