"""Esquemas Pydantic comunes y reutilizables para toda la aplicación."""

from pydantic import BaseModel, Field


class MensajeResponse(BaseModel):
    """Esquema de respuesta genérico con mensaje informativo."""

    mensaje: str = Field(
        ...,
        description="Mensaje de confirmación o detalle de la operación realizada",
        examples=["Sesión cerrada exitosamente"],
    )

