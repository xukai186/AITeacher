"""placement question rubric and longer answer keys

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-18 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "placement_questions",
        sa.Column("rubric_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.alter_column(
        "placement_questions",
        "answer_key",
        existing_type=sa.String(length=40),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "placement_questions",
        "answer_key",
        existing_type=sa.Text(),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.drop_column("placement_questions", "rubric_json")
