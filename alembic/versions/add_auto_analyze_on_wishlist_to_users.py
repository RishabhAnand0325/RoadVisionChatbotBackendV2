"""add_auto_analyze_on_wishlist_to_users

Revision ID: add_auto_analyze_wishlist
Revises: add_scraped_at_timestamp
Create Date: 2025-12-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_auto_analyze_wishlist'
down_revision: Union[str, Sequence[str], None] = '8225134edd1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add auto_analyze_on_wishlist column to users table with default value True
    op.add_column('users', sa.Column('auto_analyze_on_wishlist', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the column
    op.drop_column('users', 'auto_analyze_on_wishlist')
