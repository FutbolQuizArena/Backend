"""Pruebas del flujo completo de partida individual (Tarea 2.3.2)."""

import pytest
from sqlalchemy.orm import Session

from app.core.excepciones_partida import PartidaYaFinalizadaError, PreguntaYaRespondidaError
from app.models.categoria import Categoria
from app.models.enumeraciones_partida import EstadoPartida
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.services import partida_service


def _crear_categoria_con_preguntas(db: Session, cantidad: int = 10) -> Categoria:
    """Crea una categoría con `cantidad` preguntas de prueba, todas con respuesta correcta 'A'."""
    categoria = Categoria(nombre="Historia del Fútbol")
    db.add(categoria)
    db.commit()
    db.refresh(categoria)

    for numero in range(cantidad):
        pregunta = Pregunta(
            enunciado=f"Pregunta de prueba numero {numero}",
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


def _crear_usuario(db: Session, email: str = "jugador@futbolquiz.com") -> Usuario:
    """Crea un usuario de prueba."""
    usuario = Usuario(nombre="Jugador de Prueba", email=email, password_hash="hash_de_prueba")
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def test_iniciar_partida_individual_crea_10_preguntas(sesion_db: Session) -> None:
    """Al iniciar una partida individual, se le asignan exactamente 10 preguntas."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db)

    partida = partida_service.iniciar_partida_individual(sesion_db, usuario_actual=usuario)

    assert partida.id is not None
    assert partida.jugador_id == usuario.id
    assert partida.estado == EstadoPartida.EN_CURSO
    assert len(partida.preguntas) == 10


def test_responder_pregunta_correcta_suma_puntaje(sesion_db: Session) -> None:
    """Responder correctamente y rápido debe sumar puntaje a esa pregunta."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db)
    partida = partida_service.iniciar_partida_individual(sesion_db, usuario_actual=usuario)
    primera_pregunta = partida.preguntas[0]

    pregunta_respondida = partida_service.responder_pregunta_partida(
        sesion_db,
        pregunta_partida_id=primera_pregunta.id,
        opcion_seleccionada="A",
        tiempo_respuesta_segundos=1,
        usuario_actual=usuario,
    )

    assert pregunta_respondida.esta_respondida == 1
    assert pregunta_respondida.es_correcta == 1
    assert pregunta_respondida.puntaje_obtenido > 0


def test_finalizar_partida_guarda_resultado_y_suma_puntaje_a_usuario(sesion_db: Session) -> None:
    """Al finalizar, la partida guarda el puntaje total y se lo suma al usuario."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db)
    partida = partida_service.iniciar_partida_individual(sesion_db, usuario_actual=usuario)

    for pregunta_partida in partida.preguntas:
        partida_service.responder_pregunta_partida(
            sesion_db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada="A",
            tiempo_respuesta_segundos=1,
            usuario_actual=usuario,
        )

    partida_finalizada = partida_service.finalizar_partida_individual(
        sesion_db, partida_id=partida.id, usuario_actual=usuario
    )

    assert partida_finalizada.estado == EstadoPartida.FINALIZADA
    assert partida_finalizada.puntaje_final > 0
    assert partida_finalizada.fecha_fin is not None
    assert usuario.puntaje_total == partida_finalizada.puntaje_final


def test_no_se_puede_responder_una_partida_ya_finalizada(sesion_db: Session) -> None:
    """Intentar responder una pregunta de una partida finalizada debe fallar."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db)
    partida = partida_service.iniciar_partida_individual(sesion_db, usuario_actual=usuario)

    for pregunta_partida in partida.preguntas:
        partida_service.responder_pregunta_partida(
            sesion_db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada="A",
            tiempo_respuesta_segundos=1,
            usuario_actual=usuario,
        )
    partida_service.finalizar_partida_individual(sesion_db, partida_id=partida.id, usuario_actual=usuario)

    with pytest.raises(PartidaYaFinalizadaError):
        partida_service.finalizar_partida_individual(
            sesion_db, partida_id=partida.id, usuario_actual=usuario
        )


def test_no_se_puede_responder_dos_veces_la_misma_pregunta(sesion_db: Session) -> None:
    """Responder una pregunta que ya fue respondida debe fallar."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db)
    partida = partida_service.iniciar_partida_individual(sesion_db, usuario_actual=usuario)
    primera_pregunta = partida.preguntas[0]

    partida_service.responder_pregunta_partida(
        sesion_db,
        pregunta_partida_id=primera_pregunta.id,
        opcion_seleccionada="A",
        tiempo_respuesta_segundos=1,
        usuario_actual=usuario,
    )

    with pytest.raises(PreguntaYaRespondidaError):
        partida_service.responder_pregunta_partida(
            sesion_db,
            pregunta_partida_id=primera_pregunta.id,
            opcion_seleccionada="B",
            tiempo_respuesta_segundos=1,
            usuario_actual=usuario,
        )