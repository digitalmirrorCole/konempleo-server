"""Edit vitaeOffer smartdataId Column

Revision ID: f294666a0623
Revises: 9acaa8364963
Create Date: 2025-01-01 22:30:27.571998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f294666a0623'
down_revision: Union[str, None] = '9acaa8364963'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        'vitaeOffer', 
        'smartdataId',
        existing_type=sa.Integer(),
        type_=sa.String(),  # Change to String
        existing_nullable=True  # Ensure it remains nullable if needed
    )

def downgrade():
    op.alter_column(
        'vitaeOffer', 
        'smartdataId',
        existing_type=sa.String(),
        type_=sa.Integer(),  # Revert to Integer
        existing_nullable=True
    )