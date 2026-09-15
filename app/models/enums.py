"""Enumeraciones del modelo de dominio."""

import enum


class RolUsuario(str, enum.Enum):
    """Roles disponibles para los usuarios del sistema."""

    JUGADOR = "JUGADOR"
    ADMINISTRADOR = "ADMINISTRADOR"

