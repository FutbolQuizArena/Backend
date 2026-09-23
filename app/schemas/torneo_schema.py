"""Esquemas Pydantic para la entidad Torneo y sus componentes."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class CruceResponse(BaseModel):
    """Esquema de respuesta para un cruce eliminatorio en un torneo."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del cruce")
    torneo_id: int = Field(..., description="Identificador del torneo")
    ronda: int = Field(..., description="Número de ronda eliminatoria")
    jugador_a_id: int = Field(..., description="Identificador del participante jugador A")
    jugador_b_id: int = Field(..., description="Identificador del participante jugador B")
    ganador_id: int | None = Field(default=None, description="Identificador del participante ganador")
    estado: EstadoCruce = Field(..., description="Estado del cruce")

