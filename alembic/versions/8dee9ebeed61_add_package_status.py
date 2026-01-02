"""add package status

Revision ID: 8dee9ebeed61
Revises: 
Create Date: 2025-12-30 14:51:02.364208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dee9ebeed61'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "packages",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.create_index("ix_packages_status", "packages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_packages_status", table_name="packages")
    op.drop_column("packages", "status")
