"""Update offer enums with ENUM fixes

Revision ID: 278a9688fff7
Revises: bce9245a0b23
Create Date: 2025-01-26 19:52:29.537616
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# Define ENUM types
offer_type_enum = ENUM(
    "Presencial", "Remoto", "Hibrido",
    name="offer_type_enum",
    create_type=True,
)
experience_years_enum = ENUM(
    "sin_experiencia",
    "seis_meses",
    "un_ano",
    "dos_anos",
    "tres_anos",
    "mas_de_tres_anos",
    name="experienceyearsenum",
    create_type=True,
)
education_enum = ENUM(
    "primaria",
    "bachillerato",
    "tecnico",
    "tecnologo",
    "universitario",
    "posgrado",
    name="educationenum",
    create_type=True,
)
shift_enum = ENUM(
    "lv", "ls", "rotativo", "por_definir",
    name="shiftenum",
    create_type=True,
)

# Mappings for updates
experience_mapping = {
    0: "sin_experiencia",
    6: "seis_meses",
    12: "un_ano",
    24: "dos_anos",
    36: "tres_anos",
    999: "mas_de_tres_anos",
}
education_mapping = {
    "none": "primaria",
    "high_school": "bachillerato",
    "bachelor": "universitario",
    "master": "posgrado",
    "doctorate": "posgrado",
}
shift_mapping = {
    "morning": "lv",
    "evening": "ls",
    "night": "rotativo",
}

# Revision identifiers
revision = "278a9688fff7"
down_revision = "bce9245a0b23"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure ENUM types are created in the database
    offer_type_enum.create(op.get_bind(), checkfirst=True)
    experience_years_enum.create(op.get_bind(), checkfirst=True)
    education_enum.create(op.get_bind(), checkfirst=True)
    shift_enum.create(op.get_bind(), checkfirst=True)

    # Update offer_type
    op.execute("""
        UPDATE offers
        SET offer_type = CASE
            WHEN offer_type ILIKE 'Presencial' THEN 'Presencial'
            WHEN offer_type ILIKE 'Remoto' THEN 'Remoto'
            WHEN offer_type ILIKE 'Hibrido' THEN 'Hibrido'
            ELSE NULL
        END
    """)
    op.alter_column(
        "offers",
        "offer_type",
        type_=offer_type_enum,
        existing_type=sa.String(),
        postgresql_using="offer_type::offer_type_enum",
        nullable=True,
    )

    # Update experience_years
    op.add_column(
        "offers", sa.Column("experience_years_new", experience_years_enum, nullable=True)
    )
    for old_value, new_value in experience_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET experience_years_new = '{new_value}'::experienceyearsenum
            WHERE experience_years = {old_value}
        """)
    op.drop_column("offers", "experience_years")
    op.alter_column(
        "offers", "experience_years_new", new_column_name="experience_years"
    )

    # Update education
    op.add_column(
        "offers", sa.Column("ed_required_new", education_enum, nullable=True)
    )
    for old_value, new_value in education_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET ed_required_new = '{new_value}'::educationenum
            WHERE ed_required = '{old_value}'
        """)
    op.drop_column("offers", "ed_required")
    op.alter_column("offers", "ed_required_new", new_column_name="ed_required")

    # Update shift
    op.add_column("offers", sa.Column("shift_new", shift_enum, nullable=True))
    for old_value, new_value in shift_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET shift_new = '{new_value}'::shiftenum
            WHERE shift = '{old_value}'
        """)
    op.drop_column("offers", "shift")
    op.alter_column("offers", "shift_new", new_column_name="shift")


def downgrade():
    # Revert offer_type
    op.alter_column(
        "offers",
        "offer_type",
        type_=sa.String(),
        existing_type=offer_type_enum,
        nullable=True,
    )
    offer_type_enum.drop(op.get_bind(), checkfirst=True)

    # Revert experience_years
    op.add_column(
        "offers", sa.Column("experience_years_old", sa.Integer, nullable=True)
    )
    reverse_experience_mapping = {v: k for k, v in experience_mapping.items()}
    for new_value, old_value in reverse_experience_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET experience_years_old = {old_value}
            WHERE experience_years = '{new_value}'
        """)
    op.drop_column("offers", "experience_years")
    op.alter_column(
        "offers", "experience_years_old", new_column_name="experience_years"
    )
    experience_years_enum.drop(op.get_bind(), checkfirst=True)

    # Revert education
    op.add_column(
        "offers", sa.Column("ed_required_old", sa.String(), nullable=True)
    )
    reverse_education_mapping = {v: k for k, v in education_mapping.items()}
    for new_value, old_value in reverse_education_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET ed_required_old = '{old_value}'
            WHERE ed_required = '{new_value}'
        """)
    op.drop_column("offers", "ed_required")
    op.alter_column(
        "offers", "ed_required_old", new_column_name="ed_required"
    )
    education_enum.drop(op.get_bind(), checkfirst=True)

    # Revert shift
    op.add_column("offers", sa.Column("shift_old", sa.String(), nullable=True))
    reverse_shift_mapping = {v: k for k, v in shift_mapping.items()}
    for new_value, old_value in reverse_shift_mapping.items():
        op.execute(f"""
            UPDATE offers
            SET shift_old = '{old_value}'
            WHERE shift = '{new_value}'
        """)
    op.drop_column("offers", "shift")
    op.alter_column("offers", "shift_old", new_column_name="shift")
    shift_enum.drop(op.get_bind(), checkfirst=True)
