"""add viewed_at to inquiries

Revision ID: e7129ddbe600
Revises: 0a63ce5beab1
Create Date: 2025-08-27 20:01:34.212320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7129ddbe600'
down_revision: Union[str, Sequence[str], None] = '0a63ce5beab1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
