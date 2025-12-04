"""Add scraped_at timestamp to ScrapedTender for corrigendum tracking

Revision ID: add_scraped_at_timestamp
Revises: 55bc938787d4
Create Date: 2025-12-03

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'add_scraped_at_timestamp'
down_revision = '55bc938787d4'
branch_labels = None
depends_on = None


def upgrade():
    # Add scraped_at column to scraped_tenders table
    op.add_column('scraped_tenders', sa.Column('scraped_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
    
    # Create index on scraped_at for efficient querying
    op.create_index('idx_scraped_at', 'scraped_tenders', ['scraped_at'])


def downgrade():
    # Drop index
    op.drop_index('idx_scraped_at', table_name='scraped_tenders')
    
    # Drop column
    op.drop_column('scraped_tenders', 'scraped_at')
