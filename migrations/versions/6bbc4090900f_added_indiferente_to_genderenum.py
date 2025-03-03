"""Added indiferente to genderEnum

Revision ID: 6bbc4090900f
Revises: 8e6f3b9c0e11
Create Date: 2025-03-03 16:01:37.752235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6bbc4090900f'
down_revision: Union[str, None] = '8e6f3b9c0e11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define new ENUM type
new_gender_enum = postgresql.ENUM("male", "female", "other", "indiferente", name="genderenum", create_type=False)
old_gender_enum = postgresql.ENUM("male", "female", "other", name="genderenum", create_type=False)

def upgrade():
    # Update ENUM type in PostgreSQL
    op.execute("ALTER TYPE gender_enum ADD VALUE 'indiferente'")

def downgrade():
    # Downgrade logic (not directly possible for ENUM modifications in PostgreSQL)
    op.execute("ALTER TABLE offers ALTER COLUMN gender DROP DEFAULT")  # Drop default first if exists
    op.execute("ALTER TYPE gender_enum RENAME TO gender_enum_old")
    op.execute("CREATE TYPE gender_enum AS ENUM ('male', 'female', 'other')")
    op.execute("ALTER TABLE offers ALTER COLUMN gender TYPE gender_enum USING gender::text::gender_enum")
    op.execute("DROP TYPE gender_enum_old")