"""Pruebas de emparejamiento y flujo de duelo en línea (Tarea 2.3.3)."""

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPartida
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.services import duelo_service


def _crear_categoria_con_preguntas(db: Session, cantidad: int = 10) -> Categoria:
    """Crea una categoría con `cantidad` preguntas de prueba, todas con respuesta correcta 'A'."""
    categoria = Categoria(nombre="Mundiales")
    db.add(categoria)
    db.commit()
    db.refresh(categoria)

    for numero in range(cantidad):
        pregunta = Pregunta(
            enunciado=f"Pregunta de mundiales numero {numero}",
            opcion_a="Correcta",
            opcion_b="Incorrecta 1",
            opcion_c="Incorrecta 2",
            opcion_d="Incorrecta 3",
            respuesta_correcta="A",
            categoria_id=categoria.id,
        )
        db.add(pregunta)
    db.commit()
    return categoria


def _crear_usuario(db: Session, email: str) -> Usuario:
    """Crea un usuario de prueba."""
    usuario = Usuario(nombre=email.split("@")[0], email=email, password_hash="hash_de_prueba")
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _responder_todas_las_preguntas(
    db: Session, duelo, usuario: Usuario, opcion: str, tiempo_segundos: int
) -> None:
    """Responde todas las preguntas de un jugador dentro de un duelo."""
    numero_jugador = 1 if duelo.jugador1_id == usuario.id else 2
    for pregunta_partida in duelo.preguntas_de_jugador(numero_jugador):
        duelo_service.responder_pregunta_duelo(
            db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada=opcion,
            tiempo_respuesta_segundos=tiempo_segundos,
            usuario_actual=usuario,
        )


def test_primer_jugador_queda_esperando_rival(sesion_db: Session) -> None:
    """El primer jugador en buscar duelo crea uno nuevo y queda PENDIENTE_RIVAL."""
    _crear_categoria_con_preguntas(sesion_db)
    jugador1 = _crear_usuario(sesion_db, "jugador1@futbolquiz.com")

    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador1)

    assert duelo.estado == EstadoPartida.PENDIENTE_RIVAL
    assert duelo.jugador1_id == jugador1.id
    assert duelo.jugador2_id is None
    assert len(duelo.preguntas_de_jugador(1)) == 10


def test_segundo_jugador_se_empareja_con_el_primero(sesion_db: Session) -> None:
    """El segundo jugador en buscar duelo se une al que estaba esperando, y el duelo pasa a EN_CURSO."""
    _crear_categoria_con_preguntas(sesion_db)
    jugador1 = _crear_usuario(sesion_db, "jugador1@futbolquiz.com")
    jugador2 = _crear_usuario(sesion_db, "jugador2@futbolquiz.com")

    duelo_de_jugador1 = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador1)
    duelo_de_jugador2 = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador2)

    assert duelo_de_jugador2.id == duelo_de_jugador1.id
    assert duelo_de_jugador2.estado == EstadoPartida.EN_CURSO
    assert duelo_de_jugador2.jugador2_id == jugador2.id
    assert len(duelo_de_jugador2.preguntas_de_jugador(2)) == 10


def test_duelo_se_finaliza_cuando_ambos_responden_y_gana_el_de_mas_puntaje(sesion_db: Session) -> None:
    """Cuando ambos jugadores respondieron todo, el duelo finaliza y gana quien respondió más rápido."""
    _crear_categoria_con_preguntas(sesion_db)
    jugador1 = _crear_usuario(sesion_db, "rapido@futbolquiz.com")
    jugador2 = _crear_usuario(sesion_db, "lento@futbolquiz.com")

    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador1)
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador2)

    # Jugador 1 responde rápido (más puntaje), jugador 2 responde lento (menos puntaje)
    _responder_todas_las_preguntas(sesion_db, duelo, jugador1, opcion="A", tiempo_segundos=1)
    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.estado == EstadoPartida.EN_CURSO  # todavía falta el jugador 2

    _responder_todas_las_preguntas(sesion_db, duelo, jugador2, opcion="A", tiempo_segundos=14)
    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)

    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.puntaje_jugador1 > duelo.puntaje_jugador2
    assert duelo.numero_ganador == 1
    assert duelo.es_empate is False
    assert jugador1.puntaje_total == duelo.puntaje_jugador1
    assert jugador2.puntaje_total == duelo.puntaje_jugador2


def test_duelo_propiedades_nombres_y_aciertos(sesion_db: Session) -> None:
    """Verifica que el modelo y esquema expongan correctamente los nombres y aciertos de ambos jugadores."""
    _crear_categoria_con_preguntas(sesion_db)
    jugador1 = _crear_usuario(sesion_db, "maradona@futbolquiz.com")
    jugador2 = _crear_usuario(sesion_db, "messi@futbolquiz.com")

    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador1)
    duelo = duelo_service.buscar_o_crear_duelo_online(sesion_db, usuario_actual=jugador2)

    assert duelo.jugador1_nombre == "maradona"
    assert duelo.jugador2_nombre == "messi"

    # Jugador 1 responde 10 preguntas bien
    _responder_todas_las_preguntas(sesion_db, duelo, jugador1, opcion="A", tiempo_segundos=2)
    # Jugador 2 responde 5 preguntas bien (opcion A) y 5 mal (opcion B)
    preguntas_j2 = duelo.preguntas_de_jugador(2)
    for p in preguntas_j2[:5]:
        duelo_service.responder_pregunta_duelo(sesion_db, p.id, opcion_seleccionada="A", tiempo_respuesta_segundos=3, usuario_actual=jugador2)
    for p in preguntas_j2[5:]:
        duelo_service.responder_pregunta_duelo(sesion_db, p.id, opcion_seleccionada="B", tiempo_respuesta_segundos=3, usuario_actual=jugador2)

    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.aciertos_jugador1 == 10
    assert duelo.aciertos_jugador2 == 5