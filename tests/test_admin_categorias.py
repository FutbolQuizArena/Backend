"""Pruebas para la administración de categorías (Tarea 5.1.2 - Módulo 5)."""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta, RolUsuario
from app.models.pregunta import Pregunta
from app.models.usuario import Usuario
from app.repositories import categoria_repository, usuario_repository
from app.services import autenticacion_service, usuario_service


@pytest.fixture
def usuario_admin(sesion_db: Session) -> Usuario:
    """Crea un usuario con rol ADMINISTRADOR."""
    admin = Usuario(
        nombre="Admin Categorias",
        email="admin.cat@futbolquiz.com",
        password_hash=usuario_service.hashear_password("adminPassword123"),
        rol=RolUsuario.ADMINISTRADOR,
    )
    return usuario_repository.crear(sesion_db, admin)


@pytest.fixture
def usuario_jugador(sesion_db: Session) -> Usuario:
    """Crea un usuario regular con rol JUGADOR."""
    jugador = Usuario(
        nombre="Jugador Categorias",
        email="jugador.cat@futbolquiz.com",
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
# Pruebas de Autorización y Seguridad
# ==============================================================================


def test_admin_categorias_sin_token_retorna_401(cliente: TestClient) -> None:
    """Cualquier endpoint de categorías administrativas sin token debe rechazar con 401."""
    resp = cliente.get("/api/admin/categorias")
    assert resp.status_code == 401


def test_admin_categorias_con_rol_jugador_retorna_403(
    cliente: TestClient, headers_jugador: dict[str, str]
) -> None:
    """Un usuario con rol JUGADOR debe ser rechazado con 403 Forbidden."""
    resp = cliente.get("/api/admin/categorias", headers=headers_jugador)
    assert resp.status_code == 403


# ==============================================================================
# Pruebas de Creación (POST /api/admin/categorias)
# ==============================================================================


def test_crear_categoria_exitosa(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Crea una categoría exitosamente con estado ACTIVA por defecto."""
    payload = {"nombre": "Copas del Mundo"}
    resp = cliente.post("/api/admin/categorias", json=payload, headers=headers_admin)
    assert resp.status_code == 201

    data = resp.json()
    assert data["id"] is not None
    assert data["nombre"] == "Copas del Mundo"
    assert data["estado"] == "ACTIVA"
    assert data["preguntas_count"] == 0

    # Verificar en BD
    cat_bd = categoria_repository.obtener_categoria_por_id(sesion_db, data["id"])
    assert cat_bd is not None
    assert cat_bd.nombre == "Copas del Mundo"
    assert cat_bd.estado == EstadoCategoria.ACTIVA


def test_crear_categoria_con_estado_borrador(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Crea una categoría explícitamente en estado BORRADOR."""
    payload = {"nombre": "Champions League", "estado": "BORRADOR"}
    resp = cliente.post("/api/admin/categorias", json=payload, headers=headers_admin)
    assert resp.status_code == 201

    data = resp.json()
    assert data["nombre"] == "Champions League"
    assert data["estado"] == "BORRADOR"


def test_crear_categoria_nombre_duplicado_retorna_409(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Rechaza la creación de una categoría con nombre repetido (insensible a mayúsculas)."""
    payload = {"nombre": "Equipos Historicos"}
    resp1 = cliente.post("/api/admin/categorias", json=payload, headers=headers_admin)
    assert resp1.status_code == 201

    # Intentar crear con diferente casing y espacios
    payload_duplicado = {"nombre": "  equipos historicos  "}
    resp2 = cliente.post("/api/admin/categorias", json=payload_duplicado, headers=headers_admin)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["code"] == "CATEGORIA_YA_EXISTE"


def test_crear_categoria_nombre_vacio_retorna_422(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Rechaza nombres vacíos o formados exclusivamente por espacios en blanco."""
    resp1 = cliente.post("/api/admin/categorias", json={"nombre": ""}, headers=headers_admin)
    assert resp1.status_code == 422

    resp2 = cliente.post("/api/admin/categorias", json={"nombre": "    "}, headers=headers_admin)
    assert resp2.status_code == 422


# ==============================================================================
# Pruebas de Listado y Filtros (GET /api/admin/categorias)
# ==============================================================================


def test_listar_categorias_admin_devuelve_preguntas_count(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Verifica que el listado compute correctamente preguntas_count (excluyendo eliminadas lógicamente)."""
    cat = Categoria(nombre="Reglamento", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()
    sesion_db.refresh(cat)

    # Pregunta 1 activa
    p1 = Pregunta(
        enunciado="¿Cuánto dura un partido?",
        opcion_a="90 min", opcion_b="80 min", opcion_c="100 min", opcion_d="45 min",
        respuesta_correcta="A", categoria_id=cat.id, estado=EstadoPregunta.ACTIVA,
    )
    # Pregunta 2 borrador (debe contarse como asociada)
    p2 = Pregunta(
        enunciado="¿Cuánto dura el entretiempo?",
        opcion_a="15 min", opcion_b="10 min", opcion_c="20 min", opcion_d="5 min",
        respuesta_correcta="A", categoria_id=cat.id, estado=EstadoPregunta.BORRADOR,
    )
    # Pregunta 3 eliminada lógicamente (no debe contarse)
    p3 = Pregunta(
        enunciado="Pregunta vieja eliminada",
        opcion_a="A", opcion_b="B", opcion_c="C", opcion_d="D",
        respuesta_correcta="A", categoria_id=cat.id, estado=EstadoPregunta.ACTIVA,
        eliminada_en=datetime.now(timezone.utc),
    )
    sesion_db.add_all([p1, p2, p3])
    sesion_db.commit()

    resp = cliente.get("/api/admin/categorias", headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()

    cat_item = next(c for c in data if c["id"] == cat.id)
    assert cat_item["preguntas_count"] == 2


def test_listar_categorias_filtro_buscar(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """El filtro buscar filtra por coincidencia parcial insensible a mayúsculas."""
    cat1 = Categoria(nombre="Champions League Especial", estado=EstadoCategoria.ACTIVA)
    cat2 = Categoria(nombre="Copa Libertadores", estado=EstadoCategoria.ACTIVA)
    cat3 = Categoria(nombre="Europa League Sub-20", estado=EstadoCategoria.ACTIVA)
    sesion_db.add_all([cat1, cat2, cat3])
    sesion_db.commit()

    resp = cliente.get("/api/admin/categorias?buscar=league", headers=headers_admin)
    assert resp.status_code == 200
    nombres = [c["nombre"] for c in resp.json()]
    assert "Champions League Especial" in nombres
    assert "Europa League Sub-20" in nombres
    assert "Copa Libertadores" not in nombres


def test_listar_categorias_filtro_estado(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """El filtro estado restringe a ACTIVA o BORRADOR."""
    cat_activa = Categoria(nombre="Goleadores Activa", estado=EstadoCategoria.ACTIVA)
    cat_borrador = Categoria(nombre="Curiosidades Borrador", estado=EstadoCategoria.BORRADOR)
    sesion_db.add_all([cat_activa, cat_borrador])
    sesion_db.commit()

    resp_borrador = cliente.get("/api/admin/categorias?estado=BORRADOR", headers=headers_admin)
    assert resp_borrador.status_code == 200
    items_borrador = resp_borrador.json()
    assert all(c["estado"] == "BORRADOR" for c in items_borrador)
    assert any(c["nombre"] == "Curiosidades Borrador" for c in items_borrador)


# ==============================================================================
# Pruebas de Detalle (GET /api/admin/categorias/{id})
# ==============================================================================


def test_obtener_categoria_detalle_exitoso(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Consulta una categoría puntual por ID."""
    cat = Categoria(nombre="Estadios del Mundo", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    resp = cliente.get(f"/api/admin/categorias/{cat.id}", headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == cat.id
    assert data["nombre"] == "Estadios del Mundo"
    assert data["preguntas_count"] == 0


def test_obtener_categoria_no_existente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Consultar un ID inexistente retorna 404."""
    resp = cliente.get("/api/admin/categorias/999999", headers=headers_admin)
    assert resp.status_code == 404
    assert resp.json()["code"] == "RECURSO_NO_ENCONTRADO"


# ==============================================================================
# Pruebas de Actualización (PATCH /api/admin/categorias/{id})
# ==============================================================================


def test_actualizar_categoria_nombre_y_estado(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Actualiza nombre y estado de una categoría existente."""
    cat = Categoria(nombre="Balon de Oro", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    payload = {"nombre": "Balón de Oro y Premios", "estado": "BORRADOR"}
    resp = cliente.patch(f"/api/admin/categorias/{cat.id}", json=payload, headers=headers_admin)
    assert resp.status_code == 200

    data = resp.json()
    assert data["nombre"] == "Balón de Oro y Premios"
    assert data["estado"] == "BORRADOR"

    # Verificar en BD
    sesion_db.refresh(cat)
    assert cat.nombre == "Balón de Oro y Premios"
    assert cat.estado == EstadoCategoria.BORRADOR


def test_actualizar_categoria_mismo_nombre_no_da_conflicto(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Conservar el mismo nombre durante un PATCH no debe disparar error 409."""
    cat = Categoria(nombre="Directores Técnicos", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    payload = {"nombre": "Directores Técnicos", "estado": "BORRADOR"}
    resp = cliente.patch(f"/api/admin/categorias/{cat.id}", json=payload, headers=headers_admin)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "BORRADOR"


def test_actualizar_categoria_nombre_duplicado_con_otra_retorna_409(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Rechaza renombrar una categoría con un nombre que ya pertenece a otra."""
    cat1 = Categoria(nombre="Historia del Futbol", estado=EstadoCategoria.ACTIVA)
    cat2 = Categoria(nombre="Arbitraje", estado=EstadoCategoria.ACTIVA)
    sesion_db.add_all([cat1, cat2])
    sesion_db.commit()

    payload = {"nombre": "historia del futbol"}
    resp = cliente.patch(f"/api/admin/categorias/{cat2.id}", json=payload, headers=headers_admin)
    assert resp.status_code == 409
    assert resp.json()["code"] == "CATEGORIA_YA_EXISTE"


def test_actualizar_categoria_inexistente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Intentar actualizar una categoría que no existe retorna 404."""
    resp = cliente.patch(
        "/api/admin/categorias/999999",
        json={"nombre": "Inexistente"},
        headers=headers_admin,
    )
    assert resp.status_code == 404


# ==============================================================================
# Pruebas de Cambio Rápido de Estado (PATCH /api/admin/categorias/{id}/estado)
# ==============================================================================


def test_cambiar_estado_categoria_toggle(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Alterna el estado rápidamente entre ACTIVA y BORRADOR."""
    cat = Categoria(nombre="Táctica y Estrategia", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    # Pasar a BORRADOR
    resp1 = cliente.patch(
        f"/api/admin/categorias/{cat.id}/estado",
        json={"estado": "BORRADOR"},
        headers=headers_admin,
    )
    assert resp1.status_code == 200
    assert resp1.json()["estado"] == "BORRADOR"

    # Volver a ACTIVA
    resp2 = cliente.patch(
        f"/api/admin/categorias/{cat.id}/estado",
        json={"estado": "ACTIVA"},
        headers=headers_admin,
    )
    assert resp2.status_code == 200
    assert resp2.json()["estado"] == "ACTIVA"


def test_cambiar_estado_categoria_invalido_retorna_422(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Enviar un estado no admitido retorna 422."""
    cat = Categoria(nombre="Mundialitos", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    resp = cliente.patch(
        f"/api/admin/categorias/{cat.id}/estado",
        json={"estado": "DESHABILITADA"},
        headers=headers_admin,
    )
    assert resp.status_code == 422


# ==============================================================================
# Pruebas de Eliminación (DELETE /api/admin/categorias/{id})
# ==============================================================================


def test_eliminar_categoria_sin_preguntas_exitoso(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Elimina físicamente una categoría que no tiene preguntas vinculadas."""
    cat = Categoria(nombre="Categoría Temporal Vacía", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    resp = cliente.delete(f"/api/admin/categorias/{cat.id}", headers=headers_admin)
    assert resp.status_code == 200
    assert resp.json()["mensaje"] == "Categoría eliminada exitosamente"

    # Comprobar que no existe en BD
    cat_bd = categoria_repository.obtener_categoria_por_id(sesion_db, cat.id)
    assert cat_bd is None


def test_eliminar_categoria_con_preguntas_retorna_400(
    cliente: TestClient, headers_admin: dict[str, str], sesion_db: Session
) -> None:
    """Rechaza la eliminación con 400 Bad Request si la categoría tiene preguntas asociadas."""
    cat = Categoria(nombre="Futbol Femenino", estado=EstadoCategoria.ACTIVA)
    sesion_db.add(cat)
    sesion_db.commit()

    pregunta = Pregunta(
        enunciado="¿Quién ganó el último mundial femenino?",
        opcion_a="España", opcion_b="Inglaterra", opcion_c="EEUU", opcion_d="Alemania",
        respuesta_correcta="A", categoria_id=cat.id,
    )
    sesion_db.add(pregunta)
    sesion_db.commit()

    resp = cliente.delete(f"/api/admin/categorias/{cat.id}", headers=headers_admin)
    assert resp.status_code == 400
    data = resp.json()
    assert data["code"] == "CATEGORIA_CON_PREGUNTAS"

    # Verificar que la categoría sigue existiendo en BD
    cat_bd = categoria_repository.obtener_categoria_por_id(sesion_db, cat.id)
    assert cat_bd is not None


def test_eliminar_categoria_inexistente_retorna_404(
    cliente: TestClient, headers_admin: dict[str, str]
) -> None:
    """Intentar eliminar una categoría inexistente retorna 404."""
    resp = cliente.delete("/api/admin/categorias/999999", headers=headers_admin)
    assert resp.status_code == 404


# ==============================================================================
# Pruebas de Regresión para Módulo 2 (obtener_categoria_aleatoria)
# ==============================================================================


def test_modulo2_regresion_categoria_aleatoria_solo_retorna_activas(sesion_db: Session) -> None:
    """Verifica que obtener_categoria_aleatoria nunca devuelva una categoría en BORRADOR."""
    # Limpiar o crear categorías controladas
    cat_borrador = Categoria(nombre="En Armado Borrador", estado=EstadoCategoria.BORRADOR)
    cat_activa = Categoria(nombre="Oficial Activa", estado=EstadoCategoria.ACTIVA)
    sesion_db.add_all([cat_borrador, cat_activa])
    sesion_db.commit()

    for _ in range(10):
        seleccionada = categoria_repository.obtener_categoria_aleatoria(sesion_db)
        assert seleccionada is not None
        assert seleccionada.estado == EstadoCategoria.ACTIVA
        assert seleccionada.nombre != "En Armado Borrador"


def test_modulo2_regresion_categoria_aleatoria_sin_activas_retorna_none(sesion_db: Session) -> None:
    """Si solo existen categorías en BORRADOR, obtener_categoria_aleatoria retorna None."""
    # Eliminar todas las activas existentes en la sesión de prueba
    for cat in sesion_db.query(Categoria).all():
        cat.estado = EstadoCategoria.BORRADOR
    sesion_db.commit()

    seleccionada = categoria_repository.obtener_categoria_aleatoria(sesion_db)
    assert seleccionada is None
