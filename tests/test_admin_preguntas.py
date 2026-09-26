"""Pruebas para la administración de preguntas (Tarea 5.1.1 - Módulo 5)."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionValidacion
from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoPregunta, RolUsuario
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.repositories import pregunta_repository, usuario_repository
from app.services import autenticacion_service, usuario_service


@pytest.fixture
def categoria_prueba(sesion_db: Session) -> Categoria:
    """Crea una categoría de prueba para asociar preguntas."""
    categoria = Categoria(nombre="Mundiales")
    sesion_db.add(categoria)
    sesion_db.commit()
    sesion_db.refresh(categoria)
    return categoria


@pytest.fixture
def categoria_alternativa(sesion_db: Session) -> Categoria:
    """Crea una segunda categoría de prueba."""
    categoria = Categoria(nombre="Clubes")
    sesion_db.add(categoria)
    sesion_db.commit()
    sesion_db.refresh(categoria)
    return categoria


@pytest.fixture
def usuario_admin(sesion_db: Session) -> Usuario:
    """Crea un usuario con rol ADMINISTRADOR."""
    admin = Usuario(
        nombre="Admin Quiz",
        email="admin@futbolquiz.com",
        password_hash=usuario_service.hashear_password("adminPassword123"),
        rol=RolUsuario.ADMINISTRADOR,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea un usuario regular con rol JUGADOR."""
    jugador = Usuario(
        nombre="Jugador Quiz",
        email="jugador@futbolquiz.com",
        password_hash=usuario_service.hashear_password("jugadorPassword123"),
        rol=RolUsuario.JUGADOR,
    )
    return usuario_repository.crear(sesion_db, jugador)


