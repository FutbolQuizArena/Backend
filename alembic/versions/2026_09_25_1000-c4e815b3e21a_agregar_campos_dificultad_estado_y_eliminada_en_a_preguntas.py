"""agregar_campos_dificultad_estado_y_eliminada_en_a_preguntas

Revision ID: c4e815b3e21a
Revises: 1e42ce65396a
Create Date: 2026-09-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e815b3e21a'
down_revision: Union[str, None] = '1e42ce65396a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear tipo ENUM en Postgres si no existe
    estado_pregunta_enum = sa.Enum('ACTIVA', 'BORRADOR', name='estado_pregunta_enum')
    estado_pregunta_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('preguntas', sa.Column('dificultad', sa.String(length=50), server_default='Media', nullable=True))
    op.add_column('preguntas', sa.Column('estado', estado_pregunta_enum, server_default='ACTIVA', nullable=False))
    op.add_column('preguntas', sa.Column('eliminada_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('preguntas', 'eliminada_en')
    op.drop_column('preguntas', 'estado')
    op.drop_column('preguntas', 'dificultad')
    sa.Enum(name='estado_pregunta_enum').drop(op.get_bind(), checkfirst=True)
