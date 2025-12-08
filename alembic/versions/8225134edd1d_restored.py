"""restored missing revision

Revision ID: 8225134edd1d
Revises: add_scraped_at_timestamp
Create Date: 2025-12-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8225134edd1d'
down_revision = 'add_scraped_at_timestamp'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
