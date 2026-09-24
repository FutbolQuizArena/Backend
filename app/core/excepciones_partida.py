"""Excepciones propias del dominio de partidas y duelos (Módulo 2)."""

from app.core.excepciones import ExcepcionBase
from fastapi import status


class PartidaYaFinalizadaError(ExcepcionBase):
    """Excepción lanzada cuando se intenta operar sobre una partida que ya finalizó."""

    def __init__(
        self,
        mensaje: str = "La partida ya se encuentra finalizada",
        detalle: str | None = None,
    ) -> None:
        super().__init__(
            codigo="PARTIDA_YA_FINALIZADA",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_400_BAD_REQUEST,
        )


class PreguntaYaRespondidaError(ExcepcionBase):
    """Excepción lanzada cuando se intenta responder una pregunta que ya fue respondida."""

    def __init__(
        self,
        mensaje: str = "Esta pregunta ya fue respondida",
        detalle: str | None = None,
    ) -> None:
        super().__init__(
            codigo="PREGUNTA_YA_RESPONDIDA",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_400_BAD_REQUEST,
        )