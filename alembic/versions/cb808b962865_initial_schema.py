"""initial schema

Revision ID: cb808b962865
Revises: 5802609933b5
Create Date: 2025-12-20 22:52:50.203665

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb808b962865'
down_revision: Union[str, Sequence[str], None] = '5802609933b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.db import Base  # <-- ADJUST if needed
    import app.db.models    # <-- ADJUST if needed

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.db import Base  # <-- SAME AS ABOVE

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

