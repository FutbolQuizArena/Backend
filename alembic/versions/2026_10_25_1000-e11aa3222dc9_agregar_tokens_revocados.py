"""Agregar revocación persistente de tokens JWT.

Revision ID: e11aa3222dc9
Revises: d8f92144b20a
"""

from alembic import op
import sqlalchemy as sa

revision = "e11aa3222dc9"
down_revision = "d8f92144b20a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tokens_revocados",
        sa.Column("huella", sa.String(64), primary_key=True),
        sa.Column("expira_en", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_tokens_revocados_expira_en", "tokens_revocados", ["expira_en"])


def downgrade() -> None:
    op.drop_index("ix_tokens_revocados_expira_en", table_name="tokens_revocados")
    op.drop_table("tokens_revocados")
