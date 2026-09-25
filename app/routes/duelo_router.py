"""Controlador para rutas de Duelos."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.excepciones import AccesoDenegadoError, ExcepcionRecursoNoEncontrado
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.repositories import duelo_repository
from app.schemas.duelo_schema import DueloEstadoResponse, DueloIniciarLocalRequest, DueloJuegoResponse
from app.schemas.partida_schema import RespuestaPartidaRequest, RespuestaPartidaResponse
from app.services import duelo_service

duelo_router = APIRouter(prefix="/api/duelos", tags=["Duelos"])


def _numero_de_jugador(duelo, usuario_id: int) -> int:
    """Determina si el usuario es el jugador 1 o el jugador 2 del duelo."""
    if duelo.jugador1_id == usuario_id:
        return 1
    return 2


@duelo_router.post(
    "/online",
    response_model=DueloJuegoResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar o crear un duelo en línea",
    description=(
        "Empareja al usuario autenticado con un duelo en línea: si hay alguien esperando "
        "rival se une a ese duelo (que pasa a EN_CURSO), si no, crea uno nuevo que queda "
        "PENDIENTE_RIVAL. Devuelve las preguntas del jugador que consulta. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def buscar_o_crear_duelo_online(
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> DueloJuegoResponse:
    """Endpoint de emparejamiento online, delegando la lógica al servicio."""
    duelo = duelo_service.buscar_o_crear_duelo_online(db, usuario_actual=usuario_actual)
    numero_jugador = _numero_de_jugador(duelo, usuario_actual.id)
    return DueloJuegoResponse.desde_duelo(duelo, numero_jugador)


@duelo_router.post(
    "/local",
    response_model=DueloJuegoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar un duelo local",
    description=(
        "Inicia un duelo local (mismo dispositivo, por turnos) con un invitado sin cuenta. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def iniciar_duelo_local(
    datos: DueloIniciarLocalRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> DueloJuegoResponse:
    """Endpoint para iniciar un duelo local, delegando la lógica al servicio."""
    duelo = duelo_service.iniciar_duelo_local(
        db, usuario_actual=usuario_actual, nombre_invitado=datos.nombre_invitado
    )
    return DueloJuegoResponse.desde_duelo(duelo, numero_jugador=1)


@duelo_router.post(
    "/preguntas/{pregunta_partida_id}/respuesta",
    response_model=RespuestaPartidaResponse,
    status_code=status.HTTP_200_OK,
    summary="Responder una pregunta dentro de un duelo",
    description=(
        "Registra la respuesta del jugador a una de sus preguntas dentro de un duelo. "
        "Si con esta respuesta ambos jugadores ya completaron todas sus preguntas, el "
        "duelo se finaliza automáticamente y se determina el ganador. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
)
def responder_pregunta_duelo(
    pregunta_partida_id: int,
    datos: RespuestaPartidaRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> RespuestaPartidaResponse:
    """Endpoint para responder una pregunta del duelo, delegando la lógica al servicio."""
    pregunta_partida = duelo_service.responder_pregunta_duelo(
        db,
        pregunta_partida_id=pregunta_partida_id,
        opcion_seleccionada=datos.opcion_seleccionada,
        tiempo_respuesta_segundos=datos.tiempo_respuesta_segundos,
        usuario_actual=usuario_actual,
    )
    duelo_service.finalizar_duelo_si_corresponde(db, pregunta_partida.partida_id)
    return RespuestaPartidaResponse(
        es_correcta=pregunta_partida.es_correcta,
        puntaje_obtenido=pregunta_partida.puntaje_obtenido,
    )


@duelo_router.get(
    "/{duelo_id}",
    response_model=DueloEstadoResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar estado y resultado de un duelo",
    description=(
        "Devuelve el estado actual de un duelo (esperando rival, en curso o finalizado) "
        "y, si ya está finalizado, el puntaje de ambos jugadores y quién ganó. "
        "Solo pueden consultarlo los dos jugadores que participan del duelo. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TOKEN_INVALIDO",
                        "message": "Token de autenticación inválido o expirado",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "El usuario autenticado no participa de este duelo.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ACCESO_DENEGADO",
                        "message": "No formás parte de este duelo",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "El duelo especificado no fue encontrado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "RECURSO_NO_ENCONTRADO",
                        "message": "No se encontró el duelo",
                        "detail": None,
                    }
                }
            },
        },
    },
)
def consultar_estado_duelo(
    duelo_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> DueloEstadoResponse:
    """Endpoint para consultar el estado/resultado de un duelo, finalizándolo si ya corresponde."""
    duelo = duelo_repository.obtener_duelo_por_id(db, duelo_id)
    if duelo is None:
        raise ExcepcionRecursoNoEncontrado(mensaje="No se encontró el duelo")

    if usuario_actual.id not in (duelo.jugador1_id, duelo.jugador2_id):
        raise AccesoDenegadoError(mensaje="No formás parte de este duelo")

    duelo = duelo_service.finalizar_duelo_si_corresponde(db, duelo_id)
    return DueloEstadoResponse.model_validate(duelo)