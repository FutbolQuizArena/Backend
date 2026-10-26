"""Repositorio de acceso a datos para la entidad Usuario."""

from typing import Optional
from sqlalchemy import and_, func, or_
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


def _condiciones_jugador_en_ranking() -> tuple:
    """Condiciones para que un usuario aparezca en el ranking: ser jugador y estar habilitado."""
    return (Usuario.rol == RolUsuario.JUGADOR, Usuario.esta_habilitado.is_(True))


def listar_ranking(db: Session, limite: int, desplazamiento: int) -> list[Usuario]:
    """Devuelve una página del ranking general (Tarea 4.1.2).

    Ordena por puntaje_total descendente. Si dos jugadores empatan, queda primero el de
    cuenta más antigua (fecha_alta) y, como último recurso, el de menor id, para que el
    orden sea siempre el mismo.
    """
    return (
        db.query(Usuario)
        .filter(*_condiciones_jugador_en_ranking())
        .order_by(Usuario.puntaje_total.desc(), Usuario.fecha_alta.asc(), Usuario.id.asc())
        .offset(desplazamiento)
        .limit(limite)
        .all()
    )


def contar_jugadores_ranking(db: Session) -> int:
    """Cuenta cuántos jugadores forman parte del ranking general (Tarea 4.1.2)."""
    return db.query(func.count(Usuario.id)).filter(*_condiciones_jugador_en_ranking()).scalar() or 0


def obtener_posicion_ranking(db: Session, usuario: Usuario) -> int:
    """Calcula la posición de un usuario en el ranking general (Tarea 4.1.2).

    La posición es 1 más la cantidad de jugadores que quedan por delante, usando el
    mismo criterio de orden que listar_ranking.
    """
    jugadores_por_delante = (
        db.query(func.count(Usuario.id))
        .filter(
            *_condiciones_jugador_en_ranking(),
            or_(
                Usuario.puntaje_total > usuario.puntaje_total,
                and_(
                    Usuario.puntaje_total == usuario.puntaje_total,
                    Usuario.fecha_alta < usuario.fecha_alta,
                ),
                and_(
                    Usuario.puntaje_total == usuario.puntaje_total,
                    Usuario.fecha_alta == usuario.fecha_alta,
                    Usuario.id < usuario.id,
                ),
            ),
        )
        .scalar()
    )
    return (jugadores_por_delante or 0) + 1


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