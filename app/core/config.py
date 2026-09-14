"""Configuración central de la aplicación mediante Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Ajustes y variables de entorno del sistema."""

    # Conexión a la base de datos PostgreSQL
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/futbolquiz_db"

    # Autenticación y JWT
    JWT_SECRET: str = "super_secreto_futbolquiz_arena_cambiar_en_produccion"
    JWT_EXPIRATION_MIN: int = 60

    # Metadatos de la aplicación
    TITULO_APP: str = "FutbolQuiz Arena API"
    VERSION_APP: str = "0.1.0"
    DESCRIPCION_APP: str = "API REST del backend de FutbolQuiz Arena para gestión de torneos y trivias."
    ENTORNO: str = "desarrollo"
    esta_en_modo_debug: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Instancia única de configuración
CONFIGURACION = Configuracion()
configuracion = CONFIGURACION

