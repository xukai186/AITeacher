"""add paper gen jobs

Revision ID: e8f1a2b3c4d5
Revises: d7f2a91c3e10
Create Date: 2026-06-16 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e8f1a2b3c4d5"
down_revision = "d7f2a91c3e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_gen_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_user_id", sa.UUID(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("paper_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("progress_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_id", "purpose", name="uq_paper_gen_job_paper_purpose"),
    )


def downgrade() -> None:
    op.drop_table("paper_gen_jobs")
