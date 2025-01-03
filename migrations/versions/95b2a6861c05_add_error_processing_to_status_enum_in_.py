"""Add error_processing to status_enum in VitaeOffer

Revision ID: 95b2a6861c05
Revises: 3c9713cc85dc
Create Date: 2025-01-02 17:35:01.023779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = '95b2a6861c05'
down_revision: Union[str, None] = '3c9713cc85dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Update the enum type
status_enum = ENUM('pending', 'hired', 'error_processing', 'rejected', name='status_enum', create_type=False)

def upgrade():
    # Add new values to the enum type
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE status_enum ADD VALUE 'error_processing'")
        op.execute("ALTER TYPE status_enum ADD VALUE 'rejected'")

def downgrade():
    pass