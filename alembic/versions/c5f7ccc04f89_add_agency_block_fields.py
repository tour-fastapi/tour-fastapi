"""add agency block fields

Revision ID: c5f7ccc04f89
Revises: a59c79fff0bd
Create Date: 2025-11-09 16:01:46.299100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f7ccc04f89'
down_revision: Union[str, Sequence[str], None] = 'a59c79fff0bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
