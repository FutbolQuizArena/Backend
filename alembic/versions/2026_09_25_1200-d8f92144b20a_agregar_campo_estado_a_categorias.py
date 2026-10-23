"""agregar_campo_estado_a_categorias

Revision ID: d8f92144b20a
Revises: c4e815b3e21a
Create Date: 2026-09-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f92144b20a'
down_revision: Union[str, None] = 'c4e815b3e21a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear tipo ENUM en Postgres si no existe
    estado_categoria_enum = sa.Enum('ACTIVA', 'BORRADOR', name='estado_categoria_enum')
    estado_categoria_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('categorias', sa.Column('estado', estado_categoria_enum, server_default='ACTIVA', nullable=False))


def downgrade() -> None:
    op.drop_column('categorias', 'estado')
    sa.Enum(name='estado_categoria_enum').drop(op.get_bind(), checkfirst=True)
