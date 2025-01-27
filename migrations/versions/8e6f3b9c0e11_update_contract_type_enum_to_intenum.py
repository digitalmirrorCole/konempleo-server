"""Update contract type enum to intEnum

Revision ID: 8e6f3b9c0e11
Revises: 80de64f43509
Create Date: 2025-01-27 18:06:59.653867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

contract_mapping = {
    "termino_fijo": 1,
    "termino_indefinido": 2,
    "obra_o_labor": 3,
    "prestacion_de_servicios": 4,
    "practicas": 5,
    "freelance": 6,
}

# revision identifiers, used by Alembic.
revision: str = '8e6f3b9c0e11'
down_revision: Union[str, None] = '80de64f43509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Add a new integer column
    op.add_column(
        "offers",
        sa.Column("contract_type_new", sa.Integer, nullable=True),
    )

    # Step 2: Map existing string values to integers, casting enum to TEXT
    for old_value, new_value in contract_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET contract_type_new = {new_value}
            WHERE contract_type::text = '{old_value}'
        """)

    # Step 3: Drop the old enum column
    op.drop_column("offers", "contract_type")

    # Step 4: Rename the new integer column to the original column name
    op.alter_column("offers", "contract_type_new", new_column_name="contract_type")


def downgrade():
    # Reverse map integers back to strings
    reverse_mapping = {v: k for k, v in contract_mapping.items()}

    # Step 1: Recreate the old ENUM type
    old_contract_enum = sa.dialects.postgresql.ENUM(
        "termino_fijo",
        "termino_indefinido",
        "obra_o_labor",
        "prestacion_de_servicios",
        "practicas",
        "freelance",
        name="contract_type_enum",
        create_type=True,
    )
    old_contract_enum.create(op.get_bind(), checkfirst=True)

    # Step 2: Add a new column for the ENUM values
    op.add_column(
        "offers",
        sa.Column("contract_type_old", old_contract_enum, nullable=True),
    )

    # Step 3: Map integers back to strings
    for new_value, old_value in reverse_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET contract_type_old = '{old_value}'
            WHERE contract_type = {new_value}
        """)

    # Step 4: Drop the integer column
    op.drop_column("offers", "contract_type")

    # Step 5: Rename the old column back to the original name
    op.alter_column("offers", "contract_type_old", new_column_name="contract_type")

    # Step 6: Drop the new ENUM type
    op.execute("DROP TYPE IF EXISTS contract_type_enum CASCADE")