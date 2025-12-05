"""merge heads

Revision ID: 126b3d082b95
Revises: 3894f112b553, add_bid_synopsis_json
Create Date: 2025-11-18 00:01:44.485499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '126b3d082b95'
down_revision: Union[str, Sequence[str], None] = ('3894f112b553', 'add_bid_synopsis_json')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
