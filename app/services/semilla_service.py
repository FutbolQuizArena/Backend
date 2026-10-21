"""Servicio para la carga y siembra (seed) modular e idempotente de categorías y preguntas (Tarea 5.1.5)."""

import json
import os
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.excepciones import ExcepcionValidacion
from app.models.categoria import Categoria
from app.models.enumeraciones import EstadoCategoria, EstadoPregunta
from app.models.pregunta import Pregunta
from app.repositories import categoria_repository


def resolver_ruta_seed_por_defecto() -> str:
    """Resuelve la ruta absoluta por defecto al archivo scripts/preguntas_seed.json."""
    raiz = Path(__file__).resolve().parent.parent.parent
    return str(raiz / "scripts" / "preguntas_seed.json")


def cargar_preguntas_desde_json(ruta_archivo: Optional[str] = None) -> list[dict[str, Any]]:
    """Lee y parsea un archivo JSON con preguntas estructuradas para siembra."""
    ruta = ruta_archivo or resolver_ruta_seed_por_defecto()
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo de datos semilla en: {ruta}")

    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)

    if not isinstance(datos, list):
        raise ExcepcionValidacion(
            mensaje="El formato del archivo JSON de seed es inválido; debe ser una lista de preguntas"
        )

    return datos


def _obtener_o_crear_categoria_activa(db: Session, nombre: str) -> tuple[Categoria, bool]:
    """Devuelve una categoría activa e indica si fue creada."""
    categoria = categoria_repository.obtener_categoria_por_nombre(db, nombre)
    if categoria is None:
        categoria = Categoria(nombre=nombre, estado=EstadoCategoria.ACTIVA)
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
        return categoria, True

    if categoria.estado != EstadoCategoria.ACTIVA:
        categoria.estado = EstadoCategoria.ACTIVA
        db.commit()
        db.refresh(categoria)
    return categoria, False


def _preparar_datos_pregunta(item: dict[str, Any]) -> dict[str, str] | None:
    """Normaliza una pregunta semilla y rechaza estructuras incompletas."""
    enunciado = str(item.get("question", "")).strip()
    opciones = item.get("options")
    respuesta_correcta = str(item.get("correct_option", "")).strip().upper()
    dificultad = str(item.get("difficulty", "Media")).strip()
    if not enunciado or not isinstance(opciones, dict):
        return None

    opciones_normalizadas = [str(opciones.get(letra, "")).strip() for letra in ("A", "B", "C", "D")]
    if not all(opciones_normalizadas):
        return None
    if respuesta_correcta not in ("A", "B", "C", "D"):
        return None
    if dificultad not in ("Fácil", "Media", "Difícil"):
        dificultad = "Media"

    return {
        "enunciado": enunciado,
        "opcion_a": opciones_normalizadas[0],
        "opcion_b": opciones_normalizadas[1],
        "opcion_c": opciones_normalizadas[2],
        "opcion_d": opciones_normalizadas[3],
        "respuesta_correcta": respuesta_correcta,
        "dificultad": dificultad,
    }


def sembrar_preguntas_y_categorias(
    db: Session, lista_preguntas: list[dict[str, Any]]
) -> dict[str, int]:
    """Siembra categorías y preguntas en la base de datos de manera modular e idempotente.

    Mapeo de datos:
    - category -> Categoria (nombre case-insensitive, EstadoCategoria.ACTIVA)
    - question -> Pregunta (enunciado, opciones A-D, respuesta_correcta, dificultad, EstadoPregunta.ACTIVA)

    Idempotencia:
    - Si la categoría ya existe, se asegura de que esté ACTIVA y no se duplica.
    - Si la pregunta ya existe para esa categoría, se omite y no se duplica.

    Retorna un diccionario con las métricas del proceso.
    """
    categorias_creadas = 0
    categorias_existentes = 0
    preguntas_creadas = 0
    preguntas_omitidas = 0
    total_procesadas = 0

    # Caché en memoria para evitar consultas reiteradas por categoría
    categorias_cache: dict[str, Categoria] = {}

    for item in lista_preguntas:
        total_procesadas += 1

        # 1. Validar categoría
        cat_nombre = str(item.get("category", "")).strip()
        if not cat_nombre:
            preguntas_omitidas += 1
            continue

        clave_cat = cat_nombre.lower()
        categoria = categorias_cache.get(clave_cat)

        if categoria is None:
            categoria, fue_creada = _obtener_o_crear_categoria_activa(db, cat_nombre)
            if fue_creada:
                categorias_creadas += 1
            else:
                categorias_existentes += 1

            categorias_cache[clave_cat] = categoria

        # 2. Validar estructura de la pregunta
        datos_pregunta = _preparar_datos_pregunta(item)
        if datos_pregunta is None:
            preguntas_omitidas += 1
            continue

        # 3. Idempotencia: Verificar si la pregunta ya existe en la categoría
        pregunta_existente = (
            db.query(Pregunta)
            .filter(
                Pregunta.categoria_id == categoria.id,
                Pregunta.enunciado == datos_pregunta["enunciado"],
            )
            .first()
        )

        if pregunta_existente is not None:
            preguntas_omitidas += 1
            continue

        # 4. Crear y persistir la nueva pregunta
        nueva_pregunta = Pregunta(
            **datos_pregunta,
            categoria_id=categoria.id,
            estado=EstadoPregunta.ACTIVA,
            eliminada_en=None,
        )
        db.add(nueva_pregunta)
        preguntas_creadas += 1

    db.commit()

    return {
        "categorias_creadas": categorias_creadas,
        "categorias_existentes": categorias_existentes,
        "preguntas_creadas": preguntas_creadas,
        "preguntas_omitidas": preguntas_omitidas,
        "total_procesadas": total_procesadas,
    }

