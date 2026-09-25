"""Esquemas Pydantic para la gestión de preguntas en el panel de administración."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enumeraciones import EstadoPregunta


class PreguntaBase(BaseModel):
    """Atributos comunes para la creación y edición de preguntas."""

    enunciado: str = Field(..., min_length=1, description="Texto de la pregunta")
    categoria_id: int = Field(..., description="ID de la categoría a la que pertenece la pregunta")
    opcion_a: str = Field(..., min_length=1, description="Primera opción de respuesta")
    opcion_b: str = Field(..., min_length=1, description="Segunda opción de respuesta")
    opcion_c: str = Field(..., min_length=1, description="Tercera opción de respuesta")
    opcion_d: str = Field(..., min_length=1, description="Cuarta opción de respuesta")
    respuesta_correcta: str = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Letra de la opción correcta: 'A', 'B', 'C' o 'D'",
    )
    dificultad: Optional[str] = Field(
        default="Media",
        description="Dificultad de la pregunta: Fácil, Media o Difícil",
    )
    estado: Optional[EstadoPregunta] = Field(
        default=EstadoPregunta.ACTIVA,
        description="Estado de la pregunta: ACTIVA o BORRADOR",
    )

    @field_validator("enunciado", "opcion_a", "opcion_b", "opcion_c", "opcion_d", mode="before")
    @classmethod
    def validar_no_vacio(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("El campo no puede estar vacío ni contener solo espacios en blanco")
        return v.strip()

    @field_validator("respuesta_correcta", mode="before")
    @classmethod
    def validar_respuesta_correcta(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("La respuesta correcta debe ser una cadena")
        v_upper = v.strip().upper()
        if v_upper not in {"A", "B", "C", "D"}:
            raise ValueError("La respuesta correcta debe ser una de las opciones válidas: 'A', 'B', 'C' o 'D'")
        return v_upper


class PreguntaCreate(PreguntaBase):
    """Esquema para la creación de una nueva pregunta."""
    pass


class PreguntaUpdate(BaseModel):
    """Esquema para la actualización parcial de una pregunta existente."""

    enunciado: Optional[str] = Field(default=None, description="Nuevo texto de la pregunta")
    categoria_id: Optional[int] = Field(default=None, description="Nuevo ID de categoría")
    opcion_a: Optional[str] = Field(default=None, description="Nueva opción A")
    opcion_b: Optional[str] = Field(default=None, description="Nueva opción B")
    opcion_c: Optional[str] = Field(default=None, description="Nueva opción C")
    opcion_d: Optional[str] = Field(default=None, description="Nueva opción D")
    respuesta_correcta: Optional[str] = Field(
        default=None,
        description="Nueva letra de opción correcta ('A', 'B', 'C' o 'D')",
    )
    dificultad: Optional[str] = Field(default=None, description="Nueva dificultad")
    estado: Optional[EstadoPregunta] = Field(default=None, description="Nuevo estado")

    @field_validator("enunciado", "opcion_a", "opcion_b", "opcion_c", "opcion_d", mode="before")
    @classmethod
    def validar_no_vacio_opcional(cls, v: Any) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str) or not v.strip():
                raise ValueError("El campo no puede estar vacío ni contener solo espacios en blanco")
            return v.strip()
        return v

    @field_validator("respuesta_correcta", mode="before")
    @classmethod
    def validar_respuesta_correcta_opcional(cls, v: Any) -> Optional[str]:
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("La respuesta correcta debe ser una cadena")
            v_upper = v.strip().upper()
            if v_upper not in {"A", "B", "C", "D"}:
                raise ValueError("La respuesta correcta debe ser una de las opciones válidas: 'A', 'B', 'C' o 'D'")
            return v_upper
        return v


class PreguntaCambiarEstadoRequest(BaseModel):
    """Esquema para cambio rápido de estado (toggle ACTIVA / BORRADOR)."""

    estado: EstadoPregunta = Field(..., description="Nuevo estado para la pregunta: ACTIVA o BORRADOR")


class PreguntaAdminResponse(BaseModel):
    """Esquema de respuesta detallada para una pregunta en el panel de administración."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    enunciado: str
    categoria_id: int
    categoria_nombre: Optional[str] = None
    opcion_a: str
    opcion_b: str
    opcion_c: str
    opcion_d: str
    respuesta_correcta: str
    dificultad: Optional[str] = "Media"
    estado: EstadoPregunta
    eliminada_en: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def extraer_desde_orm(cls, data: Any) -> Any:
        if hasattr(data, "__dict__") or not isinstance(data, dict):
            categoria = getattr(data, "categoria", None)
            categoria_nombre = categoria.nombre if categoria else None
            return {
                "id": getattr(data, "id", None),
                "enunciado": getattr(data, "enunciado", None),
                "categoria_id": getattr(data, "categoria_id", None),
                "categoria_nombre": getattr(data, "categoria_nombre", categoria_nombre),
                "opcion_a": getattr(data, "opcion_a", None),
                "opcion_b": getattr(data, "opcion_b", None),
                "opcion_c": getattr(data, "opcion_c", None),
                "opcion_d": getattr(data, "opcion_d", None),
                "respuesta_correcta": getattr(data, "respuesta_correcta", None),
                "dificultad": getattr(data, "dificultad", "Media"),
                "estado": getattr(data, "estado", EstadoPregunta.ACTIVA),
                "eliminada_en": getattr(data, "eliminada_en", None),
            }
        return data


class PreguntaListadoResponse(BaseModel):
    """Respuesta paginada del listado de preguntas para el panel de administración."""

    items: list[PreguntaAdminResponse]
    total: int
    page: int
    total_paginas: int
