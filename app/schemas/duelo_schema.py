"""Esquemas Pydantic para las respuestas del duelo (Tarea 2.1.11)."""

from pydantic import BaseModel, ConfigDict


class DueloEstadoResponse(BaseModel):
    """Respuesta con el estado y resultado actual de un duelo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: str
    modalidad: str
    categoria_id: int | None
    jugador1_id: int
    jugador2_id: int | None
    puntaje_jugador1: int
    puntaje_jugador2: int
    numero_ganador: int | None
    es_empate: bool