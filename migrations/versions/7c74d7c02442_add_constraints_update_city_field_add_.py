"""Add constraints. Update city field. Add Active field to offer

Revision ID: 7c74d7c02442
Revises: 56e153519ca9
Create Date: 2024-12-27 11:43:44.114579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c74d7c02442'
down_revision: Union[str, None] = '56e153519ca9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add the 'active' column with a default value of True
    op.add_column('offers', sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    
    # Remove the 'whatsapp_message' column
    op.drop_column('offers', 'whatsapp_message')

    # Change the type of the 'city' column from Integer to String
    with op.batch_alter_table('offers', schema=None) as batch_op:
        batch_op.alter_column('city',
                              existing_type=sa.Integer(),
                              type_=sa.String(),
                              existing_nullable=True)

    # Add a unique constraint on the 'email' column of the 'users' table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_users_email', ['email'])

def downgrade():
    # Revert the 'active' column addition
    op.drop_column('offers', 'active')
    
    # Revert the removal of 'whatsapp_message' column
    op.add_column('offers', sa.Column('whatsapp_message', sa.String(), nullable=True))

    # Revert the 'city' column type back to Integer
    with op.batch_alter_table('offers', schema=None) as batch_op:
        batch_op.alter_column('city',
                              existing_type=sa.String(),
                              type_=sa.Integer(),
                              existing_nullable=True)

    # Remove the unique constraint on the 'email' column of the 'users' table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_email', type_='unique')
