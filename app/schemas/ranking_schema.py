"""Esquemas Pydantic del ranking general (Tarea 4.1.6, RF-16)."""

from pydantic import BaseModel, ConfigDict, Field


class JugadorRankingResponse(BaseModel):
    """Una fila del ranking general: la posición de un jugador y su puntaje acumulado."""

    model_config = ConfigDict(from_attributes=True)

    posicion: int = Field(ge=1)
    usuario_id: int
    nombre: str
    puntaje_total: int = Field(ge=0)


class RankingResponse(BaseModel):
    """Respuesta de la consulta del ranking general, paginada.

    `mi_posicion` es la fila del usuario que consulta (aunque no esté en la página
    pedida), para que el frontend pueda resaltarlo. Es None si el usuario no
    participa del ranking (por ejemplo, un administrador).
    """

    jugadores: list[JugadorRankingResponse]
    total_jugadores: int = Field(ge=0)
    pagina: int = Field(ge=1)
    tamano_pagina: int = Field(ge=1)
    mi_posicion: JugadorRankingResponse | None = None