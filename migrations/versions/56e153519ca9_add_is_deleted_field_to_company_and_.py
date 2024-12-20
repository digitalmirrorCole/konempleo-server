"""Add is_deleted field to Company and Users

Revision ID: 56e153519ca9
Revises: cdb66cae92be
Create Date: 2024-12-20 14:33:31.415720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '56e153519ca9'
down_revision: Union[str, None] = 'cdb66cae92be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add the is_deleted column with default value false
    op.add_column('company', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('offers', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove the is_deleted column
    op.drop_column('company', 'is_deleted')
    op.drop_column('users', 'is_deleted')
    op.drop_column('offers', 'is_deleted')