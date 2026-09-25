"""Script heredado de carga de datos de prueba (delegado a scripts/sembrar_datos.py)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.sembrar_datos import ejecutar_siembra

if __name__ == "__main__":
    print("[AVISO] scripts/sembrar_datos_prueba.py ha sido unificado en scripts/sembrar_datos.py")
    ejecutar_siembra()
db.close()