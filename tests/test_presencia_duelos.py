"""Desconexión, reconexión y cierre independiente del navegador."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.excepciones import PartidaYaFinalizadaError
from app.models.enumeraciones import EstadoPartida
from app.services import duelo_service
from tests.test_duelo import _crear_categoria_con_preguntas, _crear_usuario, _responder_todas_las_preguntas
from tests.test_torneos_jugables import encabezado
from tests.test_torneos_jugables import jugadores, crear_torneo, iniciar
from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce
from app.services import presencia_duelos
from contextlib import contextmanager
import asyncio


@pytest.mark.parametrize("ambos", [False, True])
def test_abandono_en_torneo_o_reintento_sin_ganador(cliente, sesion_db, jugadores, ambos):
    torneo = crear_torneo(sesion_db, jugadores)
    cruce = sesion_db.query(Cruce).filter_by(torneo_id=torneo.id).first()
    a, b = cruce.jugador_a.usuario, cruce.jugador_b.usuario
    datos = iniciar(cliente, torneo, cruce, a)
    duelo = duelo_service.duelo_repository.obtener_duelo_por_id(sesion_db, datos["duelo_id"])
    ausencias(sesion_db, duelo, 65 if ambos else 0, 65)
    duelo_service.cerrar_duelos_desconectados(sesion_db)
    sesion_db.refresh(cruce)
    if ambos:
        assert cruce.estado == EstadoCruce.PENDIENTE
        assert cruce.duelo_id is None
        assert cruce.ganador_id is None
        nuevo = iniciar(cliente, torneo, cruce, a)
        assert nuevo["duelo_id"] != duelo.id
    else:
        assert cruce.estado == EstadoCruce.JUGADO
        assert cruce.ganador.usuario_id == a.id
        assert duelo.numero_ganador == 1


@pytest.fixture
def partida(sesion_db):
    _crear_categoria_con_preguntas(sesion_db)
    a = _crear_usuario(sesion_db, "presencia1@test.com")
    b = _crear_usuario(sesion_db, "presencia2@test.com")
    duelo_service.buscar_o_crear_duelo_online(sesion_db, a)
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, b)
    return duelo, a, b


def ausencias(db, duelo, segundos1, segundos2):
    ahora = datetime.now(timezone.utc)
    duelo.ultima_presencia_jugador1 = ahora - timedelta(seconds=segundos1)
    duelo.ultima_presencia_jugador2 = ahora - timedelta(seconds=segundos2)
    db.commit()


def test_abandono_cierra_y_premia_una_sola_vez(sesion_db, partida, cliente):
    duelo, a, b = partida
    duelo_service.responder_pregunta_duelo(sesion_db, duelo.preguntas_de_jugador(1)[0].id, "A", 1, a)
    ausencias(sesion_db, duelo, 0, 60)
    duelo_service.cerrar_duelos_desconectados(sesion_db)
    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.numero_ganador == 1
    assert duelo.motivo_finalizacion == "ABANDONO"
    puntos = a.puntaje_total
    assert puntos == 95
    for _ in range(2):
        duelo_service.registrar_presencia(sesion_db, duelo.id, b)
        duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert a.puntaje_total == puntos
    with pytest.raises(PartidaYaFinalizadaError):
        duelo_service.responder_pregunta_duelo(sesion_db, duelo.preguntas_de_jugador(2)[0].id, "A", 1, b)
    historial = cliente.get("/api/historial/duelos", headers=encabezado(a)).json()
    assert historial["duelos"][0]["resultado"] == "VICTORIA"
    assert historial["duelos"][0]["motivo_finalizacion"] == "ABANDONO"


def test_reconexion_antes_del_plazo_conserva_progreso(sesion_db, partida, cliente):
    duelo, a, b = partida
    pregunta = duelo.preguntas_de_jugador(2)[0]
    duelo_service.responder_pregunta_duelo(sesion_db, pregunta.id, "A", 2, b)
    ausencias(sesion_db, duelo, 0, 59)
    r = cliente.post(f"/api/duelos/{duelo.id}/presencia", headers=encabezado(b))
    assert r.status_code == 200
    assert r.json()["estado"] == "EN_CURSO"
    assert not r.json()["jugador2_ausente"]
    juego = cliente.get(f"/api/duelos/{duelo.id}/juego", headers=encabezado(b)).json()
    assert juego["preguntas"][0]["esta_respondida"]
    assert juego["preguntas"][0]["id"] == pregunta.id
    assert juego["puntaje_propio"] == 89
    assert juego["aciertos_propios"] == 1
    assert all("respuesta_correcta" not in p for p in juego["preguntas"])
    # Abrir otra pestaña y volver a buscar recupera el mismo duelo.
    retomado = duelo_service.buscar_o_crear_duelo_online(sesion_db, b)
    assert retomado.id == duelo.id
    assert retomado.preguntas_de_jugador(2)[0].esta_respondida


def test_heartbeat_tardio_no_revive(sesion_db, partida):
    duelo, a, b = partida
    ausencias(sesion_db, duelo, 0, 61)
    duelo_service.registrar_presencia(sesion_db, duelo.id, b)
    assert duelo.numero_ganador == 1
    assert duelo.motivo_finalizacion == "ABANDONO"


def test_ambos_ausentes_no_da_victoria_arbitraria(sesion_db, partida, cliente):
    duelo, a, b = partida
    ausencias(sesion_db, duelo, 70, 65)
    duelo_service.cerrar_duelos_desconectados(sesion_db)
    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.numero_ganador is None
    assert not duelo.es_empate
    assert duelo.motivo_finalizacion == "SIN_CONEXION"
    assert a.puntaje_total == b.puntaje_total == 0
    historial = cliente.get("/api/historial/duelos", headers=encabezado(a)).json()
    assert historial["duelos"][0]["resultado"] == "SIN_RESULTADO"


def test_no_premia_a_rival_tambien_ausente(sesion_db, partida):
    duelo, a, b = partida
    ausencias(sesion_db, duelo, 30, 61)
    duelo_service.cerrar_duelos_desconectados(sesion_db)
    assert duelo.estado == EstadoPartida.EN_CURSO
    duelo_service.registrar_presencia(sesion_db, duelo.id, a)
    assert duelo.numero_ganador == 1


def test_quien_termino_no_pierde_por_irse(sesion_db, partida):
    duelo, a, b = partida
    _responder_todas_las_preguntas(sesion_db, duelo, a, "A", 1)
    ausencias(sesion_db, duelo, 200, 0)
    duelo_service.cerrar_duelos_desconectados(sesion_db)
    assert duelo.estado == EstadoPartida.EN_CURSO
    _responder_todas_las_preguntas(sesion_db, duelo, b, "A", 14)
    duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.numero_ganador == 1
    assert duelo.motivo_finalizacion is None


def test_presencia_sin_responder_y_acceso_ajeno(sesion_db, partida, cliente):
    duelo, a, b = partida
    otro = _crear_usuario(sesion_db, "ajeno@test.com")
    for accion in ("presencia", "juego"):
        metodo = cliente.post if accion == "presencia" else cliente.get
        assert metodo(f"/api/duelos/{duelo.id}/{accion}", headers=encabezado(otro)).status_code in (401, 403)
    for _ in range(3):
        ausencias(sesion_db, duelo, 10, 0)
        duelo_service.registrar_presencia(sesion_db, duelo.id, a)
    assert duelo.estado == EstadoPartida.EN_CURSO
    assert not any(p.esta_respondida for p in duelo.preguntas)


def test_respuesta_detecta_abandono_y_persiste_cierre(sesion_db, partida):
    duelo, a, b = partida
    ausencias(sesion_db, duelo, 0, 61)
    with pytest.raises(PartidaYaFinalizadaError):
        duelo_service.responder_pregunta_duelo(sesion_db, duelo.preguntas_de_jugador(2)[0].id, "A", 1, b)
    sesion_db.refresh(duelo)
    assert duelo.motivo_finalizacion == "ABANDONO"
    assert duelo.numero_ganador == 1


def test_revision_del_servidor_cierra_sin_peticiones_http(sesion_db, partida, monkeypatch):
    duelo, a, b = partida
    ausencias(sesion_db, duelo, 0, 61)

    @contextmanager
    def sesion_de_pruebas():
        yield sesion_db

    monkeypatch.setattr(presencia_duelos, "SesionLocal", sesion_de_pruebas)
    presencia_duelos.revisar_duelos()
    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.numero_ganador == 1


def test_revision_periodica_reintenta_errores_y_respeta_cancelacion(monkeypatch):
    esperas = []
    revisiones = []

    async def esperar(segundos):
        esperas.append(segundos)
        if len(esperas) == 3:
            raise asyncio.CancelledError

    def revisar():
        revisiones.append(True)
        if len(revisiones) == 1:
            raise RuntimeError("Interrupción transitoria de DB")

    monkeypatch.setattr(presencia_duelos.asyncio, "sleep", esperar)
    monkeypatch.setattr(presencia_duelos, "revisar_duelos", revisar)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(presencia_duelos._revisar_periodicamente())
    assert esperas == [5, 5, 5]
    assert len(revisiones) == 2
