"""add track columns to past exam paper templates

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-24 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "past_exam_paper_templates",
        sa.Column("english_track", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "past_exam_paper_templates",
        sa.Column("math_track", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("past_exam_paper_templates", "math_track")
    op.drop_column("past_exam_paper_templates", "english_track")
