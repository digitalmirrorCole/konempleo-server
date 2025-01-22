"""Add created_date and modified_date to Offer and VitaeOffer

Revision ID: 5177791cc61e
Revises: df5da8a82660
Create Date: 2025-01-22 10:13:16.171171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5177791cc61e'
down_revision: Union[str, None] = 'df5da8a82660'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add new columns to 'offers'
    op.add_column('offers', sa.Column('created_date', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('offers', sa.Column('modified_date', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False))
    
    # Add new columns to 'vitaeOffer'
    op.add_column('vitaeOffer', sa.Column('created_date', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    op.add_column('vitaeOffer', sa.Column('modified_date', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False))
    
    # Ensure default values for existing records in 'offers'
    op.execute("UPDATE offers SET created_date = NOW(), modified_date = NOW() WHERE created_date IS NULL")
    
    # Ensure default values for existing records in 'vitaeOffer'
    op.execute('UPDATE "vitaeOffer" SET created_date = NOW(), modified_date = NOW() WHERE created_date IS NULL')

def downgrade():
    # Drop the added columns from 'offers'
    op.drop_column('offers', 'created_date')
    op.drop_column('offers', 'modified_date')
    
    # Drop the added columns from 'vitaeOffer'
    op.drop_column('vitaeOffer', 'created_date')
    op.drop_column('vitaeOffer', 'modified_date')