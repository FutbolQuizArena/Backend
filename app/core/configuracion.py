"""Configuración central de la aplicación mediante Pydantic Settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Ajustes y variables de entorno del sistema."""

    # Conexión a la base de datos PostgreSQL
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/futbolquiz_db"

    # Autenticación y JWT
    JWT_SECRET: str = Field(..., repr=False) # Clave privada para firmar tokens JWT, debe ser segura y no compartida.
    JWT_EXPIRATION_MIN: int = 60
    JWT_ALGORITMO: str = "HS256"

    # Metadatos de la aplicación
    TITULO_APP: str = "FutbolQuiz Arena API"
    VERSION_APP: str = "0.1.0"
    DESCRIPCION_APP: str = "API REST del backend de FutbolQuiz Arena para gestión de torneos y trivias."
    ENTORNO: str = "desarrollo"
    esta_en_modo_debug: bool = True

    @field_validator("JWT_SECRET")
    @classmethod
    def validar_clave_jwt(cls, valor: str) -> str:
        """Exige una clave privada y rechaza el antiguo valor de ejemplo."""
        if (
            len(valor.encode("utf-8")) < 32
            or not valor.strip()
            or valor == "super_secreto_futbolquiz_arena_cambiar_en_produccion"
        ):
            raise ValueError("JWT_SECRET debe ser una clave privada de al menos 32 bytes, distinta del ejemplo.")
        return valor

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
    )


# Instancia única de configuración
CONFIGURACION = Configuracion()
configuracion = CONFIGURACION

