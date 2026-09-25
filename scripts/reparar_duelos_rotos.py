"""
Script de reparación puntual: detecta duelos ONLINE que quedaron en un estado
roto por el bug de la race condition (Tarea de corrección) — es decir, duelos
en estado EN_CURSO con un jugador 2 asignado, pero SIN sus 10 preguntas
cargadas (porque la inserción falló a mitad de camino antes de la corrección).

Para esos casos, los vuelve a dejar como PENDIENTE_RIVAL (sin jugador 2),
tal como deberían haber quedado si la inserción hubiera fallado correctamente
con el código ya corregido. Así quedan disponibles de nuevo para emparejar.

Uso: python scripts/reparar_duelos_rotos.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.base_datos import SesionLocal
from app.models.enumeraciones import EstadoPartida, ModalidadDuelo
from app.models.partida import PreguntaPartida
from app.models.partida_duelo import PartidaDuelo


def reparar_duelos_rotos() -> None:
    db = SesionLocal()
    try:
        duelos_en_curso = (
            db.query(PartidaDuelo)
            .filter(
                PartidaDuelo.modalidad == ModalidadDuelo.ONLINE.value,
                PartidaDuelo.estado == EstadoPartida.EN_CURSO,
                PartidaDuelo.jugador2_id.isnot(None),
            )
            .all()
        )

        reparados = 0
        for duelo in duelos_en_curso:
            cantidad_preguntas_jugador2 = (
                db.query(PreguntaPartida)
                .filter(
                    PreguntaPartida.partida_id == duelo.id,
                    PreguntaPartida.numero_jugador == 2,
                )
                .count()
            )

            if cantidad_preguntas_jugador2 == 0:
                print(
                    f"Duelo id={duelo.id}: EN_CURSO con jugador2_id={duelo.jugador2_id} "
                    f"pero sin preguntas del jugador 2. Reparando -> PENDIENTE_RIVAL."
                )
                duelo.jugador2_id = None
                duelo.fecha_emparejamiento = None
                duelo.estado = EstadoPartida.PENDIENTE_RIVAL
                db.add(duelo)
                reparados += 1

        db.commit()
        print(f"\nListo. Duelos reparados: {reparados} de {len(duelos_en_curso)} revisados.")
    finally:
        db.close()


if __name__ == "__main__":
    reparar_duelos_rotos()