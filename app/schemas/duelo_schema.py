"""Esquemas Pydantic para las respuestas del duelo (Tarea 2.1.11 y endpoints de juego)."""

from pydantic import BaseModel, ConfigDict

from app.schemas.partida_schema import PreguntaJuegoResponse


class DueloEstadoResponse(BaseModel):
    """Respuesta con el estado y resultado actual de un duelo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: str
    modalidad: str
    categoria_id: int | None
    categoria_nombre: str | None = None
    jugador1_id: int
    jugador2_id: int | None
    jugador1_nombre: str | None = None
    jugador2_nombre: str | None = None
    puntaje_jugador1: int
    puntaje_jugador2: int
    aciertos_jugador1: int = 0
    aciertos_jugador2: int = 0
    numero_ganador: int | None
    es_empate: bool


class DueloIniciarLocalRequest(BaseModel):
    """Datos enviados para iniciar un duelo local (mismo dispositivo)."""

    nombre_invitado: str


class DueloJuegoResponse(BaseModel):
    """Respuesta al iniciar/buscar un duelo: el duelo y las preguntas del jugador que consulta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: str
    modalidad: str
    categoria_id: int | None
    categoria_nombre: str | None = None
    jugador1_id: int | None = None
    jugador2_id: int | None = None
    jugador1_nombre: str | None = None
    jugador2_nombre: str | None = None
    preguntas: list[PreguntaJuegoResponse]

    @classmethod
    def desde_duelo(cls, duelo, numero_jugador: int) -> "DueloJuegoResponse":
        """Arma la respuesta mostrando solo las preguntas del jugador indicado."""
        preguntas_juego = []
        for pregunta_partida in duelo.preguntas_de_jugador(numero_jugador):
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
        categoria_nombre = (
            duelo.categoria_nombre
            if hasattr(duelo, "categoria_nombre")
            else (duelo.categoria.nombre if getattr(duelo, "categoria", None) else None)
        )
        estado_str = duelo.estado.value if hasattr(duelo.estado, "value") else str(duelo.estado)
        return cls(
            id=duelo.id,
            estado=estado_str,
            modalidad=duelo.modalidad,
            categoria_id=duelo.categoria_id,
            categoria_nombre=categoria_nombre,
            jugador1_id=duelo.jugador1_id,
            jugador2_id=duelo.jugador2_id,
            jugador1_nombre=duelo.jugador1_nombre,
            jugador2_nombre=duelo.jugador2_nombre,
            preguntas=preguntas_juego,
        )