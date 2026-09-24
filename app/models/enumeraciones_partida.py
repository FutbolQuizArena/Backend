"""Enumeraciones del dominio de partidas y duelos (Módulo 2)."""

import enum


class EstadoPartida(str, enum.Enum):
    """Estados posibles de una partida. PENDIENTE_RIVAL solo aplica a duelos online."""

    PENDIENTE_RIVAL = "PENDIENTE_RIVAL"
    EN_CURSO = "EN_CURSO"
    FINALIZADA = "FINALIZADA"


class TipoPartida(str, enum.Enum):
    """Tipo de partida: individual o duelo contra otro jugador."""

    INDIVIDUAL = "INDIVIDUAL"
    DUELO = "DUELO"


class ModalidadDuelo(str, enum.Enum):
    """Modalidad de un duelo: en línea asincrónico o local (mismo dispositivo)."""

    ONLINE = "ONLINE"
    LOCAL = "LOCAL"