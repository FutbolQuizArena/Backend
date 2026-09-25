"""Pruebas unitarias y de integración para la determinación de ganador y avance de ronda (Sub-tarea 3.2.2)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.cruce import Cruce
from app.models.enumeraciones import (
    EstadoCategoria,
    EstadoCruce,
    EstadoPartida,
    EstadoTorneo,
    RolUsuario,
)
from app.models.partida_duelo import PartidaDuelo
from app.models.participante_torneo import ParticipanteTorneo
from app.models.pregunta import Pregunta
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import duelo_repository, torneo_repository
from app.schemas.torneo_schema import (
    CruceResolverRequest,
    TorneoCreate,
    TorneoUnirseRequest,
)
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, duelo_service, torneo_service, usuario_service


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def categoria_con_preguntas(sesion_db: Session) -> Categoria:
    """Crea una categoría activa con 10 preguntas de prueba para disputar duelos."""
    categoria = Categoria(nombre="Mundiales Torneo", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(categoria)
    sesion_db.flush()

    for i in range(1, 11):
        pregunta = Pregunta(
            enunciado=f"Pregunta torneo número {i}",
            opcion_a="Opción A (Correcta)",
            opcion_b="Opción B",
            opcion_c="Opción C",
            opcion_d="Opción D",
            respuesta_correcta="A",
            categoria_id=categoria.id,
        )
        sesion_db.add(pregunta)
    sesion_db.flush()
    return categoria


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario creador del torneo."""
    datos = UsuarioCreate(
        nombre="Organizador Maestro",
        email="organizador.avance@futbolquiz.com",
        password="passwordOrganizador1",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


def crear_usuarios_prueba(sesion_db: Session, cantidad: int, prefijo: str = "jug") -> list[Usuario]:
    """Crea y persiste una lista de usuarios jugadores."""
    usuarios = []
    for i in range(1, cantidad + 1):
        datos = UsuarioCreate(
            nombre=f"{prefijo}_{i}",
            email=f"{prefijo}_{i}_{cantidad}@futbolquiz.com",
            password=f"passwordSegura{i}",
            rol=RolUsuario.JUGADOR,
        )
        usuarios.append(usuario_service.registrar_usuario(sesion_db, datos))
    return usuarios


def auth_header(usuario: Usuario) -> dict[str, str]:
    """Genera el encabezado Authorization con Bearer JWT para un usuario."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas Unitarias de Modelos de Dominio
# ==============================================================================


def test_modelo_usuario_sumar_puntaje(sesion_db: Session, usuario_creador: Usuario) -> None:
    """Verifica que el método sumar_puntaje incremente el puntaje_total del usuario."""
    puntaje_inicial = usuario_creador.puntaje_total
    usuario_creador.sumar_puntaje(1500)
    assert usuario_creador.puntaje_total == puntaje_inicial + 1500


def test_modelo_cruce_determinar_ganador_exitoso(sesion_db: Session) -> None:
    """Verifica que determinar_ganador asigne el ID y cambie el estado a JUGADO."""
    p1 = ParticipanteTorneo(torneo_id=1, usuario_id=10)
    p2 = ParticipanteTorneo(torneo_id=1, usuario_id=20)
    sesion_db.add_all([p1, p2])
    sesion_db.flush()

    cruce = Cruce(
        torneo_id=1,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p2.id,
        estado=EstadoCruce.PENDIENTE,
    )
    sesion_db.add(cruce)
    sesion_db.flush()

    cruce.determinar_ganador(p1)
    assert cruce.ganador_id == p1.id
    assert cruce.estado == EstadoCruce.JUGADO


def test_modelo_cruce_determinar_ganador_rechaza_participante_ajeno(sesion_db: Session) -> None:
    """Verifica que determinar_ganador lance ValueError si el participante no pertenece al cruce."""
    p1 = ParticipanteTorneo(torneo_id=1, usuario_id=10)
    p2 = ParticipanteTorneo(torneo_id=1, usuario_id=20)
    p_ajeno = ParticipanteTorneo(torneo_id=1, usuario_id=30)
    sesion_db.add_all([p1, p2, p_ajeno])
    sesion_db.flush()

    cruce = Cruce(
        torneo_id=1,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p2.id,
        estado=EstadoCruce.PENDIENTE,
    )
    sesion_db.add(cruce)
    sesion_db.flush()

    with pytest.raises(ValueError, match="no pertenece al cruce"):
        cruce.determinar_ganador(p_ajeno)


def test_modelo_torneo_armar_cruces_siguiente_ronda(sesion_db: Session) -> None:
    """Verifica que armar_cruces_siguiente_ronda empareje consecutivamente a los ganadores."""
    torneo = Torneo(
        nombre="Torneo Test Rondas",
        cantidad_participantes=4,
        codigo_acceso="TESTRO",
        estado=EstadoTorneo.EN_CURSO,
        creador_id=1,
    )
    sesion_db.add(torneo)
    sesion_db.flush()

    p1 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=1)
    p2 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=2)
    p3 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=3)
    p4 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=4)
    sesion_db.add_all([p1, p2, p3, p4])
    sesion_db.flush()

    # 4 ganadores pasan a la siguiente ronda (ej: 4 cuartofinalistas ganaron -> 2 semis)
    nuevos_cruces = torneo.armar_cruces_siguiente_ronda([p1, p2, p3, p4], ronda_siguiente=2)
    assert len(nuevos_cruces) == 2

    cruce1, cruce2 = nuevos_cruces
    assert cruce1.ronda == 2
    assert cruce1.jugador_a_id == p1.id
    assert cruce1.jugador_b_id == p2.id
    assert cruce1.estado == EstadoCruce.PENDIENTE
    assert cruce1.ganador_id is None

    assert cruce2.ronda == 2
    assert cruce2.jugador_a_id == p3.id
    assert cruce2.jugador_b_id == p4.id
    assert cruce2.estado == EstadoCruce.PENDIENTE


def test_modelo_torneo_finalizar_torneo() -> None:
    """Verifica que finalizar_torneo mute el estado a FINALIZADO."""
    torneo = Torneo(
        nombre="Torneo Finalizando",
        cantidad_participantes=4,
        codigo_acceso="FIN123",
        estado=EstadoTorneo.EN_CURSO,
        creador_id=1,
    )
    torneo.finalizar_torneo()
    assert torneo.estado == EstadoTorneo.FINALIZADO


# ==============================================================================
# Pruebas de Integración: Flujo Completo Torneo 4 Participantes (Semis -> Final)
# ==============================================================================


def test_flujo_completo_torneo_4_jugadores_avance_y_coronacion(
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Flujo end-to-end de un torneo de 4 jugadores:

    1. Creador crea torneo cupo 4.
    2. Se unen 3 jugadores -> Se generan 2 cruces en Ronda 1 (Semifinales).
    3. Se resuelve Cruce 1 -> Ronda 1 sigue incompleta (Cruce 2 pendiente).
    4. Se resuelve Cruce 2 -> Ronda 1 completa -> Se genera automáticamente Ronda 2 (Final).
    5. Se resuelve la Final -> Torneo pasa a FINALIZADO, se consagra al campeón y se premian los +1.500 puntos.
    """
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Clausura 4", cantidad_participantes=4),
        usuario_creador,
    )

    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="clausura4")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    # El torneo pasó a EN_CURSO y tiene 2 cruces en Ronda 1
    assert torneo.estado == EstadoTorneo.EN_CURSO
    cruces_r1 = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)
    assert len(cruces_r1) == 2
    cruce_semis_1, cruce_semis_2 = cruces_r1

    # --- PASO 3: Resolver Cruce Semis 1 ---
    res_1 = torneo_service.resolver_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce_semis_1.id,
        usuario_actual=usuario_creador,
        datos=CruceResolverRequest(ganador_participante_id=cruce_semis_1.jugador_a_id),
    )
    assert res_1.ronda_completada is False
    assert res_1.siguiente_ronda_generada is False
    assert res_1.nueva_ronda is None
    assert res_1.torneo_finalizado is False
    assert res_1.ganador_id == cruce_semis_1.jugador_a_id
    assert res_1.estado_cruce == EstadoCruce.JUGADO

    # --- PASO 4: Resolver Cruce Semis 2 (completa Ronda 1) ---
    res_2 = torneo_service.resolver_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce_semis_2.id,
        usuario_actual=usuario_creador,
        datos=CruceResolverRequest(ganador_participante_id=cruce_semis_2.jugador_b_id),
    )
    assert res_2.ronda_completada is True
    assert res_2.siguiente_ronda_generada is True
    assert res_2.nueva_ronda == 2
    assert res_2.torneo_finalizado is False

    # Verificar que en la base de datos se generó la Final (Ronda 2)
    cruces_r2 = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=2)
    assert len(cruces_r2) == 1
    cruce_final = cruces_r2[0]
    assert cruce_final.ronda == 2
    assert cruce_final.jugador_a_id == cruce_semis_1.jugador_a_id
    assert cruce_final.jugador_b_id == cruce_semis_2.jugador_b_id
    assert cruce_final.estado == EstadoCruce.PENDIENTE

    # --- PASO 5: Disputar y resolver la Final ---
    campeon_participante = cruce_final.jugador_a
    usuario_campeon = campeon_participante.usuario
    puntaje_previo = usuario_campeon.puntaje_total

    res_final = torneo_service.resolver_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce_final.id,
        usuario_actual=usuario_creador,
        datos=CruceResolverRequest(ganador_participante_id=cruce_final.jugador_a_id),
    )

    assert res_final.ronda_completada is True
    assert res_final.siguiente_ronda_generada is False
    assert res_final.torneo_finalizado is True
    assert res_final.puntos_otorgados_campeon == 1500
    assert res_final.campeon is not None
    assert res_final.campeon.usuario_id == usuario_campeon.id

    # Torneo en base de datos quedó en FINALIZADO
    sesion_db.refresh(torneo)
    assert torneo.estado == EstadoTorneo.FINALIZADO

    # El usuario campeón sumó exactamente 1500 puntos
    sesion_db.refresh(usuario_campeon)
    assert usuario_campeon.puntaje_total == puntaje_previo + 1500


