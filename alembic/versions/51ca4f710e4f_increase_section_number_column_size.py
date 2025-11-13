"""increase_section_number_column_size

Revision ID: 51ca4f710e4f
Revises: 7a0c7243c532
Create Date: 2025-11-13 17:37:36.830509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '51ca4f710e4f'
down_revision: Union[str, Sequence[str], None] = '7a0c7243c532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Increase section_number column size from VARCHAR(50) to VARCHAR(200)
    op.alter_column('analysis_rfp_sections', 'section_number',
                    type_=sa.String(200),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert section_number column size from VARCHAR(200) to VARCHAR(50)
    op.alter_column('analysis_rfp_sections', 'section_number',
                    type_=sa.String(50),
                    nullable=True)
