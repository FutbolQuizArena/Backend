"""Modelo de base de datos para la entidad Categoria (Tarea 2.1.1)."""

from sqlalchemy import Column, Enum as SQLEnum, Integer, String
from sqlalchemy.orm import relationship

from app.core.base_datos import Base
from app.models.enumeraciones import EstadoCategoria


class Categoria(Base):
    """Modelo ORM que representa una categoría de preguntas."""

    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    estado = Column(
        SQLEnum(EstadoCategoria, name="estado_categoria_enum"),
        nullable=False,
        default=EstadoCategoria.ACTIVA,
        server_default=EstadoCategoria.ACTIVA.value,
    )

    preguntas = relationship("Pregunta", back_populates="categoria")

