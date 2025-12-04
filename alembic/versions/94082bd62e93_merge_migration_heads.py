"""merge migration heads

Revision ID: 94082bd62e93
Revises: 11e2442262fc, f325d6bb53b5
Create Date: 2025-11-24 10:20:58.189703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '94082bd62e93'
down_revision: Union[str, Sequence[str], None] = ('11e2442262fc', 'f325d6bb53b5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
