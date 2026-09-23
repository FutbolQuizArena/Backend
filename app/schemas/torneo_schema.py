"""Esquemas Pydantic para la entidad Torneo y sus componentes."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.enumeraciones import EstadoCruce, EstadoTorneo


class TorneoBase(BaseModel):
    """Atributos base del torneo."""

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre o título del torneo")
    cantidad_participantes: int = Field(..., ge=2, description="Cantidad de participantes configurada para el torneo")


class TorneoResponse(TorneoBase):
    """Esquema de respuesta devuelto al cliente. Nunca expone contrasena_acceso."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del torneo")
    codigo_acceso: str = Field(..., description="Código de acceso único del torneo")
    estado: EstadoTorneo = Field(..., description="Estado actual del torneo")
    creador_id: int = Field(..., description="Identificador del usuario creador")
    fecha_creacion: datetime = Field(..., description="Fecha y hora de creación del torneo")


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

