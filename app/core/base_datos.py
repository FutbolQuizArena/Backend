"""Conexión centralizada a la base de datos PostgreSQL mediante SQLAlchemy."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.configuracion import CONFIGURACION

# Normalización de URL para PostgreSQL / Supabase
# Muchos proveedores (Supabase, Render) entregan el esquema como postgres://
url_conexion = CONFIGURACION.DATABASE_URL
if url_conexion.startswith("postgres://"):
    url_conexion = url_conexion.replace("postgres://", "postgresql://", 1)

# Supabase Pooler: El puerto 5432 opera en 'Session Mode' (límite estricto de 15 clientes concurrentes).
# El puerto 6543 opera en 'Transaction Mode' (PgBouncer), diseñado para alta concurrencia
# evitando el error FATAL (EMAXCONNSESSION) ante ráfagas de consultas.
if "pooler.supabase.com:5432" in url_conexion:
    url_conexion = url_conexion.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")

# Argumentos de conexión según motor
argumentos_conexion = {}
argumentos_engine = {
    "pool_pre_ping": True,
}

if url_conexion.startswith("sqlite"):
    argumentos_conexion["check_same_thread"] = False
else:
    # Configuración de pool robusto para PostgreSQL concurrente
    argumentos_engine.update({
        "pool_size": 20,
        "max_overflow": 40,
        "pool_timeout": 60,
        "pool_recycle": 300,
    })

argumentos_engine["connect_args"] = argumentos_conexion

# Motor de base de datos armado una sola vez aquí
motor_bd = create_engine(
    url_conexion,
    **argumentos_engine,
)

# Fábrica de sesiones
SesionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=motor_bd,
)

# Base declarativa para modelos SQLAlchemy
Base = declarative_base()


def obtener_db() -> Generator[Session, None, None]:
    """Genera una sesión de base de datos y asegura su cierre tras la petición."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()


# Alias para interoperabilidad
get_db = obtener_db
SessionLocal = SesionLocal
engine = motor_bd

