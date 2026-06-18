"""add past exam paper templates for placement mock papers

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-06-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a1b2c3d4e5f6"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "past_exam_paper_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("syllabus_exam_year", sa.Integer(), nullable=False),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("sections_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_past_exam_paper_templates_subject_syllabus_year",
        "past_exam_paper_templates",
        ["subject_code", "syllabus_exam_year"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_past_exam_paper_templates_subject_syllabus_year",
        table_name="past_exam_paper_templates",
    )
    op.drop_table("past_exam_paper_templates")
