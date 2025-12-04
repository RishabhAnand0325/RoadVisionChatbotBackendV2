"""add_email_template_hash_table

Revision ID: 87eedb7eb8b1
Revises: 94082bd62e93
Create Date: 2025-11-29 08:42:18.206846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '87eedb7eb8b1'
down_revision: Union[str, Sequence[str], None] = '94082bd62e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create email_template_hashes table
    op.create_table(
        'email_template_hashes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_hash', sa.String(), nullable=False),
        sa.Column('email_sender', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_validated_at', sa.DateTime(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # Create unique index on template_hash
    op.create_index(
        op.f('ix_email_template_hashes_template_hash'),
        'email_template_hashes',
        ['template_hash'],
        unique=True
    )
    # Create index on email_sender for faster lookups
    op.create_index(
        op.f('ix_email_template_hashes_email_sender'),
        'email_template_hashes',
        ['email_sender'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_email_template_hashes_email_sender'), table_name='email_template_hashes')
    op.drop_index(op.f('ix_email_template_hashes_template_hash'), table_name='email_template_hashes')
    # Drop table
    op.drop_table('email_template_hashes')
