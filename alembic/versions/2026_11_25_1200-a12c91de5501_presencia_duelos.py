"""Persistir presencia y motivo de cierre de duelos online."""

from alembic import op
import sqlalchemy as sa

revision = "a12c91de5501"
down_revision = "f23b48c091aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("partidas_duelo", sa.Column("ultima_presencia_jugador1", sa.DateTime(timezone=True)))
    op.add_column("partidas_duelo", sa.Column("ultima_presencia_jugador2", sa.DateTime(timezone=True)))
    op.add_column("partidas_duelo", sa.Column("motivo_finalizacion", sa.String(40)))
    # Las partidas en curso anteriores al despliegue reciben un minuto de gracia.
    op.execute(sa.text("UPDATE partidas_duelo SET ultima_presencia_jugador1 = CURRENT_TIMESTAMP, "
                       "ultima_presencia_jugador2 = CURRENT_TIMESTAMP WHERE modalidad = 'ONLINE'"))


def downgrade() -> None:
    op.drop_column("partidas_duelo", "motivo_finalizacion")
    op.drop_column("partidas_duelo", "ultima_presencia_jugador2")
    op.drop_column("partidas_duelo", "ultima_presencia_jugador1")
