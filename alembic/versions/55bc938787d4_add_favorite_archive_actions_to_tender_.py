"""add_favorite_archive_actions_to_tender_action_enum

Revision ID: 55bc938787d4
Revises: 87eedb7eb8b1
Create Date: 2025-11-29 11:08:58.751601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '55bc938787d4'
down_revision: Union[str, Sequence[str], None] = '87eedb7eb8b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum values to TenderActionEnum for user-specific favorite and archive actions
    op.execute("ALTER TYPE tenderactionenum ADD VALUE IF NOT EXISTS 'favorited'")
    op.execute("ALTER TYPE tenderactionenum ADD VALUE IF NOT EXISTS 'unfavorited'")
    op.execute("ALTER TYPE tenderactionenum ADD VALUE IF NOT EXISTS 'archived'")
    op.execute("ALTER TYPE tenderactionenum ADD VALUE IF NOT EXISTS 'unarchived'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # You would need to recreate the enum type if downgrade is needed
    pass
