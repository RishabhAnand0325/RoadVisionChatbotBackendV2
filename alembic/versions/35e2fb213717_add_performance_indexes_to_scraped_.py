"""add_performance_indexes_to_scraped_tenders

Revision ID: 35e2fb213717
Revises: add_auto_analyze_wishlist
Create Date: 2026-01-06 06:09:46.931845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '35e2fb213717'
down_revision: Union[str, Sequence[str], None] = 'add_auto_analyze_wishlist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add critical indexes to scraped_tenders table for performance optimization."""
    # Index on query_id for fast category filtering
    op.create_index(
        'idx_scraped_tenders_query_id',
        'scraped_tenders',
        ['query_id'],
        unique=False
    )
    
    # Index on tender_no for fast duplicate detection
    op.create_index(
        'idx_scraped_tenders_tender_no',
        'scraped_tenders',
        ['tender_no'],
        unique=False
    )
    
    # Index on publish_date for date range queries
    op.create_index(
        'idx_scraped_tenders_publish_date',
        'scraped_tenders',
        ['publish_date'],
        unique=False
    )
    
    # Composite index for the most common query pattern (query_id + tender_no)
    op.create_index(
        'idx_scraped_tenders_query_tender',
        'scraped_tenders',
        ['query_id', 'tender_no'],
        unique=False
    )


def downgrade() -> None:
    """Remove the performance indexes."""
    op.drop_index('idx_scraped_tenders_query_tender', table_name='scraped_tenders')
    op.drop_index('idx_scraped_tenders_publish_date', table_name='scraped_tenders')
    op.drop_index('idx_scraped_tenders_tender_no', table_name='scraped_tenders')
    op.drop_index('idx_scraped_tenders_query_id', table_name='scraped_tenders')