# ==============================================================================
# Pruebas de Integración: Torneo de 8 Participantes (Cuartos -> Semis -> Final)
# ==============================================================================


def test_flujo_torneo_8_jugadores_tres_rondas_completo(
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Torneo de 8 jugadores: Cuartos (4 cruces) -> Semis (2 cruces) -> Final (1 cruce)."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Copa de Campeones 8", cantidad_participantes=8),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 7, prefijo="copa8")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    assert torneo.estado == EstadoTorneo.EN_CURSO

    # Ronda 1: Cuartos de final (4 cruces)
    cruces_r1 = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)
    assert len(cruces_r1) == 4

    for i, cruce in enumerate(cruces_r1):
        res = torneo_service.resolver_cruce(
            db=sesion_db,
            torneo_id=torneo.id,
            cruce_id=cruce.id,
            usuario_actual=usuario_creador,
            datos=CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id),
        )
        if i < 3:
            assert res.siguiente_ronda_generada is False
        else:
            assert res.siguiente_ronda_generada is True
            assert res.nueva_ronda == 2

    # Ronda 2: Semifinales (2 cruces)
    cruces_r2 = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=2)
    assert len(cruces_r2) == 2

    for i, cruce in enumerate(cruces_r2):
        res = torneo_service.resolver_cruce(
            db=sesion_db,
            torneo_id=torneo.id,
            cruce_id=cruce.id,
            usuario_actual=usuario_creador,
            datos=CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id),
        )
        if i < 1:
            assert res.siguiente_ronda_generada is False
        else:
            assert res.siguiente_ronda_generada is True
            assert res.nueva_ronda == 3

    # Ronda 3: Final (1 cruce)
    cruces_r3 = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=3)
    assert len(cruces_r3) == 1
    cruce_final = cruces_r3[0]

    res_final = torneo_service.resolver_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce_final.id,
        usuario_actual=usuario_creador,
        datos=CruceResolverRequest(ganador_participante_id=cruce_final.jugador_a_id),
    )
    assert res_final.torneo_finalizado is True
    assert res_final.puntos_otorgados_campeon == 1500
    sesion_db.refresh(torneo)
    assert torneo.estado == EstadoTorneo.FINALIZADO


