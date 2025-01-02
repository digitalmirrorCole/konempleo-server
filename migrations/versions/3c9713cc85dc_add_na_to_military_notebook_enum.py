"""Add NA to military_notebook_enum

Revision ID: 3c9713cc85dc
Revises: f294666a0623
Create Date: 2025-01-02 09:26:44.953844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c9713cc85dc'
down_revision: Union[str, None] = 'f294666a0623'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Add the 'NA' value to the military_notebook_enum
    op.execute("""
        ALTER TYPE military_notebook_enum ADD VALUE 'NA';
    """)

def downgrade():
    # Downgrade logic: Revert the addition of 'NA'
    # Downgrading enums is more complex because PostgreSQL doesn't allow removing values directly.
    # One approach is to create a new enum type without the 'NA' value, migrate the column, and drop the old enum type.
    op.execute("""
        CREATE TYPE military_notebook_enum_old AS ENUM ('yes', 'no');
    """)
    op.execute("""
        ALTER TABLE offers ALTER COLUMN military_notebook TYPE military_notebook_enum_old USING military_notebook::text::military_notebook_enum_old;
    """)
    op.execute("""
        DROP TYPE military_notebook_enum;
    """)
    op.execute("""
        ALTER TYPE military_notebook_enum_old RENAME TO military_notebook_enum;
    """)
