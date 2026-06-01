"""add master plan pending_version_id

Revision ID: c4a8e12f0b01
Revises: b681e38deb7d
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a8e12f0b01"
down_revision: Union[str, None] = "b681e38deb7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "master_plans",
        sa.Column("pending_version_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_master_plans_pending_version",
        "master_plans",
        "master_plan_versions",
        ["pending_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_master_plans_pending_version", "master_plans", type_="foreignkey")
    op.drop_column("master_plans", "pending_version_id")
