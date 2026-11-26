"""Concurrencia real: TEST_POSTGRES_URL debe apuntar a PostgreSQL de pruebas.

Cada caso crea su propio esquema, lo usa mediante SET LOCAL en cada transacción
y elimina exclusivamente ese esquema al finalizar. Nunca usa DATABASE_URL.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.base_datos import Base
from app.core.excepciones import ExcepcionBase
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta
from app.models.pregunta import Pregunta
from app.repositories import categoria_repository
from app.services import categoria_service, pregunta_service
from tests.test_categorias_jugables import crear_banco


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="Requiere PostgreSQL de pruebas")
@pytest.mark.parametrize("acciones", [("categoria", "categoria"), ("pregunta", "pregunta"), ("categoria", "pregunta")])
def test_dos_solicitudes_no_pueden_quitar_ambas_categorias(acciones):
    url = make_url(os.environ["TEST_POSTGRES_URL"])
    argumentos = {"connect_timeout": 10}
    if url.get_dialect().driver == "psycopg":
        argumentos["prepare_threshold"] = None
    motor = create_engine(url, connect_args=argumentos)
    esquema = "test_banco_" + uuid4().hex
    try:
        with motor.begin() as conexion:
            conexion.execute(text(f'CREATE SCHEMA "{esquema}"'))

        @event.listens_for(motor, "begin")
        def seleccionar_esquema(conexion):
            # Compatible con poolers en modo transacción: no depende del estado de sesión.
            conexion.exec_driver_sql(f'SET LOCAL search_path TO "{esquema}"')
            conexion.exec_driver_sql("SET LOCAL statement_timeout = '20s'")

        Base.metadata.create_all(motor)
        with Session(motor) as db:
            categorias = [crear_banco(db, "Primera"), crear_banco(db, "Segunda")]
            objetivos = [(categoria.id, db.query(Pregunta.id).filter_by(categoria_id=categoria.id).first()[0])
                         for categoria in categorias]

        barrera = Barrier(2, timeout=15)

        def desactivar(indice):
            with Session(motor) as db:
                # Precargar también prueba que no se reutilice estado anterior al bloqueo.
                categoria_repository.obtener_categoria_por_id(db, objetivos[indice][0])
                barrera.wait()
                try:
                    if acciones[indice] == "categoria":
                        categoria_service.cambiar_estado_categoria(db, objetivos[indice][0], EstadoCategoria.BORRADOR)
                    else:
                        pregunta_service.cambiar_estado_pregunta(db, objetivos[indice][1], EstadoPregunta.BORRADOR)
                    return "permitida"
                except ExcepcionBase as error:
                    assert error.codigo == "ULTIMA_CATEGORIA_JUGABLE"
                    return "rechazada"

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(desactivar, (0, 1)))
        assert sorted(resultados) == ["permitida", "rechazada"]
        with Session(motor) as db:
            assert len(categoria_repository.listar_categorias_activas(db)) == 1
    finally:
        with motor.begin() as conexion:
            conexion.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        motor.dispose()
