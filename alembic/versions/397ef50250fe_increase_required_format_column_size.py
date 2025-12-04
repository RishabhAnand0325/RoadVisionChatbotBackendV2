"""increase_required_format_column_size

Revision ID: 397ef50250fe
Revises: 51ca4f710e4f
Create Date: 2025-11-13 17:38:50.463833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '397ef50250fe'
down_revision: Union[str, Sequence[str], None] = '51ca4f710e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Increase required_format column size from VARCHAR(50) to VARCHAR(100)
    op.alter_column('analysis_document_templates', 'required_format',
                    type_=sa.String(100),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert required_format column size from VARCHAR(100) to VARCHAR(50)
    op.alter_column('analysis_document_templates', 'required_format',
                    type_=sa.String(50),
                    nullable=True)
