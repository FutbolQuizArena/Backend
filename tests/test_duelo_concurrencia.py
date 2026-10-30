"""Integración PostgreSQL: configurar TEST_POSTGRES_URL con una base de pruebas.

Cada ejecución crea y elimina su propio esquema aislado, sin usar DATABASE_URL.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.core.base_datos import Base
from app.models.enumeraciones import EstadoPartida
from app.models.partida_duelo import PartidaDuelo
from app.models.usuario import Usuario
from app.services import duelo_service
from tests.test_duelo import _crear_categoria_con_preguntas, _crear_usuario


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="Requiere PostgreSQL de pruebas")
def test_cuatro_busquedas_simultaneas_forman_dos_duelos():
    motor = create_engine(os.environ["TEST_POSTGRES_URL"], connect_args={"connect_timeout": 5})
    esquema = "test_duelo_" + uuid4().hex
    try:
        with motor.begin() as conexion:
            conexion.execute(text(f'CREATE SCHEMA "{esquema}"'))

        @event.listens_for(motor, "checkout")
        def seleccionar_esquema(conexion, registro, proxy):
            with conexion.cursor() as cursor:
                cursor.execute(f'SET search_path TO "{esquema}"')
            conexion.commit()

        Base.metadata.create_all(motor)
        with Session(motor) as db:
            _crear_categoria_con_preguntas(db)
            ids = [_crear_usuario(db, f"j{i}@test.com").id for i in range(4)]

        barrera = Barrier(4, timeout=10)

        def buscar(usuario_id):
            with Session(motor) as db:
                db.execute(text("SET statement_timeout = '15s'"))
                usuario = db.get(Usuario, usuario_id)
                barrera.wait()
                return duelo_service.buscar_o_crear_duelo_online(db, usuario).id

        with ThreadPoolExecutor(max_workers=4) as ejecutor:
            resultados = list(ejecutor.map(buscar, ids))

        assert len(set(resultados)) == 2
        with Session(motor) as db:
            duelos = db.query(PartidaDuelo).all()
            assert len(duelos) == 2
            assert all(d.estado == EstadoPartida.EN_CURSO for d in duelos)
            participantes = [j for d in duelos for j in (d.jugador1_id, d.jugador2_id)]
            assert sorted(participantes) == sorted(ids)
            assert all(len(d.preguntas_de_jugador(n)) == 10 for d in duelos for n in (1, 2))
    finally:
        with motor.begin() as conexion:
            conexion.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        motor.dispose()
