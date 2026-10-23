"""Validación de la clave privada utilizada para firmar tokens JWT."""

import secrets

import pytest
from pydantic import ValidationError

from app.core.configuracion import Configuracion


def test_clave_jwt_obligatoria(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin variable ni archivo de entorno, el backend debe rechazar el inicio."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Configuracion(_env_file=None)


@pytest.mark.parametrize(
    "clave",
    ["", "clave-corta", " " * 32, "super_secreto_futbolquiz_arena_cambiar_en_produccion"],
)
def test_rechazar_clave_jwt_insegura(clave: str) -> None:
    """Rechaza claves vacías, débiles y el antiguo valor público."""
    with pytest.raises(ValidationError, match="JWT_SECRET") as error:
        Configuracion(_env_file=None, JWT_SECRET=clave)
    if clave:
        assert clave not in str(error.value)


def test_aceptar_clave_privada_sin_exponerla() -> None:
    """La clave configurada funciona y no aparece al representar los ajustes."""
    clave = secrets.token_hex(32)
    configuracion = Configuracion(_env_file=None, JWT_SECRET=clave)
    assert configuracion.JWT_SECRET == clave
    assert clave not in repr(configuracion)
