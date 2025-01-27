"""Update contract type enum

Revision ID: eb8e448b98e6
Revises: 278a9688fff7
Create Date: 2025-01-27 07:22:33.216254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# Define the new ENUM type
new_contract_enum = ENUM(
    "Término Fijo",
    "Término Indefinido",
    "Obra o Labor",
    "Prestación de Servicios",
    "Prácticas",
    "Freelance",
    name="contract_type_enum",
    create_type=True,  # Ensure the type is created in the database
)

# Map old string values to new string values
contract_mapping = {
    "full_time": "Término Fijo",       # full_time -> Término Fijo
    "part_time": "Término Indefinido" # part_time -> Término Indefinido
}

# revision identifiers, used by Alembic.
revision: str = 'eb8e448b98e6'
down_revision: Union[str, None] = '278a9688fff7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Step 1: Add a new temporary column for the updated ENUM values
    op.add_column(
        "offers", sa.Column("contract_type_new", sa.String(), nullable=True),
    )

    # Step 2: Update the new column with mapped values from the old ENUM column
    for old_value, new_value in contract_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET contract_type_new = '{new_value}'
            WHERE contract_type = '{old_value}'
        """)

    # Step 3: Drop the old column
    op.drop_column("offers", "contract_type")

    # Step 4: Drop the old ENUM type
    op.execute("DROP TYPE IF EXISTS contract_type_enum CASCADE")

    # Step 5: Create the new ENUM type
    new_contract_enum.create(op.get_bind())

    # Step 6: Add the new column with the updated ENUM type
    op.add_column(
        "offers", sa.Column("contract_type", new_contract_enum, nullable=True),
    )

    # Step 7: Update the new ENUM column with values from the temporary column
    op.execute("""
        UPDATE offers
        SET contract_type = contract_type_new::contract_type_enum
    """)

    # Step 8: Drop the temporary column
    op.drop_column("offers", "contract_type_new")


def downgrade():
    # Step 1: Add a temporary column for the old ENUM values
    old_contract_enum = ENUM(
        "full_time",
        "part_time",
        name="contract_type_enum",
        create_type=True,
    )
    old_contract_enum.create(op.get_bind())

    op.add_column(
        "offers", sa.Column("contract_type_old", old_contract_enum, nullable=True),
    )

    # Step 2: Reverse map the new ENUM values back to the old ENUM values
    reverse_contract_mapping = {v: k for k, v in contract_mapping.items()}
    for new_value, old_value in reverse_contract_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET contract_type_old = '{old_value}'
            WHERE contract_type = '{new_value}'
        """)

    # Step 3: Drop the new column
    op.drop_column("offers", "contract_type")

    # Step 4: Rename the old column back to the original column name
    op.alter_column("offers", "contract_type_old", new_column_name="contract_type")

    # Step 5: Drop the new ENUM type
    op.execute("DROP TYPE IF EXISTS contract_type_enum CASCADE")
