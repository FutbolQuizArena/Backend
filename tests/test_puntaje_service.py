"""Pruebas unitarias para el cálculo de puntaje y control de tiempo (Tarea 2.3.1)."""

from app.services.configuracion_partida import (
    TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS,
    esta_dentro_del_tiempo,
)
from app.services.puntaje_service import calcular_puntaje


def test_respuesta_incorrecta_no_suma_puntaje() -> None:
    """Una respuesta incorrecta siempre vale 0 puntos, sin importar el tiempo."""
    assert calcular_puntaje(es_correcta=False, tiempo_respuesta_segundos=2) == 0


def test_respuesta_correcta_fuera_de_tiempo_no_suma_puntaje() -> None:
    """Una respuesta correcta pero fuera de tiempo vale 0 puntos."""
    tiempo_excedido = TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS + 1
    assert calcular_puntaje(es_correcta=True, tiempo_respuesta_segundos=tiempo_excedido) == 0


def test_respuesta_correcta_e_inmediata_da_puntaje_maximo() -> None:
    """Responder correctamente en el instante 0 da el puntaje máximo (100)."""
    assert calcular_puntaje(es_correcta=True, tiempo_respuesta_segundos=0) == 100


def test_respuesta_correcta_justo_al_limite_da_puntaje_minimo() -> None:
    """Responder correctamente justo al límite de tiempo da el puntaje mínimo (20)."""
    puntaje = calcular_puntaje(
        es_correcta=True, tiempo_respuesta_segundos=TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS
    )
    assert puntaje == 20


def test_respuesta_correcta_a_mitad_de_tiempo_da_puntaje_intermedio() -> None:
    """Responder a la mitad del tiempo permitido da un puntaje entre el mínimo y el máximo."""
    mitad_tiempo = TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS / 2
    puntaje = calcular_puntaje(es_correcta=True, tiempo_respuesta_segundos=mitad_tiempo)
    assert 20 < puntaje < 100


def test_esta_dentro_del_tiempo_limite_es_valido() -> None:
    """El tiempo límite exacto todavía se considera dentro de tiempo."""
    assert esta_dentro_del_tiempo(TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS) is True


def test_esta_fuera_de_tiempo_cuando_excede_el_limite() -> None:
    """Un segundo más que el límite ya se considera fuera de tiempo."""
    assert esta_dentro_del_tiempo(TIEMPO_LIMITE_POR_PREGUNTA_SEGUNDOS + 1) is False