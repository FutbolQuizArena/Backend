"""Acceso a las revocaciones compartidas por todas las instancias del backend."""

from sqlalchemy.dialects.postgresql import insert as insertar_postgresql
from sqlalchemy.dialects.sqlite import insert as insertar_sqlite
from sqlalchemy.orm import Session

from app.models.token_revocado import TokenRevocado


def esta_revocado(db: Session, huella: str) -> bool:
    """Consulta la base en cada petición, sin depender de cachés en memoria."""
    return db.get(TokenRevocado, huella) is not None


def revocar(db: Session, huella: str, expira_en: int, ahora: int) -> None:
    """Persiste la revocación y limpia vencidas; admite cierres concurrentes."""
    insertar = (
        insertar_sqlite if db.get_bind().dialect.name == "sqlite" else insertar_postgresql
    )
    try:
        db.query(TokenRevocado).filter(TokenRevocado.expira_en <= ahora).delete(
            synchronize_session=False
        )
        db.execute(
            insertar(TokenRevocado)
            .values(huella=huella, expira_en=expira_en)
            .on_conflict_do_nothing(index_elements=["huella"])
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
