"""Script para cargar una categoría de prueba con 10 preguntas (solo para testing manual)."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.base_datos import SesionLocal
from app.models.categoria import Categoria
from app.models.pregunta import Pregunta

db = SesionLocal()

categoria = db.query(Categoria).filter(Categoria.nombre == "PRUEBA - Historia del Futbol").first()
if categoria is None:
    categoria = Categoria(nombre="PRUEBA - Historia del Futbol")
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    print(f"Categoria creada con id={categoria.id}")
else:
    print(f"Categoria ya existia con id={categoria.id}")

preguntas_existentes = db.query(Pregunta).filter(Pregunta.categoria_id == categoria.id).count()
if preguntas_existentes < 10:
    for numero in range(10 - preguntas_existentes):
        pregunta = Pregunta(
            enunciado=f"Pregunta de prueba numero {numero}",
            opcion_a="Correcta",
            opcion_b="Incorrecta 1",
            opcion_c="Incorrecta 2",
            opcion_d="Incorrecta 3",
            respuesta_correcta="A",
            categoria_id=categoria.id,
        )
        db.add(pregunta)
    db.commit()
    print("Preguntas de prueba creadas")
else:
    print("Ya habia suficientes preguntas de prueba")

db.close()