# ==============================================================================
# Pruebas de Duelos Vinculados al Cruce
# ==============================================================================


def test_iniciar_y_recuperar_duelo_cruce(
    sesion_db: Session,
    usuario_creador: Usuario,
    categoria_con_preguntas: Categoria,
) -> None:
    """Verifica que iniciar_duelo_cruce genere el duelo online y que llamadas subsiguientes lo recuperen."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Duelo Link", cantidad_participantes=4),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="dueloLink")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    cruce = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)[0]
    usuario_a = cruce.jugador_a.usuario
    usuario_b = cruce.jugador_b.usuario

    # Jugador A inicia el duelo
    resp_a = torneo_service.iniciar_duelo_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce.id,
        usuario_actual=usuario_a,
    )
    assert resp_a.duelo_id is not None
    assert resp_a.cruce_id == cruce.id

    # Jugador B entra al cruce y recupera el mismo duelo
    resp_b = torneo_service.iniciar_duelo_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce.id,
        usuario_actual=usuario_b,
    )
    assert resp_b.duelo_id == resp_a.duelo_id


def test_resolver_cruce_con_duelo_finalizado_real(
    sesion_db: Session,
    usuario_creador: Usuario,
    categoria_con_preguntas: Categoria,
) -> None:
    """Verifica que al resolver un cruce mediante duelo_id se declare ganador al jugador victorioso."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Real Duel", cantidad_participantes=4),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="realDuel")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    cruce = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)[0]
    usuario_a = cruce.jugador_a.usuario
    usuario_b = cruce.jugador_b.usuario

    # Iniciar duelo
    resp_duelo = torneo_service.iniciar_duelo_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce.id,
        usuario_actual=usuario_a,
    )

    duelo = duelo_repository.obtener_duelo_por_id(sesion_db, resp_duelo.duelo_id)
    assert duelo is not None

    # Simular respuestas: jugador 1 responde correctamente y suma puntos; jugador 2 no suma
    preguntas_j1 = duelo.preguntas_de_jugador(1)
    preguntas_j2 = duelo.preguntas_de_jugador(2)

    for p in preguntas_j1:
        p.registrar_respuesta(opcion="A", tiempo_segundos=5, es_correcta=True, puntaje=100)
    for p in preguntas_j2:
        p.registrar_respuesta(opcion="B", tiempo_segundos=10, es_correcta=False, puntaje=0)

    # Finalizar duelo
    duelo_service.finalizar_duelo_si_corresponde(sesion_db, duelo.id)
    assert duelo.estado == EstadoPartida.FINALIZADA
    assert duelo.numero_ganador == 1

    # Resolver cruce mediante duelo_id
    resolucion = torneo_service.resolver_cruce(
        db=sesion_db,
        torneo_id=torneo.id,
        cruce_id=cruce.id,
        usuario_actual=usuario_creador,
        datos=CruceResolverRequest(duelo_id=duelo.id),
    )

    # El ganador del cruce debe ser el participante correspondiente al jugador 1 (usuario_a)
    assert resolucion.ganador_id == cruce.jugador_a_id
    assert resolucion.estado_cruce == EstadoCruce.JUGADO


