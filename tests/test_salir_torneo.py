"""Pruebas de integración y unitarias para el endpoint de salir de torneo (DELETE /api/torneos/{id}/salir)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionRecursoNoEncontrado, TorneoNoDisponibleError
from app.models.enumeraciones import EstadoTorneo, RolUsuario
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
    """Crea y persiste el usuario creador del torneo."""
    datos = UsuarioCreate(
        nombre="Usuario Creador",
        email="creador@futbolquiz.com",
        password="claveSegura123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_participante(sesion_db: Session) -> Usuario:
    """Crea y persiste un segundo usuario participante."""
    datos = UsuarioCreate(
        nombre="Usuario Participante",
        email="participante@futbolquiz.com",
        password="claveSegura123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def usuario_externo(sesion_db: Session) -> Usuario:
    """Crea y persiste un tercer usuario no inscripto en el torneo."""
    datos = UsuarioCreate(
        nombre="Usuario Externo",
        email="externo@futbolquiz.com",
        password="claveSegura123",
        rol=RolUsuario.JUGADOR,
    )
    return usuario_service.registrar_usuario(sesion_db, datos)


@pytest.fixture
def torneo_con_dos_jugadores(
    sesion_db: Session,
    usuario_creador: Usuario,
    usuario_participante: Usuario,
) -> Torneo:
    """Crea un torneo de 4 jugadores con el creador y un participante unidos."""
    datos_crear = TorneoCreate(
        nombre="Torneo Relampago",
        cantidad_participantes=4,
    )
    torneo = torneo_service.crear_torneo(sesion_db, datos_crear, usuario_creador)
    datos_unirse = TorneoUnirseRequest(codigo_acceso=torneo.codigo_acceso)
    torneo_service.unirse_a_torneo(sesion_db, datos_unirse, usuario_participante)
    return torneo


def auth_header(usuario: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para un usuario dado."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas Unitarias del Modelo de Dominio (Torneo.salir)
# ==============================================================================


def test_modelo_salir_participante_regular(usuario_creador: Usuario, usuario_participante: Usuario):
    """Verifica que Torneo.salir() retorna 'participante_eliminado' para un no creador en ESPERANDO_JUGADORES."""
    torneo = Torneo(
        nombre="Torneo Test",
        cantidad_participantes=4,
        codigo_acceso="ABC123",
        estado=EstadoTorneo.ESPERANDO_JUGADORES,
        creador_id=usuario_creador.id,
    )
    resultado = torneo.salir(usuario_participante)
    assert resultado == "participante_eliminado"


def test_modelo_salir_creador(usuario_creador: Usuario):
    """Verifica que Torneo.salir() retorna 'torneo_cancelado' cuando quien sale es el creador."""
    torneo = Torneo(
        nombre="Torneo Test",
        cantidad_participantes=4,
        codigo_acceso="ABC123",
        estado=EstadoTorneo.ESPERANDO_JUGADORES,
        creador_id=usuario_creador.id,
    )
    resultado = torneo.salir(usuario_creador)
    assert resultado == "torneo_cancelado"


def test_modelo_salir_torneo_en_curso(usuario_creador: Usuario, usuario_participante: Usuario):
    """Verifica que Torneo.salir() retorna 'no_permitido' si el torneo está EN_CURSO."""
    torneo = Torneo(
        nombre="Torneo Test",
        cantidad_participantes=4,
        codigo_acceso="ABC123",
        estado=EstadoTorneo.EN_CURSO,
        creador_id=usuario_creador.id,
    )
    assert torneo.salir(usuario_participante) == "no_permitido"
    assert torneo.salir(usuario_creador) == "no_permitido"


def test_modelo_salir_torneo_finalizado(usuario_creador: Usuario, usuario_participante: Usuario):
    """Verifica que Torneo.salir() retorna 'no_permitido' si el torneo está FINALIZADO."""
    torneo = Torneo(
        nombre="Torneo Test",
        cantidad_participantes=4,
        codigo_acceso="ABC123",
        estado=EstadoTorneo.FINALIZADO,
        creador_id=usuario_creador.id,
    )
    assert torneo.salir(usuario_participante) == "no_permitido"
    assert torneo.salir(usuario_creador) == "no_permitido"


# ==============================================================================
# Pruebas Unitarias de Capa de Servicio (salir_de_torneo)
# ==============================================================================


def test_servicio_salir_torneo_inexistente(sesion_db: Session, usuario_creador: Usuario):
    """Lanza ExcepcionRecursoNoEncontrado si el torneo_id no existe."""
    with pytest.raises(ExcepcionRecursoNoEncontrado):
        torneo_service.salir_de_torneo(sesion_db, torneo_id=99999, usuario_actual=usuario_creador)


def test_servicio_salir_usuario_no_participante(
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_externo: Usuario,
):
    """Lanza TorneoNoDisponibleError si el usuario no es participante del torneo."""
    with pytest.raises(TorneoNoDisponibleError) as exc_info:
        torneo_service.salir_de_torneo(
            sesion_db,
            torneo_id=torneo_con_dos_jugadores.id,
            usuario_actual=usuario_externo,
        )
    assert "No eres participante" in exc_info.value.mensaje


def test_servicio_salir_torneo_en_curso(
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_participante: Usuario,
):
    """Lanza TorneoNoDisponibleError si el torneo ya está EN_CURSO."""
    torneo_repository.actualizar_estado(
        sesion_db,
        torneo=torneo_con_dos_jugadores,
        nuevo_estado=EstadoTorneo.EN_CURSO,
    )
    with pytest.raises(TorneoNoDisponibleError) as exc_info:
        torneo_service.salir_de_torneo(
            sesion_db,
            torneo_id=torneo_con_dos_jugadores.id,
            usuario_actual=usuario_participante,
        )
    assert "No es posible salir" in exc_info.value.mensaje


# ==============================================================================
# Pruebas de Integración HTTP (DELETE /api/torneos/{id}/salir)
# ==============================================================================


def test_participante_regular_sale_exitosamente(
    cliente: TestClient,
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_participante: Usuario,
    usuario_creador: Usuario,
):
    """Un participante regular sale exitosamente: recibe 200, se elimina su inscripción y el torneo sigue."""
    torneo_id = torneo_con_dos_jugadores.id
    headers = auth_header(usuario_participante)

    # Verificar que el participante esté antes
    assert torneo_repository.es_participante(sesion_db, torneo_id=torneo_id, usuario_id=usuario_participante.id)

    respuesta = cliente.delete(f"/api/torneos/{torneo_id}/salir", headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["mensaje"] == "Has salido del torneo exitosamente"

    # Verificar en BD que ya no es participante
    sesion_db.expire_all()
    assert not torneo_repository.es_participante(sesion_db, torneo_id=torneo_id, usuario_id=usuario_participante.id)

    # El torneo sigue existiendo y su creador sigue inscripto
    torneo_bd = torneo_repository.obtener_por_id(sesion_db, id=torneo_id)
    assert torneo_bd is not None
    assert torneo_bd.estado == EstadoTorneo.ESPERANDO_JUGADORES
    assert torneo_repository.es_participante(sesion_db, torneo_id=torneo_id, usuario_id=usuario_creador.id)


def test_creador_sale_cancela_torneo_completo(
    cliente: TestClient,
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_creador: Usuario,
    usuario_participante: Usuario,
):
    """El creador sale: recibe 200, el torneo se cancela/elimina por completo junto a los participantes."""
    torneo_id = torneo_con_dos_jugadores.id
    headers = auth_header(usuario_creador)

    respuesta = cliente.delete(f"/api/torneos/{torneo_id}/salir", headers=headers)

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["mensaje"] == "Torneo cancelado exitosamente al salir el creador"

    # Verificar en BD que el torneo ya no existe
    sesion_db.expire_all()
    assert torneo_repository.obtener_por_id(sesion_db, id=torneo_id) is None

    # Verificar que los participantes asociados se eliminaron en cascada
    participantes = (
        sesion_db.query(ParticipanteTorneo)
        .filter(ParticipanteTorneo.torneo_id == torneo_id)
        .all()
    )
    assert len(participantes) == 0


def test_salir_torneo_en_curso_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_participante: Usuario,
):
    """Intentar salir de un torneo EN_CURSO retorna 400 Bad Request."""
    torneo_repository.actualizar_estado(
        sesion_db,
        torneo=torneo_con_dos_jugadores,
        nuevo_estado=EstadoTorneo.EN_CURSO,
    )
    headers = auth_header(usuario_participante)

    respuesta = cliente.delete(f"/api/torneos/{torneo_con_dos_jugadores.id}/salir", headers=headers)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TORNEO_NO_DISPONIBLE"
    assert "No es posible salir" in cuerpo["message"]


def test_salir_torneo_finalizado_retorna_400(
    cliente: TestClient,
    sesion_db: Session,
    torneo_con_dos_jugadores: Torneo,
    usuario_participante: Usuario,
):
    """Intentar salir de un torneo FINALIZADO retorna 400 Bad Request."""
    torneo_repository.actualizar_estado(
        sesion_db,
        torneo=torneo_con_dos_jugadores,
        nuevo_estado=EstadoTorneo.FINALIZADO,
    )
    headers = auth_header(usuario_participante)

    respuesta = cliente.delete(f"/api/torneos/{torneo_con_dos_jugadores.id}/salir", headers=headers)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TORNEO_NO_DISPONIBLE"
    assert "No es posible salir" in cuerpo["message"]


def test_salir_torneo_usuario_no_participante_retorna_400(
    cliente: TestClient,
    torneo_con_dos_jugadores: Torneo,
    usuario_externo: Usuario,
):
    """Un usuario que no está en el torneo intenta salir: retorna 400 Bad Request."""
    headers = auth_header(usuario_externo)

    respuesta = cliente.delete(f"/api/torneos/{torneo_con_dos_jugadores.id}/salir", headers=headers)

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TORNEO_NO_DISPONIBLE"
    assert "No eres participante" in cuerpo["message"]


def test_salir_torneo_inexistente_retorna_404(
    cliente: TestClient,
    usuario_creador: Usuario,
):
    """Intentar salir de un torneo que no existe retorna 404 Not Found."""
    headers = auth_header(usuario_creador)

    respuesta = cliente.delete("/api/torneos/99999/salir", headers=headers)

    assert respuesta.status_code == 404
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "RECURSO_NO_ENCONTRADO"


def test_salir_torneo_sin_token_retorna_401(
    cliente: TestClient,
    torneo_con_dos_jugadores: Torneo,
):
    """Petición sin header Authorization retorna 401 Unauthorized."""
    respuesta = cliente.delete(f"/api/torneos/{torneo_con_dos_jugadores.id}/salir")
    assert respuesta.status_code == 401


def test_salir_torneo_token_invalido_retorna_401(
    cliente: TestClient,
    torneo_con_dos_jugadores: Torneo,
):
    """Petición con token JWT inválido retorna 401 con código TOKEN_INVALIDO."""
    headers = {"Authorization": "Bearer token_invalido_xyz"}
    respuesta = cliente.delete(f"/api/torneos/{torneo_con_dos_jugadores.id}/salir", headers=headers)
    assert respuesta.status_code == 401
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "TOKEN_INVALIDO"

