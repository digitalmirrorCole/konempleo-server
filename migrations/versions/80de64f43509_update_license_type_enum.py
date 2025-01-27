"""Update license type enum

Revision ID: 80de64f43509
Revises: eb8e448b98e6
Create Date: 2025-01-27 08:05:12.500422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, ARRAY

# revision identifiers, used by Alembic.
revision: str = '80de64f43509'
down_revision: Union[str, None] = 'eb8e448b98e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Drop the old column
    op.drop_column("offers", "license")

    # Step 2: Add a new column as an array of strings with a default value
    op.add_column(
        "offers",
        sa.Column(
            "license",
            ARRAY(sa.String),
            nullable=False,
            server_default="{'No Aplica'}",  # Default value for the new column
        ),
    )

