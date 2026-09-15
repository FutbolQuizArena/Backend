"""Pruebas unitarias para el modelo y los esquemas de Usuario."""

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario_schema import UsuarioBase, UsuarioCreate, UsuarioResponse


def test_creacion_usuario_modelo(sesion_db: Session) -> None:
    """Verifica que se pueda persistir un usuario con valores por defecto correctos."""
    nuevo_usuario = Usuario(
        nombre="Lionel Messi",
        email="messi@futbolquiz.com",
        password_hash="hash_super_seguro_123",
    )
    sesion_db.add(nuevo_usuario)
    sesion_db.commit()
    sesion_db.refresh(nuevo_usuario)

    assert nuevo_usuario.id is not None
    assert nuevo_usuario.nombre == "Lionel Messi"
    assert nuevo_usuario.email == "messi@futbolquiz.com"
    assert nuevo_usuario.password_hash == "hash_super_seguro_123"
    assert nuevo_usuario.rol == RolUsuario.JUGADOR
    assert nuevo_usuario.puntaje_total == 0
    assert nuevo_usuario.esta_habilitado is True
    assert nuevo_usuario.fecha_alta is not None


def test_creacion_usuario_rol_administrador(sesion_db: Session) -> None:
    """Verifica la asignación explícita de rol ADMINISTRADOR."""
    admin = Usuario(
        nombre="Admin Quiz",
        email="admin@futbolquiz.com",
        password_hash="hash_admin",
        rol=RolUsuario.ADMINISTRADOR,
    )
    sesion_db.add(admin)
    sesion_db.commit()
    sesion_db.refresh(admin)

    assert admin.rol == RolUsuario.ADMINISTRADOR


def test_unicidad_email_usuario(sesion_db: Session) -> None:
    """Verifica que no se permita registrar dos usuarios con el mismo email."""
    u1 = Usuario(
        nombre="Usuario 1",
        email="duplicado@futbolquiz.com",
        password_hash="hash1",
    )
    sesion_db.add(u1)
    sesion_db.commit()

    u2 = Usuario(
        nombre="Usuario 2",
        email="duplicado@futbolquiz.com",
        password_hash="hash2",
    )
    sesion_db.add(u2)
    with pytest.raises(IntegrityError):
        sesion_db.commit()


def test_esquema_usuario_create_valido() -> None:
    """Verifica que UsuarioCreate acepte password y no exponga password_hash."""
    datos = {
        "nombre": "Cristiano Ronaldo",
        "email": "cr7@futbolquiz.com",
        "password": "mi_password_secreto",
    }
    schema = UsuarioCreate(**datos)
    assert schema.nombre == "Cristiano Ronaldo"
    assert schema.email == "cr7@futbolquiz.com"
    assert schema.password == "mi_password_secreto"
    assert schema.rol == RolUsuario.JUGADOR
    assert not hasattr(schema, "password_hash")


def test_esquema_usuario_base_email_invalido() -> None:
    """Verifica que UsuarioBase valide el formato de email."""
    with pytest.raises(ValidationError):
        UsuarioBase(nombre="Juan", email="email-no-valido")


def test_esquema_usuario_response_desde_modelo(sesion_db: Session) -> None:
    """Verifica que UsuarioResponse serialice desde el modelo ORM y nunca incluya hashes ni passwords."""
    usuario = Usuario(
        nombre="Diego Maradona",
        email="diego@futbolquiz.com",
        password_hash="hash_privado_inaccesible",
        puntaje_total=100,
    )
    sesion_db.add(usuario)
    sesion_db.commit()
    sesion_db.refresh(usuario)

    respuesta = UsuarioResponse.model_validate(usuario)

    assert respuesta.id == usuario.id
    assert respuesta.nombre == "Diego Maradona"
    assert respuesta.email == "diego@futbolquiz.com"
    assert respuesta.rol == RolUsuario.JUGADOR
    assert respuesta.puntaje_total == 100
    assert respuesta.esta_habilitado is True
    assert respuesta.fecha_alta is not None

    dump = respuesta.model_dump()
    assert "password_hash" not in dump
    assert "password" not in dump

