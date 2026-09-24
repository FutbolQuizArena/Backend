"""Modelo de base de datos para la entidad Pregunta (Tarea 2.1.1)."""

from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.base_datos import Base


class Pregunta(Base):
    """Modelo ORM que representa una pregunta de opción múltiple."""

    __tablename__ = "preguntas"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    enunciado = Column(Text, nullable=False)
    opcion_a = Column(String(255), nullable=False)
    opcion_b = Column(String(255), nullable=False)
    opcion_c = Column(String(255), nullable=False)
    opcion_d = Column(String(255), nullable=False)
    respuesta_correcta = Column(String(1), nullable=False)  # "A" | "B" | "C" | "D"
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False, index=True)

    categoria = relationship("Categoria", back_populates="preguntas")

    def es_correcta(self, opcion_seleccionada: Optional[str]) -> bool:
        """Indica si la opción seleccionada coincide con la respuesta correcta."""
        if opcion_seleccionada is None:
            return False
        return opcion_seleccionada.upper() == self.respuesta_correcta.upper()

    def obtener_opciones(self) -> dict[str, str]:
        """Devuelve las 4 opciones de la pregunta como diccionario."""
        return {"A": self.opcion_a, "B": self.opcion_b, "C": self.opcion_c, "D": self.opcion_d}