"""add_corrigendum_updated_to_tender_action_enum

Revision ID: 11e2442262fc
Revises: 8510f89a1838
Create Date: 2025-11-19 18:21:27.652765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '11e2442262fc'
down_revision: Union[str, Sequence[str], None] = '8510f89a1838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'corrigendum_updated' to the TenderActionEnum
    op.execute("ALTER TYPE tenderactionenum ADD VALUE IF NOT EXISTS 'corrigendum_updated'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # You would need to recreate the enum type if downgrade is needed
    pass
