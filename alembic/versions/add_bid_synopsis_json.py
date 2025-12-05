"""add bid_synopsis_json to tender_analysis

Revision ID: add_bid_synopsis_json
Revises: f3704f4161e5
Create Date: 2025-11-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_bid_synopsis_json'
down_revision = 'f3704f4161e5'
branch_labels = None
depends_on = None


def upgrade():
    # Add bid_synopsis_json column to tender_analysis table
    op.add_column('tender_analysis', sa.Column('bid_synopsis_json', postgresql.JSON, nullable=True))


def downgrade():
    # Remove bid_synopsis_json column
    op.drop_column('tender_analysis', 'bid_synopsis_json')
