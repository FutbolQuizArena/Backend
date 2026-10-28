"""Vincular cada cruce con un único duelo.

No se infieren asociaciones históricas por jugadores: podrían ser de otro torneo.
Los cruces pendientes sin vínculo crearán su propio duelo al iniciarse.
"""

from alembic import op
import sqlalchemy as sa

revision = "f23b48c091aa"
down_revision = "e11aa3222dc9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cruces_torneo") as batch:
        batch.add_column(sa.Column("duelo_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_cruce_duelo", "partidas_duelo", ["duelo_id"], ["id"], ondelete="RESTRICT",
        )
        batch.create_unique_constraint("uq_cruce_duelo", ["duelo_id"])


def downgrade() -> None:
    with op.batch_alter_table("cruces_torneo") as batch:
        batch.drop_constraint("uq_cruce_duelo", type_="unique")
        batch.drop_constraint("fk_cruce_duelo", type_="foreignkey")
        batch.drop_column("duelo_id")
