"""Repositorio de acceso a datos para la entidad Usuario."""

from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario


def obtener_por_email(db: Session, email: str) -> Usuario | None:
    """Obtiene un usuario a partir de su correo electrónico. Retorna None si no existe."""
    return db.query(Usuario).filter(Usuario.email == email).first()


def obtener_por_id(db: Session, id: int) -> Usuario | None:
    """Obtiene un usuario a partir de su identificador único (ID). Retorna None si no existe."""
    return db.query(Usuario).filter(Usuario.id == id).first()


def crear(db: Session, usuario: Usuario) -> Usuario:
    """Persiste una nueva entidad Usuario en la base de datos."""
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def actualizar(db: Session, usuario: Usuario) -> Usuario:
    """Confirma los cambios de una entidad Usuario modificada en la base de datos."""
    db.commit()
    db.refresh(usuario)
    return usuario

def acumular_puntaje(db: Session, usuario_id: int, puntos: int) -> Usuario | None:
    """Suma puntos al puntaje_total del usuario con un UPDATE atómico (Tarea 4.1.1).

    El incremento lo calcula la base de datos (puntaje_total = puntaje_total + puntos),
    así dos partidas que terminan al mismo tiempo no se pisan entre sí.
    Devuelve el usuario actualizado, o None si el usuario no existe.
    """
    filas_actualizadas = (
        db.query(Usuario)
        .filter(Usuario.id == usuario_id)
        .update(
            {Usuario.puntaje_total: Usuario.puntaje_total + puntos},
            synchronize_session=False,
        )
    )
    db.commit()
    if filas_actualizadas == 0:
        return None
    return obtener_por_id(db, id=usuario_id)

def listar_usuarios_admin(
    db: Session,
    buscar: Optional[str] = None,
    rol: Optional[RolUsuario] = None,
    esta_habilitado: Optional[bool] = None,
) -> list[Usuario]:
    """Obtiene el listado de usuarios para administración con filtros opcionales."""
    query = db.query(Usuario)

    if buscar:
        termino = f"%{buscar.strip()}%"
        query = query.filter(
            or_(
                Usuario.nombre.ilike(termino),
                Usuario.email.ilike(termino),
            )
        )

    if rol is not None:
        query = query.filter(Usuario.rol == rol)

    if esta_habilitado is not None:
        query = query.filter(Usuario.esta_habilitado == esta_habilitado)

    query = query.order_by(Usuario.id.asc())
    return query.all()

