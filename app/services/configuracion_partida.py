"""
Configuración y utilidades de control de tiempo para partidas (Tarea 2.1.4).

Estas constantes definen las reglas del juego: cuántas preguntas tiene una
partida y cuántos segundos tiene el jugador para responder cada una.
"""

CANTIDAD_PREGUNTAS_POR_PARTIDA = 10
TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS = 15


def esta_dentro_del_tiempo(tiempo_respuesta_segundos: int) -> bool:
    """
    Indica si una respuesta llegó dentro del tiempo límite permitido.

    Si el jugador tarda más que TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS,
    la respuesta se considera fuera de tiempo (y no suma puntaje,
    aunque la opción elegida sea la correcta).
    """
    return tiempo_respuesta_segundos <= TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS