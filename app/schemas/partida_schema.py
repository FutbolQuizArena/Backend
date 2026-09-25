"""Esquemas Pydantic para el flujo de partida individual."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PreguntaJuegoResponse(BaseModel):
    """Pregunta tal como se muestra al jugador, sin exponer la respuesta correcta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    orden: int
    enunciado: str
    opcion_a: str
    opcion_b: str
    opcion_c: str
    opcion_d: str


class PartidaIndividualResponse(BaseModel):
    """Respuesta al iniciar una partida individual: la partida y sus 10 preguntas."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    categoria_id: int | None
    estado: str
    preguntas: list[PreguntaJuegoResponse]

    @classmethod
    def desde_partida(cls, partida) -> "PartidaIndividualResponse":
        """Arma la respuesta a partir del modelo ORM, mapeando cada PreguntaPartida a su Pregunta."""
        preguntas_juego = []
        for pregunta_partida in partida.preguntas:
            preguntas_juego.append(
                PreguntaJuegoResponse(
                    id=pregunta_partida.id,
                    orden=pregunta_partida.orden,
                    enunciado=pregunta_partida.pregunta.enunciado,
                    opcion_a=pregunta_partida.pregunta.opcion_a,
                    opcion_b=pregunta_partida.pregunta.opcion_b,
                    opcion_c=pregunta_partida.pregunta.opcion_c,
                    opcion_d=pregunta_partida.pregunta.opcion_d,
                )
            )
        return cls(
            id=partida.id,
            categoria_id=partida.categoria_id,
            estado=partida.estado,
            preguntas=preguntas_juego,
        )


class RespuestaPartidaRequest(BaseModel):
    """Datos enviados por el jugador al responder una pregunta."""

    opcion_seleccionada: str
    tiempo_respuesta_segundos: int


class RespuestaPartidaResponse(BaseModel):
    """Feedback inmediato tras responder una pregunta."""

    es_correcta: bool
    puntaje_obtenido: int


class ResultadoPartidaResponse(BaseModel):
    """Resultado final de una partida individual finalizada."""

    model_config = ConfigDict(from_attributes=True)

    partida_id: int = None
    puntaje_final: int
    fecha_fin: datetime | None

    @classmethod
    def desde_partida(cls, partida) -> "ResultadoPartidaResponse":
        return cls(
            partida_id=partida.id,
            puntaje_final=partida.puntaje_final,
            fecha_fin=partida.fecha_fin,
        )