"""Controlador para rutas de Partida Individual."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.partida_schema import (
    PartidaIndividualResponse,
    ResultadoPartidaResponse,
    RespuestaPartidaRequest,
    RespuestaPartidaResponse,
)
from app.services import partida_service

partida_router = APIRouter(prefix="/api/partidas", tags=["Partidas"])


@partida_router.post(
    "/individual",
    response_model=PartidaIndividualResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar una partida individual",
    description=(
        "Inicia una nueva partida individual para el usuario autenticado: elige una "
        "categoría al azar y le asigna 10 preguntas sin repetir. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def iniciar_partida_individual(
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> PartidaIndividualResponse:
    """Endpoint para iniciar una partida individual, delegando la lógica al servicio."""
    partida = partida_service.iniciar_partida_individual(db, usuario_actual=usuario_actual)
    return PartidaIndividualResponse.desde_partida(partida)


@partida_router.post(
    "/preguntas/{pregunta_partida_id}/respuesta",
    response_model=RespuestaPartidaResponse,
    status_code=status.HTTP_200_OK,
    summary="Responder una pregunta de la partida individual",
    description=(
        "Registra la respuesta del jugador a una pregunta de su partida individual y "
        "devuelve si fue correcta y el puntaje obtenido. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def responder_pregunta_partida(
    pregunta_partida_id: int,
    datos: RespuestaPartidaRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> RespuestaPartidaResponse:
    """Endpoint para responder una pregunta, delegando la lógica al servicio."""
    pregunta_partida = partida_service.responder_pregunta_partida(
        db,
        pregunta_partida_id=pregunta_partida_id,
        opcion_seleccionada=datos.opcion_seleccionada,
        tiempo_respuesta_segundos=datos.tiempo_respuesta_segundos,
        usuario_actual=usuario_actual,
    )
    return RespuestaPartidaResponse(
        es_correcta=pregunta_partida.es_correcta,
        puntaje_obtenido=pregunta_partida.puntaje_obtenido,
    )


@partida_router.get(
    "/{partida_id}/resultado",
    response_model=ResultadoPartidaResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalizar y consultar el resultado de la partida individual",
    description=(
        "Finaliza la partida individual (si todavía no lo estaba), suma el puntaje "
        "obtenido al usuario, y devuelve el resultado final. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def obtener_resultado_partida(
    partida_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> ResultadoPartidaResponse:
    """Endpoint para finalizar y consultar el resultado, delegando la lógica al servicio."""
    partida = partida_service.finalizar_partida_individual(
        db, partida_id=partida_id, usuario_actual=usuario_actual
    )
    return ResultadoPartidaResponse.desde_partida(partida)