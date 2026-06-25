"""exam major catalog and student exam profile

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_major_categories",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "exam_majors",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("category_code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("default_english_track", sa.String(length=20), nullable=False),
        sa.Column("default_math_track", sa.String(length=20), nullable=False),
        sa.Column("default_subject_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["category_code"], ["exam_major_categories.code"]),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "student_exam_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("major_category_code", sa.String(length=60), nullable=False),
        sa.Column("major_code", sa.String(length=60), nullable=False),
        sa.Column("english_track", sa.String(length=20), nullable=True),
        sa.Column("math_track", sa.String(length=20), nullable=True),
        sa.Column("subject_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cet_status", sa.String(length=20), nullable=True),
        sa.Column("cet_score", sa.Integer(), nullable=True),
        sa.Column("math_mastery_level", sa.String(length=20), nullable=True),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["major_category_code"], ["exam_major_categories.code"]),
        sa.ForeignKeyConstraint(["major_code"], ["exam_majors.code"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("student_exam_profiles")
    op.drop_table("exam_majors")
    op.drop_table("exam_major_categories")
