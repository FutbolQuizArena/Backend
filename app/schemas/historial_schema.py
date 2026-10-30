"""Esquemas Pydantic del historial personal de partidas, duelos y torneos (Tarea 4.1.6, RF-15/RF-17)."""

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enumeraciones import EstadoTorneo


class ResultadoDuelo(str, enum.Enum):
    """Resultado de un duelo visto desde el jugador que consulta su historial."""

    VICTORIA = "VICTORIA"
    DERROTA = "DERROTA"
    EMPATE = "EMPATE"


class HistorialPartidaIndividualItem(BaseModel):
    """Una partida individual finalizada dentro del historial del jugador."""

    model_config = ConfigDict(from_attributes=True)

    partida_id: int
    categoria_nombre: str | None = None
    puntaje_final: int = Field(ge=0)
    fecha_fin: datetime | None = None


class HistorialDueloItem(BaseModel):
    """Un duelo finalizado dentro del historial del jugador, visto desde su lado."""

    model_config = ConfigDict(from_attributes=True)

    duelo_id: int
    modalidad: str
    categoria_nombre: str | None = None
    rival_nombre: str | None = None
    puntaje_propio: int = Field(ge=0)
    puntaje_rival: int = Field(ge=0)
    resultado: ResultadoDuelo
    fecha_fin: datetime | None = None


class HistorialTorneoItem(BaseModel):
    """Una participación en un torneo dentro del historial del jugador.

    `ronda_alcanzada` es la última ronda en la que el jugador tuvo un cruce
    (None si el torneo todavía no generó cruces). `es_campeon` es True solo si
    el torneo finalizó y el jugador ganó la final.
    """

    model_config = ConfigDict(from_attributes=True)

    torneo_id: int
    nombre: str
    estado: EstadoTorneo
    ronda_alcanzada: int | None = Field(default=None, ge=1)
    es_campeon: bool = False
    fecha_creacion: datetime | None = None


class HistorialPartidasIndividualesResponse(BaseModel):
    """Respuesta del historial de partidas individuales, de la más reciente a la más antigua."""

    partidas: list[HistorialPartidaIndividualItem]
    total: int = Field(ge=0)


class HistorialDuelosResponse(BaseModel):
    """Respuesta del historial de duelos, del más reciente al más antiguo."""

    duelos: list[HistorialDueloItem]
    total: int = Field(ge=0)


class HistorialTorneosResponse(BaseModel):
    """Respuesta del historial de torneos, del más reciente al más antiguo."""

    torneos: list[HistorialTorneoItem]
    total: int = Field(ge=0)