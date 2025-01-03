"""Add background_date column to CVitae

Revision ID: df5da8a82660
Revises: 11f1f8d7f917
Create Date: 2025-01-03 16:14:20.231364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'df5da8a82660'
down_revision: Union[str, None] = '11f1f8d7f917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add background_date column
    op.add_column('cvitae', sa.Column('background_date', sa.Date(), nullable=True))

def downgrade():
    # Remove background_date column
    op.drop_column('cvitae', 'background_date')