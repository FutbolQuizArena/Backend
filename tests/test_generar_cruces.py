"""Pruebas unitarias y de integración para la generación automática de cruces (Sub-tarea 3.2.1)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cruce import Cruce
from app.models.enumeraciones import EstadoCruce, EstadoTorneo, RolUsuario
from app.models.participante_torneo import ParticipanteTorneo
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories import torneo_repository
from app.schemas.torneo_schema import TorneoCreate, TorneoUnirseRequest
from app.schemas.usuario_schema import UsuarioCreate
from app.services import autenticacion_service, torneo_service, usuario_service


# ==============================================================================
# Fixtures auxiliares
# ==============================================================================


@pytest.fixture
def usuario_creador(sesion_db: Session) -> Usuario:
    """Crea y persiste un usuario creador del torneo."""
    datos = UsuarioCreate(
        nombre="Organizador Principal",
        email="organizador.cruces@futbolquiz.com",
        password="passwordOrganizador1",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


def crear_usuarios_prueba(sesion_db: Session, cantidad: int, prefijo: str = "jugador") -> list[Usuario]:
    """Crea y persiste una lista de usuarios para completar los cupos de prueba."""
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
# Pruebas Unitarias del Modelo (Torneo.generar_cruces)
# ==============================================================================


@pytest.mark.parametrize("cantidad_participantes", [4, 8, 16])
def test_modelo_generar_cruces_tamanos_validos(cantidad_participantes: int) -> None:
    """Verifica que Torneo.generar_cruces arme exactamente cantidad/2 pares completos para 4, 8 y 16."""
    torneo = Torneo(
        nombre=f"Torneo {cantidad_participantes}",
        cantidad_participantes=cantidad_participantes,
        codigo_acceso="TEST01",
    )

    # Simular participantes inscriptos
    participantes_mock = [
        ParticipanteTorneo(id=i, usuario_id=i, torneo_id=1)
        for i in range(1, cantidad_participantes + 1)
    ]
    torneo.participantes = participantes_mock

    pares = torneo.generar_cruces()

    # Debe generar cantidad / 2 pares
    assert len(pares) == cantidad_participantes // 2

    # Verificar que cada participante aparece exactamente una vez
    participantes_en_pares = []
    for p_a, p_b in pares:
        assert p_a != p_b
        participantes_en_pares.append(p_a.id)
        participantes_en_pares.append(p_b.id)

    assert len(participantes_en_pares) == cantidad_participantes
    assert len(set(participantes_en_pares)) == cantidad_participantes
    assert set(participantes_en_pares) == {p.id for p in participantes_mock}


def test_modelo_generar_cruces_aleatoriedad() -> None:
    """Verifica que Torneo.generar_cruces utilice shuffle y varíe emparejamientos en múltiples ejecuciones."""
    torneo = Torneo(nombre="Torneo Aleatorio", cantidad_participantes=8, codigo_acceso="TEST88")
    torneo.participantes = [
        ParticipanteTorneo(id=i, usuario_id=i, torneo_id=1)
        for i in range(1, 9)
    ]

    ordenes_obtenidos = set()
    for _ in range(25):
        pares = torneo.generar_cruces()
        # Tupla con los IDs emparejados en orden
        orden = tuple((p_a.id, p_b.id) for p_a, p_b in pares)
        ordenes_obtenidos.add(orden)

    # Con 8 participantes, 25 ejecuciones deben producir al menos 2 configuraciones distintas
    assert len(ordenes_obtenidos) > 1


def test_modelo_generar_cruces_sin_participantes_retorna_vacio() -> None:
    """Verifica que Torneo.generar_cruces retorne lista vacía si no hay participantes."""
    torneo = Torneo(nombre="Torneo Vacio", cantidad_participantes=4, codigo_acceso="VACIO1")
    torneo.participantes = []
    assert torneo.generar_cruces() == []


# ==============================================================================
# Pruebas Unitarias del Repositorio (crear_cruces)
# ==============================================================================


def test_repositorio_crear_cruces_con_sesion(
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que torneo_repository.crear_cruces persista y asigne IDs a una lista de cruces."""
    torneo = Torneo(
        nombre="Torneo Repo",
        cantidad_participantes=4,
        codigo_acceso="REPO01",
        creador_id=usuario_creador.id,
    )
    sesion_db.add(torneo)
    sesion_db.commit()

    p1 = ParticipanteTorneo(torneo_id=torneo.id, usuario_id=usuario_creador.id)
    sesion_db.add(p1)
    sesion_db.commit()

    c1 = Cruce(
        torneo_id=torneo.id,
        ronda=1,
        jugador_a_id=p1.id,
        jugador_b_id=p1.id,
        estado=EstadoCruce.PENDIENTE,
        ganador_id=None,
    )

    cruces_creados = torneo_repository.crear_cruces(db=sesion_db, cruces=[c1])
    assert len(cruces_creados) == 1
    assert cruces_creados[0].id is not None
    assert cruces_creados[0].estado == EstadoCruce.PENDIENTE


# ==============================================================================
# Pruebas de Integración y Disparo Automático (Servicio y Flujo unirse_a_torneo)
# ==============================================================================