# ==============================================================================
# Pruebas de Validaciones y Casos de Borde (Excepciones y Seguridad)
# ==============================================================================


def test_validaciones_resolver_cruce(
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica el rechazo ante parámetros o estados inconsistentes al resolver cruces."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo Validaciones", cantidad_participantes=4),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="valCruces")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    cruce = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)[0]

    # 1. Torneo inexistente -> 404
    with pytest.raises(Exception) as exc:
        torneo_service.resolver_cruce(
            sesion_db, 999999, cruce.id, usuario_creador, CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id)
        )
    assert "No se encontró ningún torneo" in str(exc.value)

    # 2. Cruce inexistente -> 404
    with pytest.raises(Exception) as exc:
        torneo_service.resolver_cruce(
            sesion_db, torneo.id, 999999, usuario_creador, CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id)
        )
    assert "No se encontró ningún cruce" in str(exc.value)

    # 3. Participante ajeno como ganador -> 400
    with pytest.raises(Exception) as exc:
        torneo_service.resolver_cruce(
            sesion_db, torneo.id, cruce.id, usuario_creador, CruceResolverRequest(ganador_participante_id=999999)
        )
    assert "no pertenece a este cruce" in str(exc.value)

    # 4. Usuario ajeno intentando resolver -> 403
    usuario_externo = crear_usuarios_prueba(sesion_db, 1, prefijo="externo")[0]
    with pytest.raises(Exception) as exc:
        torneo_service.resolver_cruce(
            sesion_db, torneo.id, cruce.id, usuario_externo, CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id)
        )
    assert "No tienes permisos" in str(exc.value)

    # 5. Resolver exitosamente el cruce
    torneo_service.resolver_cruce(
        sesion_db, torneo.id, cruce.id, usuario_creador, CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id)
    )

    # 6. Intentar resolver un cruce ya JUGADO -> 400
    with pytest.raises(Exception) as exc:
        torneo_service.resolver_cruce(
            sesion_db, torneo.id, cruce.id, usuario_creador, CruceResolverRequest(ganador_participante_id=cruce.jugador_a_id)
        )
    assert "ya ha sido resuelto" in str(exc.value)


