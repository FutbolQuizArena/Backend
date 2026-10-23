"""Cálculo de puntaje por respuesta (Tarea 2.1.5)."""

from app.services.configuracion_partida import (
    TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS,
    esta_dentro_del_tiempo,
)

PUNTAJE_BASE_RESPUESTA_CORRECTA = 100
PUNTAJE_MINIMO_RESPUESTA_CORRECTA = 20


def calcular_puntaje(es_correcta: bool, tiempo_respuesta_segundos: int) -> int:
    """
    Calcula el puntaje obtenido en una pregunta.

    Reglas:
    - Si la respuesta es incorrecta, el puntaje es 0.
    - Si la respuesta llega fuera del tiempo límite, el puntaje es 0
      (aunque la opción elegida sea la correcta).
    - Si es correcta y a tiempo, el puntaje va de 100 (si responde muy rápido)
      a 20 (si responde justo antes de que se acabe el tiempo), de forma
      proporcional al tiempo usado.
    """
    if not es_correcta:
        return 0

    if not esta_dentro_del_tiempo(tiempo_respuesta_segundos):
        return 0

    proporcion_tiempo_restante = 1 - (
        tiempo_respuesta_segundos / TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS
    )
    rango_puntaje = PUNTAJE_BASE_RESPUESTA_CORRECTA - PUNTAJE_MINIMO_RESPUESTA_CORRECTA
    puntaje = PUNTAJE_MINIMO_RESPUESTA_CORRECTA + (rango_puntaje * proporcion_tiempo_restante)

    return round(puntaje)