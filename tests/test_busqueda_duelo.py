"""Vencimiento y cancelación de búsquedas online."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.enumeraciones import EstadoPartida
from app.models.partida_duelo import PartidaDuelo
from app.repositories import duelo_repository
from app.services import autenticacion_service, duelo_service
from tests.test_duelo import _crear_categoria_con_preguntas, _crear_usuario


@pytest.fixture
def jugadores(sesion_db, monkeypatch):
    monkeypatch.setattr(duelo_service.CONFIGURACION, "DUELO_ESPERA_MAX_SEGUNDOS", 120)
    _crear_categoria_con_preguntas(sesion_db)
    return [_crear_usuario(sesion_db, f"espera{n}@test.com") for n in range(3)]


def encabezado(usuario):
    return {"Authorization": f"Bearer {autenticacion_service.generar_token_jwt(usuario)}"}


def envejecer(db, duelo, segundos):
    duelo.fecha_inicio = datetime.now(timezone.utc) - timedelta(seconds=segundos)
    db.commit()


@pytest.mark.parametrize("edad", [120, 121, 3600])
def test_no_se_empareja_con_busqueda_vencida(sesion_db, jugadores, edad):
    vieja = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    envejecer(sesion_db, vieja, edad)
    nueva = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[1])
    sesion_db.refresh(vieja)
    assert nueva.id != vieja.id
    assert nueva.estado == EstadoPartida.PENDIENTE_RIVAL
    assert vieja.estado == EstadoPartida.FINALIZADA
    assert vieja.jugador2_id is None
    assert vieja.fecha_fin is not None
    assert not vieja.es_empate
    assert jugadores[0].puntaje_total == 0
    assert duelo_repository.listar_finalizados_por_jugador(sesion_db, jugadores[0].id) == []


def test_volver_a_buscar_reemplaza_espera_vencida(sesion_db, jugadores):
    vieja = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    envejecer(sesion_db, vieja, 121)
    nueva = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    assert nueva.id != vieja.id
    assert vieja.estado == EstadoPartida.FINALIZADA


def test_consultar_no_renueva_el_plazo_y_cierra_al_vencer(cliente, sesion_db, jugadores, monkeypatch):
    class Reloj(datetime):
        instante = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.instante

    monkeypatch.setattr(duelo_service, "datetime", Reloj)
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    duelo.fecha_inicio = Reloj.instante
    sesion_db.commit()
    url = f"/api/duelos/{duelo.id}"
    h = encabezado(jugadores[0])
    inicio = cliente.get(url, headers=h).json()
    assert inicio["busqueda_expira_en"] is not None
    Reloj.instante += timedelta(seconds=119)
    vigente = cliente.get(url, headers=h).json()
    assert vigente["estado"] == "PENDIENTE_RIVAL"
    assert vigente["busqueda_expira_en"] == inicio["busqueda_expira_en"]
    Reloj.instante += timedelta(seconds=1)
    vencida = cliente.get(url, headers=h).json()
    assert vencida["estado"] == "FINALIZADA"
    assert vencida["jugador2_id"] is None
    assert vencida["busqueda_expira_en"] is None
    assert not vencida["es_empate"]


def test_cancelacion_http_es_idempotente_y_no_deja_entrar_rivales(cliente, sesion_db, jugadores):
    inicio = cliente.post("/api/duelos/online", headers=encabezado(jugadores[0]))
    assert inicio.status_code == 200
    datos = inicio.json()
    assert datos["busqueda_expira_en"] is not None
    for _ in range(2):
        respuesta = cliente.post(f"/api/duelos/{datos['id']}/cancelar", headers=encabezado(jugadores[0]))
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json() == {"id": datos["id"], "estado": "FINALIZADA"}
    nueva = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[1])
    assert nueva.id != datos["id"]
    assert nueva.estado == EstadoPartida.PENDIENTE_RIVAL
    assert duelo_repository.listar_finalizados_por_jugador(sesion_db, jugadores[0].id) == []
    sesion_db.refresh(jugadores[0])
    assert jugadores[0].puntaje_total == 0


def test_otro_usuario_no_puede_cancelar(cliente, sesion_db, jugadores):
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    respuesta = cliente.post(f"/api/duelos/{duelo.id}/cancelar", headers=encabezado(jugadores[1]))
    assert respuesta.status_code == 403
    sesion_db.refresh(duelo)
    assert duelo.estado == EstadoPartida.PENDIENTE_RIVAL


def test_cancelar_requiere_sesion_y_duelo_existente(cliente, jugadores):
    assert cliente.post("/api/duelos/999999/cancelar").status_code == 401
    assert cliente.post("/api/duelos/999999/cancelar", headers=encabezado(jugadores[0])).status_code == 404


def test_cancelar_despues_del_emparejamiento_conserva_partida(cliente, sesion_db, jugadores):
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[1])
    respuesta = cliente.post(f"/api/duelos/{duelo.id}/cancelar", headers=encabezado(jugadores[0]))
    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "BUSQUEDA_YA_EMPAREJADA"
    sesion_db.refresh(duelo)
    assert duelo.estado == EstadoPartida.EN_CURSO
    assert duelo.jugador2_id == jugadores[1].id


def test_no_expira_partidas_en_curso_ni_duelos_locales(cliente, sesion_db, jugadores):
    online = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[1])
    local = duelo_service.iniciar_duelo_local(sesion_db, jugadores[0], "Invitado")
    envejecer(sesion_db, online, 3600)
    envejecer(sesion_db, local, 3600)
    duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[2])
    for duelo in (online, local):
        sesion_db.refresh(duelo)
        assert duelo.estado == EstadoPartida.EN_CURSO
    respuesta = cliente.post(f"/api/duelos/{local.id}/cancelar", headers=encabezado(jugadores[0]))
    assert respuesta.status_code == 422


def test_error_al_buscar_revierte_limpieza_y_creacion(sesion_db, jugadores, monkeypatch):
    vieja = duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[0])
    envejecer(sesion_db, vieja, 121)

    def fallar(*args, **kwargs):
        raise RuntimeError("Fallo simulado")

    monkeypatch.setattr(duelo_service.partida_repository, "agregar_preguntas_a_partida", fallar)
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        duelo_service.buscar_o_crear_duelo_online(sesion_db, jugadores[1])
    sesion_db.refresh(vieja)
    assert vieja.estado == EstadoPartida.PENDIENTE_RIVAL
    assert vieja.jugador2_id is None
    assert sesion_db.query(PartidaDuelo).count() == 1
