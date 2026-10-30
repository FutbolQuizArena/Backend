"""Lógica de negocio del ranking general (Tareas 4.1.1 y 4.1.2, RF-11 y RF-16)."""

from sqlalchemy.orm import Session

from app.models.enumeraciones import RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuario_repository
from app.schemas.ranking_schema import JugadorRankingResponse, RankingResponse

PUNTOS_CAMPEON_TORNEO = 1500


def acumular_puntaje(db: Session, usuario_id: int, puntos: int, confirmar: bool = True) -> Usuario | None:
    """
    Suma al puntaje acumulado de un usuario los puntos ganados al finalizar una partida
    individual, un duelo o un torneo (RF-11). El ranking general se ordena por ese puntaje.

    Es el único punto del sistema que modifica el puntaje acumulado: así todas las
    formas de ganar puntos se actualizan de la misma manera.
    - Si los puntos son 0 o negativos no se modifica nada: el puntaje acumulado nunca baja.
    - Si el usuario no existe retorna None.
    """
    if puntos <= 0:
        return usuario_repository.obtener_por_id(db, id=usuario_id)
    if confirmar:
        return usuario_repository.acumular_puntaje(db, usuario_id=usuario_id, puntos=puntos)
    return usuario_repository.acumular_puntaje(db, usuario_id=usuario_id, puntos=puntos, confirmar=False)


def _participa_del_ranking(usuario: Usuario) -> bool:
    """Solo los jugadores habilitados forman parte del ranking."""
    return usuario.rol == RolUsuario.JUGADOR and usuario.esta_habilitado


def _armar_fila(posicion: int, usuario: Usuario) -> JugadorRankingResponse:
    """Convierte un usuario en una fila del ranking, exponiendo solo los datos públicos."""
    return JugadorRankingResponse(
        posicion=posicion,
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        puntaje_total=usuario.puntaje_total,
    )


def obtener_ranking(
    db: Session, usuario_actual: Usuario, pagina: int, tamano_pagina: int
) -> RankingResponse:
    """Arma una página del ranking general y la posición de quien consulta (Tarea 4.1.2, RF-16).

    El ranking incluye solo jugadores habilitados, ordenados por puntaje acumulado.
    `mi_posicion` queda en None si quien consulta no participa del ranking (administrador).
    """
    desplazamiento = (pagina - 1) * tamano_pagina
    usuarios = usuario_repository.listar_ranking(
        db, limite=tamano_pagina, desplazamiento=desplazamiento
    )
    jugadores = [
        _armar_fila(desplazamiento + indice, usuario)
        for indice, usuario in enumerate(usuarios, start=1)
    ]

    mi_posicion = None
    if _participa_del_ranking(usuario_actual):
        posicion = usuario_repository.obtener_posicion_ranking(db, usuario_actual)
        mi_posicion = _armar_fila(posicion, usuario_actual)

    return RankingResponse(
        jugadores=jugadores,
        total_jugadores=usuario_repository.contar_jugadores_ranking(db),
        pagina=pagina,
        tamano_pagina=tamano_pagina,
        mi_posicion=mi_posicion,
    )
