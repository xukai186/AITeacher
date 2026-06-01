"""add plan review jobs

Revision ID: b681e38deb7d
Revises: 5c835f8f2ee8
Create Date: 2026-06-01 11:11:52.983767

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'b681e38deb7d'
down_revision = '5c835f8f2ee8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_review_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_user_id", sa.UUID(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_user_id",
            "subject_code",
            "target_date",
            "trigger",
            name="uq_plan_review_job_dedup",
        ),
    )


def downgrade() -> None:
    op.drop_table("plan_review_jobs")
