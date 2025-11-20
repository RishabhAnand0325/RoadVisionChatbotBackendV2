"""add bid synopsis requirements and ceigall data tables

Revision ID: 8d0e1624c763
Revises: 8510f89a1838
Create Date: 2025-11-20 05:40:47.071346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '8d0e1624c763'
down_revision: Union[str, Sequence[str], None] = '8510f89a1838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create bid_synopsis_requirements table
    op.create_table(
        'bid_synopsis_requirements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('requirement_index', sa.Integer(), nullable=False),
        sa.Column('original_requirement', sa.Text(), nullable=True),
        sa.Column('edited_requirement', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(
        op.f('ix_bid_synopsis_requirements_tender_id'),
        'bid_synopsis_requirements',
        ['tender_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_bid_synopsis_requirements_user_id'),
        'bid_synopsis_requirements',
        ['user_id'],
        unique=False
    )

    # Create bid_synopsis_ceigall_data table
    op.create_table(
        'bid_synopsis_ceigall_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tender_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('data_index', sa.Integer(), nullable=False),
        sa.Column('ceigall_value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(
        op.f('ix_bid_synopsis_ceigall_data_tender_id'),
        'bid_synopsis_ceigall_data',
        ['tender_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_bid_synopsis_ceigall_data_user_id'),
        'bid_synopsis_ceigall_data',
        ['user_id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop bid_synopsis_ceigall_data table
    op.drop_index(op.f('ix_bid_synopsis_ceigall_data_user_id'), table_name='bid_synopsis_ceigall_data')
    op.drop_index(op.f('ix_bid_synopsis_ceigall_data_tender_id'), table_name='bid_synopsis_ceigall_data')
    op.drop_table('bid_synopsis_ceigall_data')

    # Drop bid_synopsis_requirements table
    op.drop_index(op.f('ix_bid_synopsis_requirements_user_id'), table_name='bid_synopsis_requirements')
    op.drop_index(op.f('ix_bid_synopsis_requirements_tender_id'), table_name='bid_synopsis_requirements')
    op.drop_table('bid_synopsis_requirements')
