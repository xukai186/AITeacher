"""add study roadmap and generation jobs

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_roadmaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pending_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_user_id"),
    )
    op.create_table(
        "study_roadmap_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("roadmap_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "months_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["roadmap_id"], ["study_roadmaps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("roadmap_id", "version", name="uq_study_roadmap_version"),
    )
    op.create_foreign_key(
        "fk_study_roadmaps_pending_version",
        "study_roadmaps",
        "study_roadmap_versions",
        ["pending_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "roadmap_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("roadmap_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["roadmap_version_id"], ["study_roadmap_versions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_roadmap_generation_jobs_student_user_id",
        "roadmap_generation_jobs",
        ["student_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_roadmap_generation_jobs_student_user_id", table_name="roadmap_generation_jobs")
    op.drop_table("roadmap_generation_jobs")
    op.drop_constraint("fk_study_roadmaps_pending_version", "study_roadmaps", type_="foreignkey")
    op.drop_table("study_roadmap_versions")
    op.drop_table("study_roadmaps")
