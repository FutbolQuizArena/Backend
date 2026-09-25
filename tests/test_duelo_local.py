"""Pruebas del flujo de duelo local (Tarea 2.3.4)."""

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPartida, ModalidadDuelo
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.services import duelo_service


def _crear_categoria_con_preguntas(db: Session, cantidad: int = 10) -> Categoria:
    """Crea una categoría con `cantidad` preguntas de prueba, todas con respuesta correcta 'A'."""
    categoria = Categoria(nombre="Copa America")
    db.add(categoria)
    db.commit()
    db.refresh(categoria)

    for numero in range(cantidad):
        pregunta = Pregunta(
            enunciado=f"Pregunta de copa america numero {numero}",
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


def test_duelo_local_arranca_en_curso_sin_esperar_rival(sesion_db: Session) -> None:
    """Un duelo LOCAL arranca EN_CURSO de inmediato, sin pasar por PENDIENTE_RIVAL."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db, "anfitrion@futbolquiz.com")

    duelo = duelo_service.iniciar_duelo_local(
        sesion_db, usuario_actual=usuario, nombre_invitado="Amigo Invitado"
    )

    assert duelo.estado == EstadoPartida.EN_CURSO
    assert duelo.modalidad == ModalidadDuelo.LOCAL.value
    assert duelo.nombre_invitado == "Amigo Invitado"
    assert duelo.jugador2_id is None
    assert len(duelo.preguntas_de_jugador(1)) == 10
    assert len(duelo.preguntas_de_jugador(2)) == 10


def test_duelo_local_ambos_jugadores_responden_las_mismas_preguntas(sesion_db: Session) -> None:
    """En un duelo local, jugador 1 y el invitado (jugador 2) responden el mismo set de preguntas."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db, "anfitrion2@futbolquiz.com")

    duelo = duelo_service.iniciar_duelo_local(
        sesion_db, usuario_actual=usuario, nombre_invitado="Rival de Sofa"
    )

    preguntas_jugador1 = {pp.pregunta_id for pp in duelo.preguntas_de_jugador(1)}
    preguntas_jugador2 = {pp.pregunta_id for pp in duelo.preguntas_de_jugador(2)}
    assert preguntas_jugador1 == preguntas_jugador2


def test_duelo_local_se_finaliza_cuando_ambos_responden_todo(sesion_db: Session) -> None:
    """El duelo local finaliza y determina ganador cuando se respondieron ambos lados."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db, "anfitrion3@futbolquiz.com")

    duelo = duelo_service.iniciar_duelo_local(
        sesion_db, usuario_actual=usuario, nombre_invitado="Invitado Lento"
    )

    for pregunta_partida in duelo.preguntas_de_jugador(1):
        duelo_service.responder_pregunta_duelo(
            sesion_db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada="A",
            tiempo_respuesta_segundos=1,
            usuario_actual=usuario,
        )

    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.estado == EstadoPartida.EN_CURSO  # falta responder el lado del invitado (jugador 2)

    for pregunta_partida in duelo.preguntas_de_jugador(2):
        pregunta_partida.registrar_respuesta(
            opcion="A", tiempo_segundos=10, es_correcta=True, puntaje=50
        )
        sesion_db.add(pregunta_partida)
    sesion_db.commit()

    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.puntaje_jugador1 > 0
    assert duelo.puntaje_jugador2 == 500