"""add_document_changes_and_actions_history_to_scraped_tenders

Revision ID: 7ab253e2428e
Revises: fdf673f3c60e
Create Date: 2026-01-12 11:50:22.926753

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '7ab253e2428e'
down_revision: Union[str, Sequence[str], None] = 'fdf673f3c60e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add document_changes_json and actions_history_json columns to scraped_tenders table."""
    # Add JSON columns to store scraped document changes and actions history
    op.add_column('scraped_tenders', sa.Column('document_changes_json', sa.JSON(), nullable=True))
    op.add_column('scraped_tenders', sa.Column('actions_history_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove document_changes_json and actions_history_json columns from scraped_tenders table."""
    op.drop_column('scraped_tenders', 'actions_history_json')
    op.drop_column('scraped_tenders', 'document_changes_json')
