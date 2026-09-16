"""Controlador para rutas de autenticación y registro de usuarios."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import obtener_db
from app.schemas.auth_schema import LoginRequest, TokenResponse
from app.schemas.usuario_schema import UsuarioCreate, UsuarioResponse
from app.services import auth_service, usuario_service

auth_router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@auth_router.post(
    "/registro",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
    description=(
        "Permite dar de alta una nueva cuenta de usuario en la plataforma. "
        "Verifica que el correo electrónico no se encuentre registrado previamente, "
        "hashea la contraseña de manera segura y asigna el rol JUGADOR por defecto."
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "Usuario registrado exitosamente.",
            "model": UsuarioResponse,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Conflicto: El correo electrónico ya se encuentra registrado.",
            "content": {
                "application/json": {
                    "example": {
                        "code": "EMAIL_YA_REGISTRADO",
                        "message": "El correo electrónico ya se encuentra registrado",
                        "detail": None,
                    }
                }
            },
        },
        422: {
            "description": "Error de validación en los datos enviados.",
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
def registrar(
    datos: UsuarioCreate,
    db: Session = Depends(obtener_db),
) -> UsuarioResponse:
    """Endpoint para registrar un usuario delegando la lógica al servicio."""
    usuario_creado = usuario_service.registrar_usuario(db=db, datos=datos)
    return UsuarioResponse.model_validate(usuario_creado)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener token JWT",
    description=(
        "Autentica a un usuario mediante sus credenciales (email y contraseña). "
        "Si las credenciales son válidas, emite un token de acceso JWT (formato Bearer) "
        "con tiempo de expiración configurado."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Autenticación exitosa. Retorna el token de acceso JWT.",
            "model": TokenResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Credenciales inválidas (email inexistente o contraseña incorrecta).",
            "content": {
                "application/json": {
                    "example": {
                        "code": "CREDENCIALES_INVALIDAS",
                        "message": "Credenciales inválidas",
                        "detail": None,
                    }
                }
            },
        },
        422: {
            "description": "Error de validación en el cuerpo de la solicitud.",
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
def login(
    datos: LoginRequest,
    db: Session = Depends(obtener_db),
) -> TokenResponse:
    """Endpoint para iniciar sesión y emitir el token JWT de acceso."""
    usuario = auth_service.autenticar_usuario(
        db=db,
        email=datos.email,
        password=datos.password,
    )
    token = auth_service.generar_token_jwt(usuario)
    return TokenResponse(access_token=token, token_type="bearer")
