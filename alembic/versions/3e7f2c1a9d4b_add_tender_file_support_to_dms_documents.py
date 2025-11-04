"""Add tender file support to DMS documents

This migration adds fields to support tender files as native DMS documents:
- source_url: Original internet URL for tender files
- is_tender_file: Flag indicating this is from tender scraping
- is_cached: Whether remote file has been cached locally
- cache_status: Caching state (pending, cached, failed)
- cache_error: Error message if caching failed
- scraped_tender_file_id: Reference to ScrapedTenderFile record

This allows tender files to appear as documents within the DMS folder hierarchy
while maintaining smart caching and versioning support.

Revision ID: 3e7f2c1a9d4b
Revises: 9c5d1b8e4a2f
Create Date: 2025-11-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e7f2c1a9d4b'
down_revision = '9c5d1b8e4a2f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add columns for tender file support
    op.add_column('dms_documents', sa.Column('source_url', sa.String(), nullable=True))
    op.add_column('dms_documents', sa.Column('is_tender_file', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('dms_documents', sa.Column('is_cached', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('dms_documents', sa.Column('cache_status', sa.String(), nullable=True, server_default='pending'))
    op.add_column('dms_documents', sa.Column('cache_error', sa.Text(), nullable=True))
    op.add_column('dms_documents', sa.Column('scraped_tender_file_id', sa.UUID(), nullable=True))

    # Step 2: Create indexes for querying tender files
    op.create_index(
        'idx_dms_documents_tender_file',
        'dms_documents',
        ['is_tender_file'],
        unique=False
    )
    op.create_index(
        'idx_dms_documents_cache_status',
        'dms_documents',
        ['cache_status'],
        unique=False
    )
    op.create_index(
        'idx_dms_documents_scraped_tender_file_id',
        'dms_documents',
        ['scraped_tender_file_id'],
        unique=False
    )

    # Step 3: Update storage_provider to allow 'remote' type
    # No SQL needed - column already accepts any string


def downgrade() -> None:
    # Reverse the changes
    op.drop_index('idx_dms_documents_scraped_tender_file_id', table_name='dms_documents')
    op.drop_index('idx_dms_documents_cache_status', table_name='dms_documents')
    op.drop_index('idx_dms_documents_tender_file', table_name='dms_documents')
    op.drop_column('dms_documents', 'scraped_tender_file_id')
    op.drop_column('dms_documents', 'cache_error')
    op.drop_column('dms_documents', 'cache_status')
    op.drop_column('dms_documents', 'is_cached')
    op.drop_column('dms_documents', 'is_tender_file')
    op.drop_column('dms_documents', 'source_url')
