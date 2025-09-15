"""manual add auth fields (already applied)

Revision ID: 0a63ce5beab1
Revises: 7b1b1e340403
Create Date: 2025-08-21 19:04:43.477506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a63ce5beab1'
down_revision: Union[str, Sequence[str], None] = '7b1b1e340403'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
