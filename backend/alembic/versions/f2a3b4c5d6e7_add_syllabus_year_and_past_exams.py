"""add syllabus exam_year and past exam questions

Revision ID: f2a3b4c5d6e7
Revises: e8f1a2b3c4d5
Create Date: 2026-06-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2a3b4c5d6e7"
down_revision = "e8f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("syllabus_nodes", sa.Column("exam_year", sa.Integer(), nullable=True))
    op.create_index("ix_syllabus_nodes_subject_exam_year", "syllabus_nodes", ["subject_code", "exam_year"])

    op.create_table(
        "past_exam_questions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=False),
        sa.Column("source_year", sa.Integer(), nullable=False),
        sa.Column("syllabus_exam_year", sa.Integer(), nullable=False),
        sa.Column("knowledge_node_id", sa.UUID(), nullable=True),
        sa.Column("q_type", sa.String(length=40), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("choices_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("answer_key", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_node_id"], ["syllabus_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_past_exam_questions_subject_syllabus_year",
        "past_exam_questions",
        ["subject_code", "syllabus_exam_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_past_exam_questions_subject_syllabus_year", table_name="past_exam_questions")
    op.drop_table("past_exam_questions")
    op.drop_index("ix_syllabus_nodes_subject_exam_year", table_name="syllabus_nodes")
    op.drop_column("syllabus_nodes", "exam_year")