@pytest.fixture
def headers_admin(usuario_admin: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para el administrador."""
    token = autenticacion_service.generar_token_jwt(usuario_admin)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_jugador(usuario_jugador: Usuario) -> dict[str, str]:
    """Genera encabezado de autorización Bearer para un jugador regular."""
    token = autenticacion_service.generar_token_jwt(usuario_jugador)
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Pruebas de Autorización y Seguridad (5.1.4)
# ==============================================================================


def test_admin_preguntas_sin_token_retorna_401(cliente: TestClient) -> None:
    """Cualquier endpoint de administración sin token debe rechazar con 401."""
    resp = cliente.get("/api/admin/preguntas")
    assert resp.status_code == 401


def test_admin_preguntas_con_rol_jugador_retorna_403(
    cliente: TestClient, headers_jugador: dict[str, str]
) -> None:
    """Un usuario con rol JUGADOR debe ser rechazado con 403 Forbidden."""
    resp = cliente.get("/api/admin/preguntas", headers=headers_jugador)
    assert resp.status_code == 403


# ==============================================================================
# Pruebas de Creación (POST /api/admin/preguntas)
# ==============================================================================


def test_crear_pregunta_exitoso_como_admin(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
) -> None:
    """Un administrador puede crear una pregunta con datos completos."""
    payload = {
        "enunciado": "¿Qué selección ganó el Mundial de 1986?",
        "categoria_id": categoria_prueba.id,
        "opcion_a": "Brasil",
        "opcion_b": "Argentina",
        "opcion_c": "Uruguay",
        "opcion_d": "Alemania",
        "respuesta_correcta": "B",
        "dificultad": "Media",
        "estado": "ACTIVA",
    }
    resp = cliente.post("/api/admin/preguntas", json=payload, headers=headers_admin)
    assert resp.status_code == 201
    datos = resp.json()
    assert datos["id"] is not None
    assert datos["enunciado"] == payload["enunciado"]
    assert datos["categoria_id"] == categoria_prueba.id
    assert datos["categoria_nombre"] == "Mundiales"
    assert datos["respuesta_correcta"] == "B"
    assert datos["dificultad"] == "Media"
    assert datos["estado"] == "ACTIVA"
    assert datos["eliminada_en"] is None


def test_crear_pregunta_categoria_inexistente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Si la categoría indicada no existe, debe responder con 404."""
    payload = {
        "enunciado": "¿Pregunta huérfana?",
        "categoria_id": 99999,
        "opcion_a": "A",
        "opcion_b": "B",
        "opcion_c": "C",
        "opcion_d": "D",
        "respuesta_correcta": "A",
    }
    resp = cliente.post("/api/admin/preguntas", json=payload, headers=headers_admin)
    assert resp.status_code == 404


def test_crear_pregunta_opciones_incompletas_retorna_422(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
) -> None:
    """Si alguna opción está vacía o es solo espacios, debe responder con 422."""
    payload = {
        "enunciado": "¿Pregunta incompleta?",
        "categoria_id": categoria_prueba.id,
        "opcion_a": "Opción 1",
        "opcion_b": "Opción 2",
        "opcion_c": "   ",  # Espacios vacíos
        "opcion_d": "Opción 4",
        "respuesta_correcta": "A",
    }
    resp = cliente.post("/api/admin/preguntas", json=payload, headers=headers_admin)
    assert resp.status_code == 422


def test_crear_pregunta_respuesta_correcta_invalida_retorna_422(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
) -> None:
    """La respuesta correcta debe pertenecer al conjunto {A, B, C, D}."""
    payload = {
        "enunciado": "¿Pregunta con clave inválida?",
        "categoria_id": categoria_prueba.id,
        "opcion_a": "Opción 1",
        "opcion_b": "Opción 2",
        "opcion_c": "Opción 3",
        "opcion_d": "Opción 4",
        "respuesta_correcta": "Z",
    }
    resp = cliente.post("/api/admin/preguntas", json=payload, headers=headers_admin)
    assert resp.status_code == 422


# ==============================================================================
# Pruebas de Paginación y Filtros (GET /api/admin/preguntas)
# ==============================================================================


def test_listar_preguntas_paginacion_fija_6(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Crea 8 preguntas y verifica paginación fija de a 6 items."""
    for i in range(8):
        pregunta = Pregunta(
            enunciado=f"Pregunta paginada #{i + 1}",
            opcion_a="A",
            opcion_b="B",
            opcion_c="C",
            opcion_d="D",
            respuesta_correcta="A",
            categoria_id=categoria_prueba.id,
            dificultad="Media",
            estado=EstadoPregunta.ACTIVA,
        )
        sesion_db.add(pregunta)
    sesion_db.commit()

    # Página 1
    resp1 = cliente.get("/api/admin/preguntas?page=1", headers=headers_admin)
    assert resp1.status_code == 200
    datos1 = resp1.json()
    assert len(datos1["items"]) == 6
    assert datos1["total"] == 8
    assert datos1["page"] == 1
    assert datos1["total_paginas"] == 2

    # Página 2
    resp2 = cliente.get("/api/admin/preguntas?page=2", headers=headers_admin)
    assert resp2.status_code == 200
    datos2 = resp2.json()
    assert len(datos2["items"]) == 2
    assert datos2["total"] == 8
    assert datos2["page"] == 2
    assert datos2["total_paginas"] == 2


def test_listar_preguntas_tamano_pagina_personalizado(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Verifica que se pueda especificar un page_size personalizado."""
    for i in range(5):
        pregunta = Pregunta(
            enunciado=f"Pregunta personalizada {i + 1}",
            opcion_a="A",
            opcion_b="B",
            opcion_c="C",
            opcion_d="D",
            respuesta_correcta="A",
            categoria_id=categoria_prueba.id,
            dificultad="Media",
            estado=EstadoPregunta.ACTIVA,
        )
        sesion_db.add(pregunta)
    sesion_db.commit()

    resp = cliente.get("/api/admin/preguntas?page=1&page_size=2", headers=headers_admin)
    assert resp.status_code == 200
    datos = resp.json()
    assert len(datos["items"]) == 2
    assert datos["total"] == 5
    assert datos["page"] == 1
    assert datos["total_paginas"] == 3


def test_listar_preguntas_filtro_buscar_case_insensitive(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Búsqueda por texto libre sobre enunciado (case-insensitive y parcial)."""
    p1 = Pregunta(
        enunciado="¿Dónde se jugó la final del MUNDIAL 2014?",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
    )
    p2 = Pregunta(
        enunciado="¿Quién ganó la Copa Libertadores 2023?",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
    )
    sesion_db.add_all([p1, p2])
    sesion_db.commit()

    resp = cliente.get("/api/admin/preguntas?buscar=mundial", headers=headers_admin)
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["total"] == 1
    assert "MUNDIAL" in datos["items"][0]["enunciado"]


def test_listar_preguntas_filtros_combinados_categoria_y_estado(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    categoria_alternativa: Categoria,
    sesion_db: Session,
) -> None:
    """Filtro combinando categoria_id y estado (ACTIVA vs BORRADOR)."""
    p1 = Pregunta(
        enunciado="Pregunta activa en Mundiales",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
        estado=EstadoPregunta.ACTIVA,
    )
    p2 = Pregunta(
        enunciado="Pregunta borrador en Mundiales",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
        estado=EstadoPregunta.BORRADOR,
    )
    p3 = Pregunta(
        enunciado="Pregunta borrador en Clubes",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_alternativa.id,
        estado=EstadoPregunta.BORRADOR,
    )
    sesion_db.add_all([p1, p2, p3])
    sesion_db.commit()

    resp = cliente.get(
        f"/api/admin/preguntas?categoria_id={categoria_prueba.id}&estado=BORRADOR",
        headers=headers_admin,
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["total"] == 1
    assert datos["items"][0]["enunciado"] == "Pregunta borrador en Mundiales"


# ==============================================================================
# Pruebas de Detalle, Edición y Duplicación
# ==============================================================================


def test_obtener_pregunta_por_id_exitoso_e_inexistente(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Consulta puntual por ID: 200 si existe, 404 si no existe."""
    p = Pregunta(
        enunciado="Pregunta para consulta directa",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
    )
    sesion_db.add(p)
    sesion_db.commit()
    sesion_db.refresh(p)

    resp_ok = cliente.get(f"/api/admin/preguntas/{p.id}", headers=headers_admin)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["id"] == p.id

    resp_404 = cliente.get("/api/admin/preguntas/99999", headers=headers_admin)
    assert resp_404.status_code == 404


def test_actualizar_pregunta_parcial(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Actualización parcial de campos mediante PATCH."""
    p = Pregunta(
        enunciado="Enunciado original",
        opcion_a="Original A",
        opcion_b="Original B",
        opcion_c="Original C",
        opcion_d="Original D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
        dificultad="Fácil",
    )
    sesion_db.add(p)
    sesion_db.commit()
    sesion_db.refresh(p)

    payload_update = {
        "enunciado": "Enunciado modificado",
        "dificultad": "Difícil",
        "respuesta_correcta": "C",
    }
    resp = cliente.patch(f"/api/admin/preguntas/{p.id}", json=payload_update, headers=headers_admin)
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["enunciado"] == "Enunciado modificado"
    assert datos["dificultad"] == "Difícil"
    assert datos["respuesta_correcta"] == "C"
    assert datos["opcion_a"] == "Original A"  # Se conserva sin cambios


def test_cambiar_estado_toggle_activa_borrador(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """Alternar rápidamente el estado de la pregunta entre ACTIVA y BORRADOR."""
    p = Pregunta(
        enunciado="Pregunta para cambiar estado",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
        estado=EstadoPregunta.ACTIVA,
    )
    sesion_db.add(p)
    sesion_db.commit()
    sesion_db.refresh(p)

    # Pasar a BORRADOR
    resp = cliente.patch(
        f"/api/admin/preguntas/{p.id}/estado",
        json={"estado": "BORRADOR"},
        headers=headers_admin,
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "BORRADOR"

    # Pasar de nuevo a ACTIVA
    resp2 = cliente.patch(
        f"/api/admin/preguntas/{p.id}/estado",
        json={"estado": "ACTIVA"},
        headers=headers_admin,
    )
    assert resp2.status_code == 200
    assert resp2.json()["estado"] == "ACTIVA"


def test_duplicar_pregunta_queda_en_borrador(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """
    Duplicar clona la pregunta con ID distinto y estado BORRADOR
    para revisión previa del administrador.
    """
    p = Pregunta(
        enunciado="Pregunta matriz para clonar",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="B",
        categoria_id=categoria_prueba.id,
        dificultad="Media",
        estado=EstadoPregunta.ACTIVA,
    )
    sesion_db.add(p)
    sesion_db.commit()
    sesion_db.refresh(p)

    resp = cliente.post(f"/api/admin/preguntas/{p.id}/duplicar", headers=headers_admin)
    assert resp.status_code == 201
    copia = resp.json()
    assert copia["id"] != p.id
    assert copia["enunciado"] == p.enunciado
    assert copia["opcion_b"] == p.opcion_b
    assert copia["estado"] == "BORRADOR"  # Decisión documentada: BORRADOR
    assert copia["eliminada_en"] is None


# ==============================================================================
# Pruebas de Soft-Delete (Baja Lógica)
# ==============================================================================


def test_eliminar_pregunta_soft_delete(
    cliente: TestClient,
    headers_admin: dict[str, str],
    categoria_prueba: Categoria,
    sesion_db: Session,
) -> None:
    """
    Eliminar setea eliminada_en, no borra la fila física,
    y la pregunta deja de figurar en el listado ni en GET puntual.
    """
    p = Pregunta(
        enunciado="Pregunta a ser eliminada",
        opcion_a="A",
        opcion_b="B",
        opcion_c="C",
        opcion_d="D",
        respuesta_correcta="A",
        categoria_id=categoria_prueba.id,
    )
    sesion_db.add(p)
    sesion_db.commit()
    sesion_db.refresh(p)

    # Eliminar
    resp_del = cliente.delete(f"/api/admin/preguntas/{p.id}", headers=headers_admin)
    assert resp_del.status_code == 200

    # Verificar que en la base de datos la fila sigue existiendo con eliminada_en seteado
    sesion_db.refresh(p)
    assert p.eliminada_en is not None

    # Consulta directa por ID devuelve 404
    resp_get = cliente.get(f"/api/admin/preguntas/{p.id}", headers=headers_admin)
    assert resp_get.status_code == 404

    # No aparece en el listado paginado
    resp_list = cliente.get("/api/admin/preguntas", headers=headers_admin)
    ids_en_listado = [item["id"] for item in resp_list.json()["items"]]
    assert p.id not in ids_en_listado


# ==============================================================================
# Prueba de Regresión para Módulo 2 (obtener_preguntas_aleatorias_sin_repeticion)
# ==============================================================================


def test_modulo2_regresion_preguntas_aleatorias_ignora_borradores_y_eliminadas(
    sesion_db: Session,
    categoria_prueba: Categoria,
) -> None:
    """
    Verifica que obtener_preguntas_aleatorias_sin_repeticion() (Módulo 2)
    NUNCA entregue preguntas en BORRADOR o con eliminada_en seteado.
    """
    # Crear 10 preguntas ACTIVAS
    for i in range(10):
        sesion_db.add(
            Pregunta(
                enunciado=f"Pregunta activa {i}",
                opcion_a="A",
                opcion_b="B",
                opcion_c="C",
                opcion_d="D",
                respuesta_correcta="A",
                categoria_id=categoria_prueba.id,
                estado=EstadoPregunta.ACTIVA,
            )
        )

    # Crear 3 preguntas en BORRADOR
    for i in range(3):
        sesion_db.add(
            Pregunta(
                enunciado=f"Pregunta borrador {i}",
                opcion_a="A",
                opcion_b="B",
                opcion_c="C",
                opcion_d="D",
                respuesta_correcta="A",
                categoria_id=categoria_prueba.id,
                estado=EstadoPregunta.BORRADOR,
            )
        )

    # Crear 2 preguntas ELIMINADAS (soft-delete)
    for i in range(2):
        sesion_db.add(
            Pregunta(
                enunciado=f"Pregunta eliminada {i}",
                opcion_a="A",
                opcion_b="B",
                opcion_c="C",
                opcion_d="D",
                respuesta_correcta="A",
                categoria_id=categoria_prueba.id,
                estado=EstadoPregunta.ACTIVA,
                eliminada_en=datetime.now(timezone.utc),
            )
        )
    sesion_db.commit()

    # Pedir 10 preguntas
    preguntas_obtenidas = pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
        sesion_db, categoria_prueba.id, cantidad=10
    )

    assert len(preguntas_obtenidas) == 10
    for p in preguntas_obtenidas:
        assert p.estado == EstadoPregunta.ACTIVA
        assert p.eliminada_en is None
        assert "activa" in p.enunciado.lower()

    # Si pedimos 11 (cuando solo hay 10 activas), debe lanzar ExcepcionValidacion
    with pytest.raises(ExcepcionValidacion):
        pregunta_repository.obtener_preguntas_aleatorias_sin_repeticion(
            sesion_db, categoria_prueba.id, cantidad=11
        )
