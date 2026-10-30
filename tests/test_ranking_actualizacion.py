"""Pruebas de la actualización automática del puntaje acumulado del ranking (Tarea 4.1.1)."""

from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPartida
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.services import duelo_service, partida_service, ranking_service

ID_USUARIO_INEXISTENTE = 999999


def _crear_categoria_con_preguntas(db: Session, cantidad: int = 10) -> Categoria:
    """Crea una categoría con `cantidad` preguntas de prueba, todas con respuesta correcta 'A'."""
    categoria = Categoria(nombre="Ranking del Fútbol")
    db.add(categoria)
    db.commit()
    db.refresh(categoria)

    for numero in range(cantidad):
        pregunta = Pregunta(
            enunciado=f"Pregunta de ranking numero {numero}",
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


def _crear_usuario(db: Session, email: str, puntaje_inicial: int = 0) -> Usuario:
    """Crea un usuario de prueba con un puntaje acumulado inicial."""
    usuario = Usuario(
        nombre=email.split("@")[0],
        email=email,
        password_hash="hash_de_prueba",
        puntaje_total=puntaje_inicial,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _jugar_partida_individual_completa(db: Session, usuario: Usuario):
    """Juega y finaliza una partida individual respondiendo todo bien y rápido."""
    partida = partida_service.iniciar_partida_individual(db, usuario_actual=usuario)
    for pregunta_partida in partida.preguntas:
        partida_service.responder_pregunta_partida(
            db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada="A",
            tiempo_respuesta_segundos=1,
            usuario_actual=usuario,
        )
    return partida_service.finalizar_partida_individual(
        db, partida_id=partida.id, usuario_actual=usuario
    )


def test_acumular_puntaje_suma_al_total_existente(sesion_db: Session) -> None:
    """Los puntos nuevos se suman al puntaje que el usuario ya tenía."""
    usuario = _crear_usuario(sesion_db, "acumula@futbolquiz.com", puntaje_inicial=100)

    usuario_actualizado = ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=50)

    assert usuario_actualizado is not None
    assert usuario_actualizado.puntaje_total == 150


def test_acumular_puntaje_varias_veces_suma_cada_vez(sesion_db: Session) -> None:
    """Cada llamada suma sobre el valor actual de la base, sin pisar las anteriores."""
    usuario = _crear_usuario(sesion_db, "varias@futbolquiz.com")

    ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=30)
    ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=70)
    ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=5)

    assert usuario_repository.obtener_por_id(sesion_db, id=usuario.id).puntaje_total == 105


def test_acumular_cero_puntos_no_modifica_el_puntaje(sesion_db: Session) -> None:
    """Una partida sin puntos (todo incorrecto) deja el puntaje acumulado igual."""
    usuario = _crear_usuario(sesion_db, "cero@futbolquiz.com", puntaje_inicial=40)

    usuario_actualizado = ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=0)

    assert usuario_actualizado is not None
    assert usuario_actualizado.puntaje_total == 40


def test_acumular_puntos_negativos_nunca_baja_el_puntaje(sesion_db: Session) -> None:
    """Los puntos negativos se ignoran: el puntaje acumulado solo puede subir."""
    usuario = _crear_usuario(sesion_db, "negativo@futbolquiz.com", puntaje_inicial=40)

    usuario_actualizado = ranking_service.acumular_puntaje(sesion_db, usuario_id=usuario.id, puntos=-25)

    assert usuario_actualizado is not None
    assert usuario_actualizado.puntaje_total == 40


def test_acumular_puntaje_de_usuario_inexistente_retorna_none(sesion_db: Session) -> None:
    """Si el usuario no existe no se produce ningún error y se informa con None."""
    assert ranking_service.acumular_puntaje(sesion_db, usuario_id=ID_USUARIO_INEXISTENTE, puntos=10) is None
    assert ranking_service.acumular_puntaje(sesion_db, usuario_id=ID_USUARIO_INEXISTENTE, puntos=0) is None


def test_dos_partidas_individuales_acumulan_la_suma_de_ambas(sesion_db: Session) -> None:
    """Terminar dos partidas seguidas deja en el ranking la suma de sus puntajes."""
    _crear_categoria_con_preguntas(sesion_db)
    usuario = _crear_usuario(sesion_db, "doble@futbolquiz.com")

    primera = _jugar_partida_individual_completa(sesion_db, usuario)
    segunda = _jugar_partida_individual_completa(sesion_db, usuario)

    assert primera.puntaje_final > 0
    assert segunda.puntaje_final > 0
    assert usuario.puntaje_total == primera.puntaje_final + segunda.puntaje_final


def test_duelo_local_suma_puntaje_solo_al_anfitrion(sesion_db: Session) -> None:
    """En un duelo local el invitado no tiene cuenta: solo el anfitrión suma al ranking."""
    _crear_categoria_con_preguntas(sesion_db)
    anfitrion = _crear_usuario(sesion_db, "anfitrion@futbolquiz.com")
    otro_usuario = _crear_usuario(sesion_db, "otro@futbolquiz.com", puntaje_inicial=77)
    duelo = duelo_service.iniciar_duelo_local(
        sesion_db, usuario_actual=anfitrion, nombre_invitado="Invitado"
    )

    for pregunta_partida in duelo.preguntas_de_jugador(1):
        duelo_service.responder_pregunta_duelo(
            sesion_db,
            pregunta_partida_id=pregunta_partida.id,
            opcion_seleccionada="A",
            tiempo_respuesta_segundos=1,
            usuario_actual=anfitrion,
        )
    for pregunta_partida in duelo.preguntas_de_jugador(2):
        pregunta_partida.registrar_respuesta(
            opcion="A", tiempo_segundos=10, es_correcta=True, puntaje=50
        )
        sesion_db.add(pregunta_partida)
    sesion_db.commit()

    duelo = duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)

    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.puntaje_jugador1 > 0
    assert anfitrion.puntaje_total == duelo.puntaje_jugador1
    assert otro_usuario.puntaje_total == 77


def test_puntos_del_campeon_de_torneo_estan_definidos_en_el_ranking() -> None:
    """El premio al campeón es una constante única del ranking (RF-11)."""
    assert ranking_service.PUNTOS_CAMPEON_TORNEO == 1500