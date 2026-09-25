"""Enumeraciones del modelo de dominio."""

import enum


class RolUsuario(str, enum.Enum):
    """Roles disponibles para los usuarios del sistema."""

    JUGADOR = "JUGADOR"
    ADMINISTRADOR = "ADMINISTRADOR"


class EstadoTorneo(str, enum.Enum):
    """Estados posibles de un torneo."""

    ESPERANDO_JUGADORES = "ESPERANDO_JUGADORES"
    EN_CURSO = "EN_CURSO"
    FINALIZADO = "FINALIZADO"


class EstadoCruce(str, enum.Enum):
    """Estados posibles de un cruce eliminatorio."""

    PENDIENTE = "PENDIENTE"
    JUGADO = "JUGADO"


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


class EstadoPregunta(str, enum.Enum):
    """Estados posibles de una pregunta en el banco de contenido."""

    ACTIVA = "ACTIVA"
    BORRADOR = "BORRADOR"

