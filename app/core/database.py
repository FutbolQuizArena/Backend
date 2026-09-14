"""Conexión centralizada a la base de datos PostgreSQL mediante SQLAlchemy."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import CONFIGURACION

# Normalización de URL para PostgreSQL / Supabase
# Muchos proveedores (Supabase, Render) entregan el esquema como postgres://
url_conexion = CONFIGURACION.DATABASE_URL
if url_conexion.startswith("postgres://"):
    url_conexion = url_conexion.replace("postgres://", "postgresql://", 1)

# Argumentos de conexión según motor
argumentos_conexion = {}
if url_conexion.startswith("sqlite"):
    argumentos_conexion["check_same_thread"] = False

# Motor de base de datos armado una sola vez aquí
motor_bd = create_engine(
    url_conexion,
    pool_pre_ping=True,
    connect_args=argumentos_conexion,
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

