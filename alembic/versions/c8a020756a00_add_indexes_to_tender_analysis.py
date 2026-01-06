"""add_indexes_to_tender_analysis

Revision ID: c8a020756a00
Revises: 35e2fb213717
Create Date: 2026-01-06 06:14:47.151153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'c8a020756a00'
down_revision: Union[str, Sequence[str], None] = '35e2fb213717'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes to tender_analysis and tender_wishlist tables for performance."""
    # Index on tender_id for fast lookups
    op.create_index(
        'idx_tender_analysis_tender_id',
        'tender_analysis',
        ['tender_id'],
        unique=False
    )
    
    # Index on tender_ref_number for wishlist lookups
    op.create_index(
        'idx_tender_wishlist_tender_ref',
        'tender_wishlist',
        ['tender_ref_number'],
        unique=False
    )
    
    # Index on tdr for scraped tenders lookup
    op.execute('CREATE INDEX IF NOT EXISTS idx_scraped_tenders_tdr ON scraped_tenders(tdr)')


def downgrade() -> None:
    """Remove the indexes."""
    op.drop_index('idx_tender_wishlist_tender_ref', table_name='tender_wishlist')
    op.drop_index('idx_tender_analysis_tender_id', table_name='tender_analysis')
    op.execute('DROP INDEX IF EXISTS idx_scraped_tenders_tdr')
