"""Add contacted and interested columns to offers

Revision ID: bce9245a0b23
Revises: 5177791cc61e
Create Date: 2025-01-26 16:26:51.661104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bce9245a0b23'
down_revision: Union[str, None] = '5177791cc61e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add columns
    op.add_column('offers', sa.Column('contacted', sa.Integer(), server_default='0', nullable=False))
    op.add_column('offers', sa.Column('interested', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    # Remove columns
    op.drop_column('offers', 'contacted')
    op.drop_column('offers', 'interested')