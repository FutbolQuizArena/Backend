"""Pruebas de la consulta del ranking general (Tarea 4.1.2, RF-16)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.services import autenticacion_service

URL_RANKING = "/api/ranking"


def _crear_usuario(
    db: Session,
    nombre: str,
    puntaje_total: int = 0,
    rol: RolUsuario = RolUsuario.JUGADOR,
    esta_habilitado: bool = True,
) -> Usuario:
    """Crea un usuario de prueba con puntaje, rol y estado de habilitación a elección."""
    usuario = Usuario(
        nombre=nombre,
        email=f"{nombre.lower()}@futbolquiz.com",
        password_hash="hash_de_prueba",
        rol=rol,
        puntaje_total=puntaje_total,
        esta_habilitado=esta_habilitado,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _encabezado(usuario: Usuario) -> dict[str, str]:
    """Encabezado Authorization con un token válido para el usuario."""
    token = autenticacion_service.generar_token_jwt(usuario)
    return {"Authorization": f"Bearer {token}"}


def test_ranking_requiere_autenticacion(cliente: TestClient) -> None:
    respuesta = cliente.get(URL_RANKING)

    assert respuesta.status_code == 401


def test_ranking_ordena_por_puntaje_de_mayor_a_menor(
    cliente: TestClient, sesion_db: Session
) -> None:
    _crear_usuario(sesion_db, "Bajo", puntaje_total=10)
    alto = _crear_usuario(sesion_db, "Alto", puntaje_total=300)
    _crear_usuario(sesion_db, "Medio", puntaje_total=120)

    respuesta = cliente.get(URL_RANKING, headers=_encabezado(alto))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert [j["nombre"] for j in cuerpo["jugadores"]] == ["Alto", "Medio", "Bajo"]
    assert [j["posicion"] for j in cuerpo["jugadores"]] == [1, 2, 3]
    assert cuerpo["total_jugadores"] == 3


def test_ranking_desempata_por_cuenta_mas_antigua(
    cliente: TestClient, sesion_db: Session
) -> None:
    primero = _crear_usuario(sesion_db, "Antiguo", puntaje_total=100)
    _crear_usuario(sesion_db, "Reciente", puntaje_total=100)

    respuesta = cliente.get(URL_RANKING, headers=_encabezado(primero))

    nombres = [j["nombre"] for j in respuesta.json()["jugadores"]]
    assert nombres == ["Antiguo", "Reciente"]


def test_ranking_excluye_administradores_y_usuarios_deshabilitados(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Jugador", puntaje_total=50)
    _crear_usuario(sesion_db, "Admin", puntaje_total=999, rol=RolUsuario.ADMINISTRADOR)
    _crear_usuario(sesion_db, "Baja", puntaje_total=500, esta_habilitado=False)

    respuesta = cliente.get(URL_RANKING, headers=_encabezado(jugador))

    cuerpo = respuesta.json()
    assert [j["nombre"] for j in cuerpo["jugadores"]] == ["Jugador"]
    assert cuerpo["total_jugadores"] == 1


def test_ranking_no_expone_email_ni_contrasena(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Privado", puntaje_total=5)

    respuesta = cliente.get(URL_RANKING, headers=_encabezado(jugador))

    fila = respuesta.json()["jugadores"][0]
    assert set(fila) == {"posicion", "usuario_id", "nombre", "puntaje_total"}


def test_ranking_pagina_los_resultados_con_posiciones_continuas(
    cliente: TestClient, sesion_db: Session
) -> None:
    usuarios = [_crear_usuario(sesion_db, f"Jug{n}", puntaje_total=100 - n) for n in range(5)]

    respuesta = cliente.get(
        URL_RANKING, params={"pagina": 2, "tamano_pagina": 2}, headers=_encabezado(usuarios[0])
    )

    cuerpo = respuesta.json()
    assert [j["nombre"] for j in cuerpo["jugadores"]] == ["Jug2", "Jug3"]
    assert [j["posicion"] for j in cuerpo["jugadores"]] == [3, 4]
    assert cuerpo["pagina"] == 2
    assert cuerpo["tamano_pagina"] == 2
    assert cuerpo["total_jugadores"] == 5


def test_ranking_pagina_fuera_de_rango_devuelve_lista_vacia(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Unico", puntaje_total=1)

    respuesta = cliente.get(URL_RANKING, params={"pagina": 9}, headers=_encabezado(jugador))

    assert respuesta.status_code == 200
    assert respuesta.json()["jugadores"] == []


def test_ranking_informa_mi_posicion_aunque_este_en_otra_pagina(
    cliente: TestClient, sesion_db: Session
) -> None:
    for n in range(4):
        _crear_usuario(sesion_db, f"Top{n}", puntaje_total=1000 - n)
    yo = _crear_usuario(sesion_db, "Yo", puntaje_total=5)

    respuesta = cliente.get(
        URL_RANKING, params={"pagina": 1, "tamano_pagina": 2}, headers=_encabezado(yo)
    )

    mi_posicion = respuesta.json()["mi_posicion"]
    assert mi_posicion["nombre"] == "Yo"
    assert mi_posicion["posicion"] == 5
    assert mi_posicion["puntaje_total"] == 5


def test_ranking_mi_posicion_es_nula_para_administradores(
    cliente: TestClient, sesion_db: Session
) -> None:
    _crear_usuario(sesion_db, "Jugador", puntaje_total=20)
    admin = _crear_usuario(sesion_db, "Admin", rol=RolUsuario.ADMINISTRADOR)

    respuesta = cliente.get(URL_RANKING, headers=_encabezado(admin))

    assert respuesta.status_code == 200
    assert respuesta.json()["mi_posicion"] is None


def test_ranking_rechaza_parametros_de_paginacion_invalidos(
    cliente: TestClient, sesion_db: Session
) -> None:
    jugador = _crear_usuario(sesion_db, "Param", puntaje_total=1)
    encabezado = _encabezado(jugador)

    assert cliente.get(URL_RANKING, params={"pagina": 0}, headers=encabezado).status_code == 422
    assert cliente.get(URL_RANKING, params={"tamano_pagina": 0}, headers=encabezado).status_code == 422
    assert cliente.get(URL_RANKING, params={"tamano_pagina": 101}, headers=encabezado).status_code == 422