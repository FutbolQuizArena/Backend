"""Regresiones de la siembra de categorías y preguntas."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta
from app.models.pregunta import Pregunta
from app.services.semilla_service import sembrar_preguntas_y_categorias


def datos_pregunta(**cambios) -> dict:
    """Construye una entrada válida del archivo semilla."""
    return {
        "category": " Mundiales ",
        "question": " ¿Quién ganó? ",
        "options": {"A": " Argentina ", "B": "Brasil", "C": "Italia", "D": "Francia"},
        "correct_option": " a ",
        "difficulty": "Desconocida",
        **cambios,
    }


def test_siembra_normaliza_datos_y_es_idempotente(sesion_db: Session) -> None:
    datos = [datos_pregunta(), datos_pregunta(category="MUNDIALES", question="Otra pregunta")]
    resultado = sembrar_preguntas_y_categorias(sesion_db, datos)
    assert resultado == {
        "categorias_creadas": 1, "categorias_existentes": 0,
        "preguntas_creadas": 2, "preguntas_omitidas": 0, "total_procesadas": 2,
    }
    pregunta = sesion_db.query(Pregunta).filter(Pregunta.enunciado == "¿Quién ganó?").one()
    assert pregunta.enunciado == "¿Quién ganó?"
    assert pregunta.opcion_a == "Argentina"
    assert pregunta.respuesta_correcta == "A"
    assert pregunta.dificultad == "Media"
    assert pregunta.estado == EstadoPregunta.ACTIVA
    assert pregunta.eliminada_en is None
    assert sesion_db.query(Categoria).one().nombre == "Mundiales"
    assert sembrar_preguntas_y_categorias(sesion_db, datos) == {
        "categorias_creadas": 0, "categorias_existentes": 1,
        "preguntas_creadas": 0, "preguntas_omitidas": 2, "total_procesadas": 2,
    }


@pytest.mark.parametrize("estado", [EstadoCategoria.ACTIVA, EstadoCategoria.BORRADOR])
def test_siembra_reutiliza_y_activa_categoria(sesion_db: Session, estado: EstadoCategoria) -> None:
    categoria = Categoria(nombre="Mundiales", estado=estado)
    sesion_db.add(categoria)
    sesion_db.commit()
    resultado = sembrar_preguntas_y_categorias(sesion_db, [
        datos_pregunta(difficulty="Fácil"),
        datos_pregunta(category="mundiales", question="Otra pregunta", difficulty="Difícil"),
    ])
    assert categoria.estado == EstadoCategoria.ACTIVA
    assert resultado["categorias_existentes"] == 1
    assert resultado["categorias_creadas"] == 0
    assert resultado["preguntas_creadas"] == 2
    assert {p.dificultad for p in sesion_db.query(Pregunta).all()} == {"Fácil", "Difícil"}


@pytest.mark.parametrize("cambios", [
    {"question": " "}, {"options": None}, {"options": []},
    {"options": {"A": "a", "B": "b", "C": "c"}},
    {"options": {"A": "a", "B": "b", "C": "c", "D": " "}},
    {"correct_option": "E"},
])
def test_siembra_omite_pregunta_invalida_pero_crea_categoria(sesion_db: Session, cambios: dict) -> None:
    resultado = sembrar_preguntas_y_categorias(sesion_db, [datos_pregunta(**cambios)])
    assert resultado == {
        "categorias_creadas": 1, "categorias_existentes": 0,
        "preguntas_creadas": 0, "preguntas_omitidas": 1, "total_procesadas": 1,
    }
    assert sesion_db.query(Pregunta).count() == 0
    assert sesion_db.query(Categoria).count() == 1


def test_siembra_sin_categoria_o_sin_datos(sesion_db: Session) -> None:
    resultado = sembrar_preguntas_y_categorias(sesion_db, [datos_pregunta(category=" ")])
    assert resultado["preguntas_omitidas"] == 1
    assert resultado["total_procesadas"] == 1
    assert sesion_db.query(Categoria).count() == 0
    assert all(valor == 0 for valor in sembrar_preguntas_y_categorias(sesion_db, []).values())


def test_siembra_deduplica_por_categoria_incluyendo_preguntas_eliminadas(sesion_db: Session) -> None:
    sembrar_preguntas_y_categorias(sesion_db, [datos_pregunta()])
    pregunta = sesion_db.query(Pregunta).one()
    pregunta.estado = EstadoPregunta.BORRADOR
    pregunta.eliminada_en = datetime.now(timezone.utc)
    sesion_db.commit()
    resultado = sembrar_preguntas_y_categorias(sesion_db, [
        datos_pregunta(), datos_pregunta(category="Clubes"),
    ])
    assert resultado["preguntas_creadas"] == 1
    assert resultado["preguntas_omitidas"] == 1
    assert pregunta.estado == EstadoPregunta.BORRADOR
    assert pregunta.eliminada_en is not None
    assert sesion_db.query(Pregunta).count() == 2
