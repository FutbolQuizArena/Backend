"""Script CLI para sembrar el banco de preguntas y categorías en la base de datos (Tarea 5.1.5).

Uso:
    python scripts/sembrar_datos.py
    .venv\\Scripts\\python scripts/sembrar_datos.py
"""

import os
import sys

# Agregar la raíz del proyecto al path de Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.base_datos import SesionLocal
from app.services.semilla_service import (
    cargar_preguntas_desde_json,
    resolver_ruta_seed_por_defecto,
    sembrar_preguntas_y_categorias,
)


def ejecutar_siembra() -> None:
    """Ejecuta el proceso de siembra leyendo scripts/preguntas_seed.json."""
    ruta_seed = resolver_ruta_seed_por_defecto()
    print("=" * 65)
    print("   FUTBOLQUIZ ARENA - SIEMBRA DE CATEGORÍAS Y PREGUNTAS")
    print("=" * 65)
    print(f"Archivo origen: {ruta_seed}")

    try:
        preguntas = cargar_preguntas_desde_json(ruta_seed)
        print(f"Preguntas detectadas en JSON: {len(preguntas)}")
    except Exception as e:
        print(f"[ERROR] No se pudo leer el archivo de datos semilla: {e}")
        sys.exit(1)

    db = SesionLocal()
    try:
        print("Iniciando persistencia e indexación en base de datos...")
        resultado = sembrar_preguntas_y_categorias(db, preguntas)

        print("-" * 65)
        print("RESULTADOS DE LA SIEMBRA:")
        print(f"  * Categorías nuevas creadas  : {resultado['categorias_creadas']}")
        print(f"  * Categorías ya existentes   : {resultado['categorias_existentes']}")
        print(f"  * Preguntas nuevas insertadas: {resultado['preguntas_creadas']}")
        print(f"  * Preguntas omitidas (dup/inv): {resultado['preguntas_omitidas']}")
        print(f"  * Total procesadas           : {resultado['total_procesadas']}")
        print("-" * 65)
        print("[ÉXITO] Proceso de siembra finalizado correctamente.")
        print("=" * 65)
    except Exception as e:
        print(f"[ERROR INESPERADO] Error durante la siembra en BD: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    ejecutar_siembra()

