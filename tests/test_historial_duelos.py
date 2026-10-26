"""Pruebas del historial de duelos (Tarea 4.1.4, RF-15)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPartida, ModalidadDuelo, TipoPartida
from app.models.partida_duelo import PartidaDuelo
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.services import autenticacion_service, duelo_service

URL_HISTORIAL = "/api/historial/duelos"
FECHA_BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _crear_usuario(db: Session, nombre: str) -> Usuario:
    usuario = Usuario(
        nombre=nombre, email=f"{nombre.lower()}@futbolquiz.com", password_hash="hash_de_prueba"
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _crear_categoria(db: Session, nombre: str = "Mundiales") -> Categoria:
    categoria = Categoria(nombre=nombre)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


def _crear_duelo(
    db: Session,
    categoria: Categoria,
    jugador1: Usuario,
    jugador2: Usuario | None = None,
    puntaje1: int = 0,
    puntaje2: int = 0,
    numero_ganador: int | None = None,
    estado: EstadoPartida = EstadoPartida.FINALIZADA,
    modalidad: ModalidadDuelo = ModalidadDuelo.ONLINE,
    nombre_invitado: str | None = None,
    fecha_fin: datetime | None = FECHA_BASE,
) -> PartidaDuelo:
    duelo = PartidaDuelo(
        tipo=TipoPartida.DUELO,
        categoria_id=categoria.id,
        estado=estado,
        modalidad=modalidad.value,
        jugador1_id=jugador1.id,
        jugador2_id=jugador2.id if jugador2 else None,
        nombre_invitado=nombre_invitado,
        puntaje_jugador1=puntaje1,
        puntaje_jugador2=puntaje2,
        numero_ganador=numero_ganador,
        fecha_fin=fecha_fin,
    )
    db.add(duelo)
    db.commit()
    db.refresh(duelo)
    return duelo


def _encabezado(usuario: Usuario) -> dict[str, str]:
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


def test_historial_duelos_requiere_autenticacion(cliente: TestClient) -> None:
    assert cliente.get(URL_HISTORIAL).status_code == 401


def test_historial_duelos_sin_duelos_devuelve_lista_vacia(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Nuevo")

    respuesta = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"duelos": [], "total": 0}


def test_historial_duelos_se_ve_desde_el_lado_de_cada_jugador(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db, "Copa America")
    ganador = _crear_usuario(sesion_db, "Ganador")
    perdedor = _crear_usuario(sesion_db, "Perdedor")
    _crear_duelo(sesion_db, categoria, ganador, perdedor, 90, 40, numero_ganador=1)

    vista_ganador = cliente.get(URL_HISTORIAL, headers=_encabezado(ganador)).json()["duelos"][0]
    vista_perdedor = cliente.get(URL_HISTORIAL, headers=_encabezado(perdedor)).json()["duelos"][0]

    assert vista_ganador["resultado"] == "VICTORIA"
    assert vista_ganador["rival_nombre"] == "Perdedor"
    assert (vista_ganador["puntaje_propio"], vista_ganador["puntaje_rival"]) == (90, 40)
    assert vista_ganador["categoria_nombre"] == "Copa America"
    assert vista_ganador["modalidad"] == "ONLINE"
    assert vista_perdedor["resultado"] == "DERROTA"
    assert vista_perdedor["rival_nombre"] == "Ganador"
    assert (vista_perdedor["puntaje_propio"], vista_perdedor["puntaje_rival"]) == (40, 90)


def test_historial_duelos_empate(cliente: TestClient, sesion_db: Session) -> None:
    categoria = _crear_categoria(sesion_db)
    uno = _crear_usuario(sesion_db, "Uno")
    dos = _crear_usuario(sesion_db, "Dos")
    _crear_duelo(sesion_db, categoria, uno, dos, 50, 50, numero_ganador=None)

    item = cliente.get(URL_HISTORIAL, headers=_encabezado(dos)).json()["duelos"][0]

    assert item["resultado"] == "EMPATE"


def test_historial_duelos_local_usa_el_nombre_del_invitado_como_rival(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db)
    anfitrion = _crear_usuario(sesion_db, "Anfitrion")
    _crear_duelo(
        sesion_db,
        categoria,
        anfitrion,
        puntaje1=70,
        puntaje2=30,
        numero_ganador=1,
        modalidad=ModalidadDuelo.LOCAL,
        nombre_invitado="Amigo",
    )

    item = cliente.get(URL_HISTORIAL, headers=_encabezado(anfitrion)).json()["duelos"][0]

    assert item["modalidad"] == "LOCAL"
    assert item["rival_nombre"] == "Amigo"
    assert item["resultado"] == "VICTORIA"


def test_historial_duelos_excluye_en_curso_y_cerrados_sin_rival(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db)
    jugador = _crear_usuario(sesion_db, "Jugador")
    rival = _crear_usuario(sesion_db, "Rival")
    _crear_duelo(sesion_db, categoria, jugador, rival, estado=EstadoPartida.EN_CURSO)
    _crear_duelo(sesion_db, categoria, jugador, estado=EstadoPartida.FINALIZADA)  # sin rival
    jugado = _crear_duelo(sesion_db, categoria, jugador, rival, 10, 5, numero_ganador=1)

    cuerpo = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador)).json()

    assert cuerpo["total"] == 1
    assert cuerpo["duelos"][0]["duelo_id"] == jugado.id


def test_historial_duelos_solo_muestra_los_del_usuario_autenticado(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db)
    yo = _crear_usuario(sesion_db, "Yo")
    amigo = _crear_usuario(sesion_db, "Amigo")
    ajeno_a = _crear_usuario(sesion_db, "AjenoA")
    ajeno_b = _crear_usuario(sesion_db, "AjenoB")
    mio = _crear_duelo(sesion_db, categoria, yo, amigo, 1, 2, numero_ganador=2)
    _crear_duelo(sesion_db, categoria, ajeno_a, ajeno_b, 3, 4, numero_ganador=2)

    cuerpo = cliente.get(URL_HISTORIAL, headers=_encabezado(yo)).json()

    assert [d["duelo_id"] for d in cuerpo["duelos"]] == [mio.id]


def test_historial_duelos_ordena_del_mas_reciente_al_mas_antiguo(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db)
    jugador = _crear_usuario(sesion_db, "Jugador")
    rival = _crear_usuario(sesion_db, "Rival")
    _crear_duelo(sesion_db, categoria, jugador, rival, 10, 0, 1, fecha_fin=FECHA_BASE)
    _crear_duelo(
        sesion_db, categoria, jugador, rival, 30, 0, 1, fecha_fin=FECHA_BASE + timedelta(days=2)
    )
    _crear_duelo(
        sesion_db, categoria, jugador, rival, 20, 0, 1, fecha_fin=FECHA_BASE + timedelta(days=1)
    )

    cuerpo = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador)).json()

    assert [d["puntaje_propio"] for d in cuerpo["duelos"]] == [30, 20, 10]


def test_historial_duelos_sin_fecha_fin_usa_la_fecha_de_inicio(
    cliente: TestClient, sesion_db: Session
) -> None:
    categoria = _crear_categoria(sesion_db)
    jugador = _crear_usuario(sesion_db, "Jugador")
    rival = _crear_usuario(sesion_db, "Rival")
    duelo = _crear_duelo(sesion_db, categoria, jugador, rival, 5, 1, 1, fecha_fin=None)

    item = cliente.get(URL_HISTORIAL, headers=_encabezado(jugador)).json()["duelos"][0]

    assert item["fecha_fin"] is not None
    assert item["fecha_fin"].startswith(str(duelo.fecha_inicio.year))


def test_finalizar_un_duelo_guarda_su_fecha_de_fin(sesion_db: Session) -> None:
    categoria = _crear_categoria(sesion_db)
    for numero in range(10):
        sesion_db.add(
            Pregunta(
                enunciado=f"Pregunta de historial {numero}",
                opcion_a="Correcta",
                opcion_b="Incorrecta 1",
                opcion_c="Incorrecta 2",
                opcion_d="Incorrecta 3",
                respuesta_correcta="A",
                categoria_id=categoria.id,
            )
        )
    sesion_db.commit()
    anfitrion = _crear_usuario(sesion_db, "Anfitrion")
    duelo = duelo_service.iniciar_duelo_local(
        sesion_db, usuario_actual=anfitrion, nombre_invitado="Invitado"
    )
    for numero_jugador in (1, 2):
        for pregunta_partida in duelo.preguntas_de_jugador(numero_jugador):
            pregunta_partida.registrar_respuesta(
                opcion="A", tiempo_segundos=1, es_correcta=True, puntaje=10
            )
            sesion_db.add(pregunta_partida)
    sesion_db.commit()
    assert duelo.fecha_fin is None

    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)

    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.fecha_fin is not None