"""Repositorio de acceso a datos para la entidad Usuario."""

from sqlalchemy.orm import Session

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