@pytest.mark.parametrize("cupo", [4, 8, 16])
def test_generacion_automatica_cruces_al_completar_cupo(
    sesion_db: Session,
    usuario_creador: Usuario,
    cupo: int,
) -> None:
    """Verifica que al completarse el cupo (4, 8 y 16) se generen automáticamente cantidad/2 cruces."""
    # 1. Crear torneo con el cupo dado (el creador es el primer inscripto)
    datos_crear = TorneoCreate(nombre=f"Torneo Cupo {cupo}", cantidad_participantes=cupo)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)
    assert torneo.estado == EstadoTorneo.ESPERANDO_JUGADORES

    # 2. Crear los jugadores restantes necesarios (cupo - 1)
    jugadores_restantes = crear_usuarios_prueba(sesion_db, cupo - 1, prefijo=f"c{cupo}")

    # 3. Unir los jugadores uno a uno hasta antes del último
    for jugador in jugadores_restantes[:-1]:
        torneo_service.unirse_a_torneo(
            db=sesion_db,
            datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
            usuario_actual=jugador,
        )
        # El torneo debe continuar en ESPERANDO_JUGADORES y sin cruces
        cruces_intermedios = sesion_db.query(Cruce).filter(Cruce.torneo_id == torneo.id).all()
        assert len(cruces_intermedios) == 0

    # 4. Unir al último jugador que completa el cupo
    ultimo_jugador = jugadores_restantes[-1]
    torneo_actualizado = torneo_service.unirse_a_torneo(
        db=sesion_db,
        datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
        usuario_actual=ultimo_jugador,
    )

    # 5. Verificar que el torneo pasa a EN_CURSO
    assert torneo_actualizado.estado == EstadoTorneo.EN_CURSO

    # 6. Consultar cruces generados en BD
    cruces = sesion_db.query(Cruce).filter(Cruce.torneo_id == torneo.id).all()

    # Debe haber exactamente cupo / 2 cruces
    esperado_cruces = cupo // 2
    assert len(cruces) == esperado_cruces

    # Obtener IDs de todos los participantes del torneo
    participantes_bd = (
        sesion_db.query(ParticipanteTorneo)
        .filter(ParticipanteTorneo.torneo_id == torneo.id)
        .all()
    )
    ids_participantes_esperados = {p.id for p in participantes_bd}
    assert len(ids_participantes_esperados) == cupo

    # 7. Validaciones exhaustivas de cada cruce generado
    participantes_en_cruces = []
    for cruce in cruces:
        assert cruce.torneo_id == torneo.id
        assert cruce.ronda == 1
        assert cruce.estado == EstadoCruce.PENDIENTE
        assert cruce.ganador_id is None
        assert cruce.jugador_a_id != cruce.jugador_b_id
        assert cruce.jugador_a_id in ids_participantes_esperados
        assert cruce.jugador_b_id in ids_participantes_esperados

        participantes_en_cruces.append(cruce.jugador_a_id)
        participantes_en_cruces.append(cruce.jugador_b_id)

    # Cada participante debe aparecer en exactamente un cruce (ni repetido ni ausente)
    assert len(participantes_en_cruces) == cupo
    assert set(participantes_en_cruces) == ids_participantes_esperados
    assert len(set(participantes_en_cruces)) == cupo


def test_torneo_incompleto_no_genera_cruces(
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica que un torneo que no completa su cupo no genere ningún cruce."""
    datos_crear = TorneoCreate(nombre="Torneo 4 Incompleto", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    # Inscribir solo un segundo jugador (2 de 4)
    jugadores = crear_usuarios_prueba(sesion_db, 1, prefijo="inc")
    torneo_service.unirse_a_torneo(
        db=sesion_db,
        datos=TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso),
        usuario_actual=jugadores[0],
    )

    cruces = sesion_db.query(Cruce).filter(Cruce.torneo_id == torneo.id).all()
    assert len(cruces) == 0


def test_generacion_cruces_end_to_end_via_api(
    cliente: TestClient,
    sesion_db: Session,
    usuario_creador: Usuario,
) -> None:
    """Verifica de extremo a extremo que el endpoint HTTP POST /api/torneos/unirse dispare la generación de cruces."""
    datos_crear = TorneoCreate(nombre="Torneo API Cruces", cantidad_participantes=4)
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)

    jugadores = crear_usuarios_prueba(sesion_db, 3, prefijo="api_cruce")
    payload = {"codigo_acceso": torneo.codigo_acceso}

    # Jugador 1 (2/4)
    r1 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugadores[0]))
    assert r1.status_code == 200

    # Jugador 2 (3/4)
    r2 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugadores[1]))
    assert r2.status_code == 200

    # Jugador 3 (4/4 -> completa el torneo y transiciona a EN_CURSO)
    r3 = cliente.post("/api/torneos/unirse", json=payload, headers=auth_header(jugadores[2]))
    assert r3.status_code == 200
    assert r3.json()["estado"] == EstadoTorneo.EN_CURSO.value

    # Verificar en base de datos la persistencia de los 2 cruces
    cruces = sesion_db.query(Cruce).filter(Cruce.torneo_id == torneo.id).all()
    assert len(cruces) == 2
    for cruce in cruces:
        assert cruce.ronda == 1
        assert cruce.estado == EstadoCruce.PENDIENTE
        assert cruce.ganador_id is None
        assert cruce.torneo_id == torneo.id
