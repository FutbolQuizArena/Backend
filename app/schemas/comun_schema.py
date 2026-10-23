"""Esquemas Pydantic comunes y reutilizables para toda la aplicación."""

from pydantic import BaseModel, Field


class MensajeResponse(BaseModel):
    """Esquema de respuesta genérico con mensaje informativo."""

    mensaje: str = Field(
        ...,
        description="Mensaje de confirmación o detalle de la operación realizada",
        examples=["Sesión cerrada exitosamente"],
    )


class SemillaResumenResponse(BaseModel):
    """Esquema de respuesta para el resultado del proceso de siembra de datos."""

    categorias_creadas: int = Field(..., description="Cantidad de categorías nuevas insertadas")
    categorias_existentes: int = Field(..., description="Cantidad de categorías que ya existían")
    preguntas_creadas: int = Field(..., description="Cantidad de preguntas nuevas insertadas")
    preguntas_omitidas: int = Field(
        ...,
        description="Cantidad de preguntas omitidas por ya existir en BD o tener estructura incompleta",
    )
    total_procesadas: int = Field(..., description="Total de preguntas evaluadas en el lote")

