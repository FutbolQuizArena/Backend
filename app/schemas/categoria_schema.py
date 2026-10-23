"""Esquemas Pydantic para la gestión de categorías en el panel de administración."""

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enumeraciones import EstadoCategoria


class CategoriaBase(BaseModel):
    """Atributos comunes para la creación y edición de categorías."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre único de la categoría")
    estado: Optional[EstadoCategoria] = Field(
        default=EstadoCategoria.ACTIVA,
        description="Estado de la categoría: ACTIVA o BORRADOR",
    )

    @field_validator("nombre", mode="before")
    @classmethod
    def validar_nombre_no_vacio(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("El nombre de la categoría no puede estar vacío ni contener solo espacios en blanco")
        return v.strip()


class CategoriaCreate(CategoriaBase):
    """Esquema para la creación de una nueva categoría."""
    pass


class CategoriaUpdate(BaseModel):
    """Esquema para la actualización de una categoría existente."""

    nombre: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Nuevo nombre de la categoría",
    )
    estado: Optional[EstadoCategoria] = Field(
        default=None,
        description="Nuevo estado de la categoría: ACTIVA o BORRADOR",
    )

    @field_validator("nombre", mode="before")
    @classmethod
    def validar_nombre_opcional(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError("El nombre de la categoría no puede estar vacío ni contener solo espacios en blanco")
        return v.strip()


class CategoriaCambiarEstadoRequest(BaseModel):
    """Esquema para el cambio directo y rápido de estado de una categoría."""

    estado: EstadoCategoria = Field(..., description="Nuevo estado de la categoría: ACTIVA o BORRADOR")


class CategoriaAdminResponse(BaseModel):
    """Esquema de respuesta para la administración de categorías con conteo de preguntas."""

    id: int
    nombre: str
    estado: EstadoCategoria
    preguntas_count: int = Field(default=0, description="Cantidad de preguntas vinculadas a la categoría")

    model_config = ConfigDict(from_attributes=True)


class CategoriaResponse(BaseModel):
    """Esquema de respuesta de categoría para el juego y la ruleta."""

    id: int
    nombre: str
    estado: Optional[EstadoCategoria] = EstadoCategoria.ACTIVA

    model_config = ConfigDict(from_attributes=True)
