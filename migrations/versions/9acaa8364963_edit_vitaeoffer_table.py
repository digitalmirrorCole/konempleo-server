"""Edit vitaeOffer table

Revision ID: 9acaa8364963
Revises: 7c74d7c02442
Create Date: 2024-12-29 17:32:55.084502

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9acaa8364963'
down_revision: Union[str, None] = '7c74d7c02442'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Alter the `status` column to only allow 'pending' and 'hired'
    op.execute("ALTER TYPE status_enum RENAME TO old_status_enum;")
    op.execute("CREATE TYPE status_enum AS ENUM('pending', 'hired');")
    op.execute("ALTER TABLE \"vitaeOffer\" ALTER COLUMN status TYPE status_enum USING status::text::status_enum;")
    op.execute("DROP TYPE old_status_enum;")

    # Alter the `whatsapp_status` column to allow new values
    op.execute("ALTER TYPE whatsapp_status_enum RENAME TO old_whatsapp_status_enum;")
    op.execute("CREATE TYPE whatsapp_status_enum AS ENUM('notsent', 'pending_response', 'interested', 'not_interested');")
    op.execute("ALTER TABLE \"vitaeOffer\" ALTER COLUMN whatsapp_status TYPE whatsapp_status_enum USING whatsapp_status::text::whatsapp_status_enum;")
    op.execute("DROP TYPE old_whatsapp_status_enum;")

    # Add the `smartdataId` column
    op.add_column('vitaeOffer', sa.Column('smartdataId', sa.Integer(), nullable=True))

    # Add the `comments` column with a max length of 160 characters
    op.add_column('vitaeOffer', sa.Column('comments', sa.String(length=160), nullable=True))


def downgrade():
    # Revert the changes to `status`
    op.execute("ALTER TYPE status_enum RENAME TO new_status_enum;")
    op.execute("CREATE TYPE status_enum AS ENUM('pending', 'accepted', 'rejected');")
    op.execute("ALTER TABLE \"vitaeOffer\" ALTER COLUMN status TYPE status_enum USING status::text::status_enum;")
    op.execute("DROP TYPE new_status_enum;")

    # Revert the changes to `whatsapp_status`
    op.execute("ALTER TYPE whatsapp_status_enum RENAME TO new_whatsapp_status_enum;")
    op.execute("CREATE TYPE whatsapp_status_enum AS ENUM('sent', 'delivered', 'read');")
    op.execute("ALTER TABLE \"vitaeOffer\" ALTER COLUMN whatsapp_status TYPE whatsapp_status_enum USING whatsapp_status::text::whatsapp_status_enum;")
    op.execute("DROP TYPE new_whatsapp_status_enum;")

    # Remove the `smartdataId` column
    op.drop_column('vitaeOffer', 'smartdataId')

    # Remove the `comments` column
    op.drop_column('vitaeOffer', 'comments')