# ==============================================================================
# Pruebas HTTP End-to-End con TestClient
# ==============================================================================


def test_http_iniciar_duelo_cruce_endpoint(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
    categoria_con_preguntas: Categoria,
) -> None:
    """Verifica el endpoint POST /api/torneos/{id}/cruces/{cruce_id}/iniciar-duelo vía API REST."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo API Duelo", cantidad_participantes=4),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="apiDuelo")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    cruce = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)[0]
    usuario_a = cruce.jugador_a.usuario

    # Petición sin token -> 401
    resp_sin_token = cliente.post(f"/api/torneos/{torneo.id}/cruces/{cruce.id}/iniciar-duelo")
    assert resp_sin_token.status_code == 401

    # Petición con usuario ajeno -> 403
    usuario_ajeno = crear_usuarios_prueba(sesion_db, 1, prefijo="ajenoDuelo")[0]
    resp_ajeno = cliente.post(
        f"/api/torneos/{torneo.id}/cruces/{cruce.id}/iniciar-duelo",
        headers=auth_header(usuario_ajeno),
    )
    assert resp_ajeno.status_code == 403

    # Petición válida con jugador A -> 200 OK
    resp_ok = cliente.post(
        f"/api/torneos/{torneo.id}/cruces/{cruce.id}/iniciar-duelo",
        headers=auth_header(usuario_a),
    )
    assert resp_ok.status_code == 200
    datos = resp_ok.json()
    assert datos["cruce_id"] == cruce.id
    assert "duelo_id" in datos
    assert datos["ronda"] == 1


def test_http_resolver_cruce_endpoint(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica el endpoint POST /api/torneos/{id}/cruces/{cruce_id}/resolver vía API REST."""
    torneo = torneo_service.crear_torneo(
        sesion_db,
        TorneoCreate(nombre="Torneo API Resolver", cantidad_participantes=4),
        usuario_creador,
    )
    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="apiResolver")
    for j in jugadores:
        torneo_service.unirse_a_torneo(
            sesion_db,
            TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            j,
        )

    cruce = torneo_repository.obtener_cruces_por_ronda(sesion_db, torneo.id, ronda=1)[0]

    # Sin token -> 401
    resp_sin_token = cliente.post(
        f"/api/torneos/{torneo.id}/cruces/{cruce.id}/resolver",
        json={"ganador_participante_id": cruce.jugador_a_id},
    )
    assert resp_sin_token.status_code == 401

    # Creador resuelve el cruce -> 200 OK
    resp_ok = cliente.post(
        f"/api/torneos/{torneo.id}/cruces/{cruce.id}/resolver",
        headers=auth_header(usuario_creador),
        json={"ganador_participante_id": cruce.jugador_a_id},
    )
    assert resp_ok.status_code == 200
    datos = resp_ok.json()
    assert datos["cruce_id"] == cruce.id
    assert datos["ganador_id"] == cruce.jugador_a_id
    assert datos["ronda_completada"] is False
