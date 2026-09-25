"""Controlador para rutas de gestión y participación en Torneos."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.base_datos import obtener_db
from app.core.seguridad import obtener_usuario_actual
from app.models.usuario import Usuario
from app.schemas.comun_schema import MensajeResponse
from app.schemas.torneo_schema import (
    CruceIniciarDueloResponse,
    CruceResolucionResponse,
    CruceResolverRequest,
    FiltroTorneoEnum,
    TorneoCreadoResponse,
    TorneoCreate,
    TorneoDetalleResponse,
    TorneoListItemResponse,
    TorneoResponse,
    TorneoUnirseRequest,
)
from app.services import torneo_service

torneo_router = APIRouter(prefix="/api/torneos", tags=["Torneos"])


@torneo_router.post(
    "",
    response_model=TorneoCreadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo torneo",
    description=(
        "Crea un nuevo torneo con cupo de 4, 8 o 16 participantes y contraseña opcional. "
        "Genera automáticamente el código de acceso alfanumérico e inscribe de manera "
        "inmediata al usuario creador como primer participante del torneo. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Torneo creado exitosamente con código de acceso asignado.",
            "model": TorneoCreadoResponse,
        },
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación en los datos del torneo (nombre vacío o cupo distinto de 4, 8 o 16).",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ERROR_VALIDACION",
                        "message": "Error de validación en los datos de la solicitud",
                        "detail": "[...]",
                    }
                }
            },
        },
    },
)
def crear_torneo(
    datos: TorneoCreate,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> TorneoCreadoResponse:
    """Endpoint para crear un torneo delegando la lógica al servicio."""
    torneo = torneo_service.crear_torneo(
        db=db,
        datos=datos,
        usuario_actual=usuario_actual,
    )
    return TorneoCreadoResponse.model_validate(torneo)


@torneo_router.post(
    "/unirse",
    response_model=TorneoResponse,
    status_code=status.HTTP_200_OK,
    summary="Unirse a un torneo mediante código de acceso",
    description=(
        "Permite a un usuario autenticado unirse a un torneo existente utilizando su código "
        "de acceso y contraseña (si el torneo es privado). Si al unirse se alcanza el cupo "
        "máximo de participantes, el torneo transiciona automáticamente al estado EN_CURSO. "
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Unión exitosa al torneo. Retorna el estado actualizado del torneo.",
            "model": TorneoResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "El torneo no está disponible para unirse (código inexistente, contraseña errónea, torneo completo o no disponible).",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TORNEO_NO_DISPONIBLE",
                        "message": "El torneo no se encuentra disponible para unirse",
                        "detail": None,
                    }
                }
            },
        },
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Error de validación en los datos de la solicitud.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ERROR_VALIDACION",
                        "message": "Error de validación en los datos de la solicitud",
                        "detail": "[...]",
                    }
                }
            },
        },
    },
)
def unirse_a_torneo(
    datos: TorneoUnirseRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> TorneoResponse:
    """Endpoint para unirse a un torneo delegando la lógica al servicio."""
    torneo = torneo_service.unirse_a_torneo(
        db=db,
        datos=datos,
        usuario_actual=usuario_actual,
    )
    return TorneoResponse.model_validate(torneo)


@torneo_router.get(
    "",
    response_model=list[TorneoListItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar torneos según filtro",
    description=(
        "Obtiene el listado de torneos filtrados por categoría:\n"
        "- `mios` (por defecto): Torneos donde el usuario autenticado está inscripto como participante.\n"
        "- `disponibles`: Torneos en estado ESPERANDO_JUGADORES con cupo disponible donde el usuario aún no participa.\n"
        "- `finalizados`: Torneos en estado FINALIZADO en los que el usuario participó.\n\n"
        "Protege datos sensibles: nunca expone la contraseña de acceso y únicamente incluye el código de acceso "
        "en aquellos torneos donde el usuario autenticado es el creador."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Listado de torneos recuperado exitosamente.",
            "model": list[TorneoListItemResponse],
        },
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Filtro no reconocido (valores permitidos: mios, disponibles, finalizados).",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ERROR_VALIDACION",
                        "message": "Error de validación en los datos de la solicitud",
                        "detail": "[...]",
                    }
                }
            },
        },
    },
)
def listar_torneos(
    filtro: FiltroTorneoEnum = Query(
        default=FiltroTorneoEnum.MIOS,
        description="Filtro de torneos a consultar: 'mios', 'disponibles' o 'finalizados'",
    ),
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> list[TorneoListItemResponse]:
    """Endpoint para listar torneos delegando la consulta al servicio."""
    return torneo_service.listar_torneos(
        db=db,
        filtro=filtro,
        usuario_actual=usuario_actual,
    )


@torneo_router.get(
    "/{torneo_id}",
    response_model=TorneoDetalleResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener estado, participantes y cuadro de un torneo",
    description=(
        "Obtiene la información detallada de la sala del torneo para el creador y los participantes inscriptos.\n\n"
        "- Retorna los datos del torneo, el organizador (creador), el código de acceso y la lista completa de participantes.\n"
        "- El campo `cuadro` incluye los cruces eliminatorios ordenados por ronda. Si el torneo aún se encuentra en "
        "estado `ESPERANDO_JUGADORES`, `cuadro` viene como una lista vacía ya que los cruces se generan al completarse el cupo.\n"
        "- En los cruces con estado `PENDIENTE`, el campo `ganador` viene como null (se completará con la resolución de partidas en 3.2.2).\n"
        "- Control de acceso estricto: requiere que el usuario autenticado sea el creador o un participante inscripto del torneo (HTTP 403).\n\n"
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Detalle del torneo, participantes y cuadro obtenidos exitosamente.",
            "model": TorneoDetalleResponse,
        },
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
            "description": "Acceso denegado: el usuario no es creador ni participante del torneo.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "ACCESO_DENEGADO",
                        "message": "No tienes permisos para acceder a este torneo",
                        "detail": None,
                    }
                }
            },
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "El torneo solicitado no fue encontrado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TORNEO_NO_DISPONIBLE",
                        "message": "No se encontró ningún torneo con el ID 1",
                        "detail": None,
                    }
                }
            },
        },
    },
)
def obtener_detalle_torneo(
    torneo_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> TorneoDetalleResponse:
    """Endpoint para consultar la sala del torneo, participantes y cuadro de llaves."""
    return torneo_service.obtener_detalle_torneo(
        db=db,
        torneo_id=torneo_id,
        usuario_actual=usuario_actual,
    )


@torneo_router.delete(
    "/{torneo_id}/salir",
    response_model=MensajeResponse,
    status_code=status.HTTP_200_OK,
    summary="Salir de un torneo",
    description=(
        "Permite a un usuario autenticado abandonar un torneo antes de que este comience (estado ESPERANDO_JUGADORES).\n\n"
        "- Si el usuario es un participante regular: se remueve su inscripción y el torneo continúa abierto.\n"
        "- Si el usuario es el creador del torneo: el torneo completo se cancela y se eliminan sus participantes asociados.\n"
        "- No está permitido salir de torneos que ya hayan iniciado (EN_CURSO) o finalizado (FINALIZADO).\n\n"
        "Requiere token JWT Bearer en el encabezado Authorization."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Salida exitosa o cancelación del torneo.",
            "model": MensajeResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "El usuario no es participante del torneo o el torneo ya ha comenzado/finalizado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TORNEO_NO_DISPONIBLE",
                        "message": "No es posible salir de un torneo que ya ha comenzado o finalizado",
                        "detail": None,
                    }
                }
            },
        },
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
        status.HTTP_404_NOT_FOUND: {
            "description": "El torneo especificado no fue encontrado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "RECURSO_NO_ENCONTRADO",
                        "message": "No se encontró ningún torneo con el ID 1",
                        "detail": None,
                    }
                }
            },
        },
    },
)
def salir_de_torneo(
    torneo_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> MensajeResponse:
    """Endpoint para salir de un torneo delegando la lógica al servicio."""
    mensaje = torneo_service.salir_de_torneo(
        db=db,
        torneo_id=torneo_id,
        usuario_actual=usuario_actual,
    )
    return MensajeResponse(mensaje=mensaje)


@torneo_router.post(
    "/{torneo_id}/cruces/{cruce_id}/iniciar-duelo",
    response_model=CruceIniciarDueloResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar o recuperar el duelo para un cruce eliminatorio",
    description=(
        "Crea o recupera la PartidaDuelo online entre los dos participantes del cruce eliminatorio, "
        "asignando la categoría y las 10 preguntas compartidas para ambos. "
        "Solo los participantes que integran el cruce pueden iniciar o acceder al duelo."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Duelo iniciado o recuperado exitosamente.",
            "model": CruceIniciarDueloResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "El torneo no está en curso o el cruce ya ha sido disputado.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "El usuario no forma parte de este cruce eliminatorio.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "El torneo o el cruce especificado no existe.",
        },
    },
)
def iniciar_duelo_cruce(
    torneo_id: int,
    cruce_id: int,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> CruceIniciarDueloResponse:
    """Inicia o recupera el duelo para disputar un cruce de torneo."""
    return torneo_service.iniciar_duelo_cruce(
        db=db,
        torneo_id=torneo_id,
        cruce_id=cruce_id,
        usuario_actual=usuario_actual,
    )


@torneo_router.post(
    "/{torneo_id}/cruces/{cruce_id}/resolver",
    response_model=CruceResolucionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolver cruce eliminatorio y avanzar ronda",
    description=(
        "Determina el participante ganador del cruce a partir de un duelo disputado (duelo_id) "
        "o especificando directamente el ID del participante ganador (ganador_participante_id). "
        "Evalúa si la ronda actual concluyó: si aún hay cruces pendientes espera; si todos finalizaron, "
        "genera automáticamente la siguiente ronda o consagra y premia al campeón si era la Final."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Cruce resuelto exitosamente y estado del torneo actualizado.",
            "model": CruceResolucionResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Error en los datos de resolución, duelo no finalizado o cruce ya resuelto.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Token inválido, expirado o ausente.",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "El usuario no tiene permisos para resolver este cruce.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "El torneo, cruce o duelo no existe.",
        },
    },
)
def resolver_cruce(
    torneo_id: int,
    cruce_id: int,
    datos: CruceResolverRequest,
    usuario_actual: Usuario = Depends(obtener_usuario_actual),
    db: Session = Depends(obtener_db),
) -> CruceResolucionResponse:
    """Resuelve un cruce eliminatorio y evalúa el avance de ronda o coronación del campeón."""
    return torneo_service.resolver_cruce(
        db=db,
        torneo_id=torneo_id,
        cruce_id=cruce_id,
        usuario_actual=usuario_actual,
        datos=datos,
    )

