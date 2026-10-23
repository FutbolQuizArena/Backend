"""Script para limpiar de forma segura las categorías, preguntas y partidas de prueba en la base de datos.

Resuelve los errores de restricción de clave foránea (Foreign Key) eliminando en cascada ordenada:
1. preguntas_partida asociadas a partidas de prueba
2. partidas_individuales y partidas_duelo asociadas
3. partidas asociadas
4. preguntas de prueba
5. categorías de prueba
"""

import os
import sys

# Agregar la raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.base_datos import SesionLocal
from app.models.categoria import Categoria
from app.models.partida import Partida, PartidaIndividual, PreguntaPartida
from app.models.partida_duelo import PartidaDuelo
from app.models.pregunta import Pregunta


def limpiar_categoria_y_dependencias(db, categoria_id: int, categoria_nombre: str) -> None:
    """Elimina en cascada estricta una categoría y todos sus registros dependientes."""
    print(f"\nProcesando limpieza de categoría: [ID {categoria_id}] '{categoria_nombre}'...")

    # 1. Obtener IDs de partidas asociadas a esta categoría
    partidas = db.query(Partida).filter(Partida.categoria_id == categoria_id).all()
    partida_ids = [p.id for p in partidas]
    print(f"  * Partidas encontradas vinculadas: {len(partida_ids)}")

    # 2. Eliminar preguntas_partida vinculadas a esas partidas o a preguntas de esa categoría
    preguntas_categoria = db.query(Pregunta).filter(Pregunta.categoria_id == categoria_id).all()
    pregunta_ids = [p.id for p in preguntas_categoria]

    if partida_ids or pregunta_ids:
        # Eliminar registros de preguntas_partida por partida_id o por pregunta_id
        q_pp = db.query(PreguntaPartida).filter(
            (PreguntaPartida.partida_id.in_(partida_ids)) | (PreguntaPartida.pregunta_id.in_(pregunta_ids))
        )
        total_pp = q_pp.delete(synchronize_session=False)
        print(f"  * Registros eliminados de 'preguntas_partida': {total_pp}")

    # 3. Eliminar de partidas_individuales y partidas_duelo
    if partida_ids:
        total_pi = (
            db.query(PartidaIndividual)
            .filter(PartidaIndividual.id.in_(partida_ids))
            .delete(synchronize_session=False)
        )
        print(f"  * Partidas individuales eliminadas: {total_pi}")

        total_pd = (
            db.query(PartidaDuelo)
            .filter(PartidaDuelo.id.in_(partida_ids))
            .delete(synchronize_session=False)
        )
        print(f"  * Partidas duelo eliminadas: {total_pd}")

        # 4. Eliminar de partidas
        total_p = (
            db.query(Partida)
            .filter(Partida.id.in_(partida_ids))
            .delete(synchronize_session=False)
        )
        print(f"  * Partidas base eliminadas: {total_p}")

    # 5. Eliminar preguntas de la categoría
    if pregunta_ids:
        total_pr = (
            db.query(Pregunta)
            .filter(Pregunta.id.in_(pregunta_ids))
            .delete(synchronize_session=False)
        )
        print(f"  * Preguntas de prueba eliminadas: {total_pr}")

    # 6. Eliminar la categoría
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if cat:
        db.delete(cat)
        print(f"  * Categoría '{categoria_nombre}' eliminada.")

    db.commit()
    print(f"  [OK] Limpieza completada para [ID {categoria_id}] '{categoria_nombre}'.")


def ejecutar_limpieza_pruebas() -> None:
    """Busca categorías de prueba específicas y las elimina de la base de datos."""
    print("=" * 65)
    print("   LIMPIEZA DE CATEGORÍAS Y PREGUNTAS DE PRUEBA EN SUPABASE")
    print("=" * 65)

    nombres_o_patrones_prueba = [
        "PRUEBA - Historia del Futbol",
        "Copa Libertadores Test",
    ]

    db = SesionLocal()
    try:
        categorias = db.query(Categoria).all()
        a_eliminar = []

        for c in categorias:
            nombre = c.nombre.strip()
            # Detectar si coincide con la lista o contiene "PRUEBA" / "Test"
            if (
                nombre in nombres_o_patrones_prueba
                or "PRUEBA" in nombre.upper()
                or "TEST" in nombre.upper()
            ):
                a_eliminar.append((c.id, c.nombre))

        if not a_eliminar:
            print("[INFO] No se encontraron categorías de prueba para eliminar.")
            return

        print(f"Se detectaron {len(a_eliminar)} categoría(s) de prueba para limpiar:")
        for cid, cnom in a_eliminar:
            print(f"  - ID {cid}: {cnom}")

        for cid, cnom in a_eliminar:
            limpiar_categoria_y_dependencias(db, cid, cnom)

        print("-" * 65)
        print("[ÉXITO] Todas las categorías y preguntas de prueba fueron eliminadas.")
        print("Ahora la base de datos solo contiene las categorías y preguntas oficiales.")
        print("=" * 65)
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error durante la limpieza: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    ejecutar_limpieza_pruebas()
