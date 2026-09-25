"""Manejador global de excepciones con estructura estandarizada de errores."""

import logging
from typing import Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("futbolquiz.excepciones")


class ExcepcionBase(Exception):
    """Clase base para todas las excepciones del dominio de la aplicación."""

    def __init__(
        self,
        codigo: str,
        mensaje: str,
        detalle: Optional[str] = None,
        codigo_estado: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle
        self.codigo_estado = codigo_estado
        super().__init__(mensaje)


class ExcepcionRecursoNoEncontrado(ExcepcionBase):
    """Excepción lanzada cuando un recurso no existe en el sistema."""

    def __init__(
        self,
        mensaje: str = "El recurso solicitado no fue encontrado",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="RECURSO_NO_ENCONTRADO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_404_NOT_FOUND,
        )


class ExcepcionValidacion(ExcepcionBase):
    """Excepción para errores de lógica de validación del negocio."""

    def __init__(
        self,
        mensaje: str = "Los datos proporcionados no son válidos",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="ERROR_VALIDACION",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class ExcepcionNoAutorizado(ExcepcionBase):
    """Excepción lanzada ante fallas de autenticación o permisos."""

    def __init__(
        self,
        mensaje: str = "Credenciales inválidas o no proporcionadas",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="NO_AUTORIZADO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_401_UNAUTHORIZED,
        )


class ExcepcionBaseDatos(ExcepcionBase):
    """Excepción para errores ocurridos en la capa de persistencia."""

    def __init__(
        self,
        mensaje: str = "Error al operar sobre la base de datos",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="ERROR_BASE_DATOS",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class EmailYaRegistradoError(ExcepcionBase):
    """Excepción lanzada cuando se intenta registrar un usuario con un email que ya existe."""

    def __init__(
        self,
        mensaje: str = "El correo electrónico ya se encuentra registrado",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="EMAIL_YA_REGISTRADO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_409_CONFLICT,
        )


class CredencialesInvalidasError(ExcepcionBase):
    """Excepción lanzada cuando las credenciales de acceso proporcionadas no son válidas."""

    def __init__(
        self,
        mensaje: str = "Credenciales inválidas",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="CREDENCIALES_INVALIDAS",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_401_UNAUTHORIZED,
        )


class TokenInvalidoError(ExcepcionBase):
    """Excepción lanzada cuando un token JWT es inválido, ha expirado o no corresponde a un usuario activo."""

    def __init__(
        self,
        mensaje: str = "Token de autenticación inválido o expirado",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="TOKEN_INVALIDO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_401_UNAUTHORIZED,
        )


class AccesoDenegadoError(ExcepcionBase):
    """Excepción lanzada cuando el usuario no posee los permisos requeridos para acceder al recurso."""

    def __init__(
        self,
        mensaje: str = "No tenés permisos para realizar esta acción",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="ACCESO_DENEGADO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_403_FORBIDDEN,
        )


class TorneoAccesoDenegadoError(ExcepcionBase):
    """Excepción lanzada cuando el usuario no tiene permisos para acceder al torneo (creador o participante requerido)."""

    def __init__(
        self,
        mensaje: str = "No tienes permisos para acceder a este torneo",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="ACCESO_DENEGADO",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_403_FORBIDDEN,
        )


class TorneoNoDisponibleError(ExcepcionBase):
    """Excepción lanzada cuando un torneo no está disponible para unirse, no existe o las credenciales no son válidas."""

    def __init__(
        self,
        mensaje: str = "El torneo no se encuentra disponible para unirse",
        detalle: Optional[str] = None,
        codigo_estado: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(
            codigo="TORNEO_NO_DISPONIBLE",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=codigo_estado,
        )


class PartidaYaFinalizadaError(ExcepcionBase):
    """Excepción lanzada cuando se intenta operar sobre una partida que ya finalizó."""

    def __init__(
        self,
        mensaje: str = "La partida ya se encuentra finalizada",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="PARTIDA_YA_FINALIZADA",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_400_BAD_REQUEST,
        )


class PreguntaYaRespondidaError(ExcepcionBase):
    """Excepción lanzada cuando se intenta responder una pregunta que ya fue respondida."""

    def __init__(
        self,
        mensaje: str = "Esta pregunta ya fue respondida",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="PREGUNTA_YA_RESPONDIDA",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_400_BAD_REQUEST,
        )


class CategoriaYaExisteError(ExcepcionBase):
    """Excepción lanzada cuando se intenta crear o renombrar una categoría con un nombre ya existente."""

    def __init__(
        self,
        mensaje: str = "Ya existe una categoría con ese nombre",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="CATEGORIA_YA_EXISTE",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_409_CONFLICT,
        )


class CategoriaConPreguntasError(ExcepcionBase):
    """Excepción lanzada cuando se intenta eliminar una categoría que posee preguntas vinculadas."""

    def __init__(
        self,
        mensaje: str = "No se puede eliminar la categoría porque contiene preguntas asociadas",
        detalle: Optional[str] = None,
    ) -> None:
        super().__init__(
            codigo="CATEGORIA_CON_PREGUNTAS",
            mensaje=mensaje,
            detalle=detalle,
            codigo_estado=status.HTTP_400_BAD_REQUEST,
        )


def _construir_respuesta_error(
    codigo: str,
    mensaje: str,
    detalle: Optional[str],
    codigo_estado: int,
) -> JSONResponse:
    """Construye un JSONResponse con la estructura estándar fija solicitada."""
    cuerpo = {
        "code": codigo,
        "message": mensaje,
        "detail": detalle,
    }
    return JSONResponse(status_code=codigo_estado, content=cuerpo)


def registrar_manejadores_excepcion(app: FastAPI) -> None:
    """Registra los exception handlers globales en la instancia de FastAPI."""

    @app.exception_handler(ExcepcionBase)
    async def manejador_excepcion_base(
        solicitud: Request, excepcion: ExcepcionBase
    ) -> JSONResponse:
        logger.warning(
            "Excepción de dominio capturada en %s: %s - %s",
            solicitud.url.path,
            excepcion.codigo,
            excepcion.mensaje,
        )
        return _construir_respuesta_error(
            codigo=excepcion.codigo,
            mensaje=excepcion.mensaje,
            detalle=excepcion.detalle,
            codigo_estado=excepcion.codigo_estado,
        )

    @app.exception_handler(RequestValidationError)
    async def manejador_error_validacion(
        solicitud: Request, excepcion: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Fallo de validación de esquema en %s: %s",
            solicitud.url.path,
            excepcion.errors(),
        )
        return _construir_respuesta_error(
            codigo="ERROR_VALIDACION",
            mensaje="Error de validación en los datos de la solicitud",
            detalle=str(excepcion.errors()),
            codigo_estado=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(StarletteHTTPException)
    async def manejador_error_http(
        solicitud: Request, excepcion: StarletteHTTPException
    ) -> JSONResponse:
        logger.warning(
            "Error HTTP capturado en %s: %s - %s",
            solicitud.url.path,
            excepcion.status_code,
            excepcion.detail,
        )
        mensaje = (
            str(excepcion.detail)
            if isinstance(excepcion.detail, str)
            else "Error en la solicitud HTTP"
        )
        return _construir_respuesta_error(
            codigo=f"ERROR_HTTP_{excepcion.status_code}",
            mensaje=mensaje,
            detalle=None,
            codigo_estado=excepcion.status_code,
        )

    @app.exception_handler(Exception)
    async def manejador_error_inesperado(
        solicitud: Request, excepcion: Exception
    ) -> JSONResponse:
        logger.error(
            "Error interno no controlado en %s: %s",
            solicitud.url.path,
            str(excepcion),
            exc_info=True,
        )
        return _construir_respuesta_error(
            codigo="ERROR_INTERNO_SERVIDOR",
            mensaje="Ocurrió un error inesperado en el servidor",
            detalle=str(excepcion),
            codigo_estado=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

