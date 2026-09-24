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

