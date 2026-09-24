"""Modelo de base de datos para la entidad Categoria (Tarea 2.1.1)."""

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.core.base_datos import Base


class Categoria(Base):
    """Modelo ORM que representa una categoría de preguntas."""

    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)

    preguntas = relationship("Pregunta", back_populates="categoria")
