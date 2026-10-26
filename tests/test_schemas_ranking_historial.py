"""Pruebas de los esquemas del ranking y del historial (Tarea 4.1.6)."""

import pytest
from pydantic import ValidationError

from app.models.enumeraciones import EstadoTorneo
from app.schemas import (
    HistorialDueloItem,
    HistorialTorneoItem,
    JugadorRankingResponse,
    RankingResponse,
    ResultadoDuelo,
)


def _jugador(posicion: int = 1, puntaje_total: int = 100) -> JugadorRankingResponse:
    return JugadorRankingResponse(
        posicion=posicion, usuario_id=posicion, nombre=f"jugador{posicion}", puntaje_total=puntaje_total
    )


def test_jugador_ranking_se_arma_desde_un_objeto_con_atributos() -> None:
    """El schema se puede construir directo desde un objeto ORM (from_attributes)."""

    class UsuarioFalso:
        posicion = 3
        usuario_id = 7
        nombre = "Lionel"
        puntaje_total = 250

    jugador = JugadorRankingResponse.model_validate(UsuarioFalso())

    assert jugador.posicion == 3
    assert jugador.nombre == "Lionel"
    assert jugador.puntaje_total == 250


def test_jugador_ranking_no_expone_datos_sensibles() -> None:
    """El ranking lo ve cualquier usuario: no debe incluir email ni contraseña."""
    campos = set(JugadorRankingResponse.model_fields)

    assert campos == {"posicion", "usuario_id", "nombre", "puntaje_total"}


@pytest.mark.parametrize("posicion", [0, -1])
def test_jugador_ranking_rechaza_posicion_menor_a_uno(posicion: int) -> None:
    with pytest.raises(ValidationError):
        _jugador(posicion=posicion)


def test_jugador_ranking_rechaza_puntaje_negativo() -> None:
    with pytest.raises(ValidationError):
        _jugador(puntaje_total=-5)


def test_ranking_response_mi_posicion_es_opcional() -> None:
    """Quien no participa del ranking (ej. un administrador) recibe mi_posicion en None."""
    ranking = RankingResponse(
        jugadores=[_jugador(1), _jugador(2, 80)], total_jugadores=2, pagina=1, tamano_pagina=20
    )

    assert ranking.mi_posicion is None
    assert len(ranking.jugadores) == 2


def test_ranking_response_acepta_mi_posicion() -> None:
    ranking = RankingResponse(
        jugadores=[_jugador(1)],
        total_jugadores=50,
        pagina=1,
        tamano_pagina=20,
        mi_posicion=_jugador(47, 10),
    )

    assert ranking.mi_posicion.posicion == 47


@pytest.mark.parametrize("pagina,tamano_pagina", [(0, 20), (1, 0)])
def test_ranking_response_rechaza_paginacion_invalida(pagina: int, tamano_pagina: int) -> None:
    with pytest.raises(ValidationError):
        RankingResponse(jugadores=[], total_jugadores=0, pagina=pagina, tamano_pagina=tamano_pagina)


def test_resultado_duelo_tiene_los_tres_valores_en_mayusculas() -> None:
    assert {r.value for r in ResultadoDuelo} == {"VICTORIA", "DERROTA", "EMPATE"}


def test_historial_duelo_acepta_resultado_como_texto() -> None:
    duelo = HistorialDueloItem(
        duelo_id=1, modalidad="LOCAL", puntaje_propio=80, puntaje_rival=60, resultado="VICTORIA"
    )

    assert duelo.resultado is ResultadoDuelo.VICTORIA
    assert duelo.rival_nombre is None


def test_historial_duelo_rechaza_resultado_desconocido() -> None:
    with pytest.raises(ValidationError):
        HistorialDueloItem(
            duelo_id=1, modalidad="ONLINE", puntaje_propio=1, puntaje_rival=2, resultado="GANADO"
        )


def test_historial_torneo_sin_cruces_no_tiene_ronda_alcanzada() -> None:
    torneo = HistorialTorneoItem(torneo_id=1, nombre="Copa", estado=EstadoTorneo.EN_CURSO)

    assert torneo.ronda_alcanzada is None
    assert torneo.es_campeon is False


def test_historial_torneo_campeon_con_ronda_alcanzada() -> None:
    torneo = HistorialTorneoItem(
        torneo_id=1, nombre="Copa", estado="FINALIZADO", ronda_alcanzada=3, es_campeon=True
    )

    assert torneo.estado is EstadoTorneo.FINALIZADO
    assert torneo.ronda_alcanzada == 3
    assert torneo.es_campeon is True


def test_historial_torneo_rechaza_ronda_cero() -> None:
    with pytest.raises(ValidationError):
        HistorialTorneoItem(torneo_id=1, nombre="Copa", estado="FINALIZADO", ronda_alcanzada=0)