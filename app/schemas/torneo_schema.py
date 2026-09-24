"""Esquemas Pydantic para la entidad Torneo y sus componentes."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enumeraciones import EstadoCruce, EstadoTorneo


class TorneoBase(BaseModel):
    """Atributos base del torneo."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre o título del torneo")
    cantidad_participantes: int = Field(..., ge=2, description="Cantidad de participantes configurada para el torneo")


class TorneoCreate(BaseModel):
    """Esquema de solicitud para la creación de un nuevo torneo."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre o título del torneo")
    cantidad_participantes: int = Field(
        ...,
        description="Cupo máximo de participantes permitido (4, 8 o 16)",
    )
    contrasena_acceso: str | None = Field(
        default=None,
        description="Contraseña opcional de acceso. Dejar vacía para un torneo abierto.",
    )

    @field_validator("cantidad_participantes")
    @classmethod
    def validar_cantidad_participantes(cls, valor: int) -> int:
        if valor not in (4, 8, 16):
            raise ValueError("La cantidad de participantes debe ser 4, 8 o 16")
        return valor

    @field_validator("nombre")
    @classmethod
    def validar_nombre_no_vacio(cls, valor: str) -> str:
        valor_limpio = valor.strip()
        if not valor_limpio:
            raise ValueError("El nombre del torneo no puede estar vacío ni contener solo espacios")
        return valor_limpio


class TorneoResponse(TorneoBase):
    """Esquema de respuesta devuelto al cliente. Nunca expone contrasena_acceso."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del torneo")
    codigo_acceso: str = Field(..., description="Código de acceso único del torneo")
    estado: EstadoTorneo = Field(..., description="Estado actual del torneo")
    creador_id: int = Field(..., description="Identificador del usuario creador")
    fecha_creacion: datetime = Field(..., description="Fecha y hora de creación del torneo")


class TorneoCreadoResponse(TorneoResponse):
    """Esquema de respuesta específico para la creación de torneo, confirmando id y codigo_acceso."""

    pass


class ParticipanteTorneoResponse(BaseModel):
    """Esquema de respuesta para la inscripción de un usuario en un torneo."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único de la participación")
    usuario_id: int = Field(..., description="Identificador del usuario participante")
    torneo_id: int = Field(..., description="Identificador del torneo")
    fecha_ingreso: datetime = Field(..., description="Fecha y hora de ingreso al torneo")


class ParticipanteDetalleResponse(BaseModel):
    """Detalle de un participante dentro del torneo para la vista de sala y cuadro."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = Field(default=None, description="Identificador único de la inscripción")
    usuario_id: int = Field(..., description="Identificador único del usuario")
    nombre: str = Field(default="", description="Nombre del usuario participante")
    es_creador: bool = Field(default=False, description="Indica si el participante es el creador/organizador del torneo")

    @model_validator(mode="before")
    @classmethod
    def extraer_datos_de_modelo(cls, data: Any) -> Any:
        if hasattr(data, "usuario_id"):
            usr = getattr(data, "usuario", None)
            nom = getattr(usr, "nombre", None) if usr else getattr(data, "nombre", "")
            trn = getattr(data, "torneo", None)
            creador_id = getattr(trn, "creador_id", None) if trn else None
            es_cread = (data.usuario_id == creador_id) if creador_id else False
            return {
                "id": getattr(data, "id", None),
                "usuario_id": data.usuario_id,
                "nombre": nom or getattr(data, "nombre", "") or "",
                "es_creador": getattr(data, "es_creador", es_cread),
            }
        return data


class CruceResponse(BaseModel):
    """Esquema de respuesta para un cruce eliminatorio en un torneo."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del cruce")
    torneo_id: int = Field(default=0, description="Identificador del torneo")
    ronda: int = Field(..., description="Número de ronda eliminatoria")
    jugador_a_id: int | None = Field(default=None, description="Identificador del participante jugador A")
    jugador_b_id: int | None = Field(default=None, description="Identificador del participante jugador B")
    ganador_id: int | None = Field(default=None, description="Identificador del participante ganador")
    estado: EstadoCruce = Field(..., description="Estado del cruce")
    jugador_a: ParticipanteDetalleResponse | None = Field(default=None, description="Detalle del jugador A")
    jugador_b: ParticipanteDetalleResponse | None = Field(default=None, description="Detalle del jugador B")
    ganador: ParticipanteDetalleResponse | None = Field(default=None, description="Detalle del participante ganador")


class TorneoDetalleResponse(BaseModel):
    """Esquema de respuesta detallado para la sala del torneo y cuadro de llaves."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del torneo")
    nombre: str = Field(..., description="Nombre del torneo")
    estado: EstadoTorneo = Field(..., description="Estado actual del torneo")
    cantidad_participantes: int = Field(..., description="Cupo máximo de participantes")
    cantidad_participantes_actual: int = Field(..., description="Cantidad actual de participantes inscriptos")
    creador_id: int = Field(..., description="Identificador del usuario creador")
    creador_nombre: str = Field(..., description="Nombre del usuario creador u organizador")
    codigo_acceso: str = Field(..., description="Código de acceso del torneo")
    fecha_creacion: datetime = Field(..., description="Fecha y hora de creación")
    participantes: list[ParticipanteDetalleResponse] = Field(default_factory=list, description="Lista de participantes del torneo")
    cuadro: list[CruceResponse] = Field(default_factory=list, description="Cuadro de cruces eliminatorios ordenado por ronda")


class TorneoUnirseRequest(BaseModel):
    """Esquema de solicitud para unirse a un torneo mediante código de acceso."""

    codigo_acceso: str = Field(..., min_length=1, description="Código de acceso del torneo al que desea unirse")
    contrasena: str | None = Field(
        default=None,
        description="Contraseña de acceso opcional requerida si el torneo es privado",
    )

    @field_validator("codigo_acceso")
    @classmethod
    def validar_y_normalizar_codigo(cls, valor: str) -> str:
        valor_limpio = valor.strip().upper()
        if not valor_limpio:
            raise ValueError("El código de acceso no puede estar vacío ni contener solo espacios")
        return valor_limpio


class FiltroTorneoEnum(str, Enum):
    """Filtros disponibles para la consulta de torneos."""

    MIOS = "mios"
    DISPONIBLES = "disponibles"
    FINALIZADOS = "finalizados"


class TorneoListItemResponse(BaseModel):
    """Esquema de respuesta optimizado para ítems en el listado de torneos."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del torneo")
    nombre: str = Field(..., description="Nombre del torneo")
    cantidad_participantes: int = Field(..., description="Cupo máximo de participantes")
    cantidad_participantes_actual: int = Field(..., description="Cantidad actual de participantes inscriptos")
    tiene_contrasena: bool = Field(..., description="Indica si el torneo requiere contraseña de acceso")
    estado: EstadoTorneo = Field(..., description="Estado actual del torneo")
    fecha_creacion: datetime = Field(..., description="Fecha y hora de creación")
    creador_id: int = Field(..., description="Identificador del usuario creador")
    codigo_acceso: str | None = Field(
        default=None,
        description="Código de acceso del torneo (visible únicamente para el creador)",
    )

