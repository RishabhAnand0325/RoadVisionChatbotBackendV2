"""add bid synopsis extracted values table

Revision ID: f325d6bb53b5
Revises: 8d0e1624c763
Create Date: 2025-11-20 05:45:04.893535

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'f325d6bb53b5'
down_revision: Union[str, Sequence[str], None] = '8d0e1624c763'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create bid_synopsis_extracted_values table
    op.create_table(
        'bid_synopsis_extracted_values',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('value_index', sa.Integer(), nullable=False),
        sa.Column('extracted_value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(
        op.f('ix_bid_synopsis_extracted_values_tender_id'),
        'bid_synopsis_extracted_values',
        ['tender_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_bid_synopsis_extracted_values_user_id'),
        'bid_synopsis_extracted_values',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop bid_synopsis_extracted_values table
    op.drop_index(op.f('ix_bid_synopsis_extracted_values_user_id'), table_name='bid_synopsis_extracted_values')
    op.drop_index(op.f('ix_bid_synopsis_extracted_values_tender_id'), table_name='bid_synopsis_extracted_values')
    op.drop_table('bid_synopsis_extracted_values')
