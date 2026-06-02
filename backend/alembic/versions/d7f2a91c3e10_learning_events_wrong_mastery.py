"""learning events and wrong book mastery fields

Revision ID: d7f2a91c3e10
Revises: c4a8e12f0b01
Create Date: 2026-06-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7f2a91c3e10"
down_revision: Union[str, None] = "c4a8e12f0b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_user_id", sa.UUID(), nullable=False),
        sa.Column("subject_code", sa.String(length=40), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("ref_type", sa.String(length=40), nullable=True),
        sa.Column("ref_id", sa.UUID(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_events_student_created", "learning_events", ["student_user_id", "created_at"])

    op.add_column(
        "wrong_book_items",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
    )
    op.add_column(
        "wrong_book_items",
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "wrong_book_items",
        sa.Column("consecutive_correct_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "wrong_book_items",
        sa.Column("first_correct_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "wrong_book_items",
        sa.Column("last_practice_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "wrong_book_items",
        sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wrong_book_items", "mastered_at")
    op.drop_column("wrong_book_items", "last_practice_at")
    op.drop_column("wrong_book_items", "first_correct_at")
    op.drop_column("wrong_book_items", "consecutive_correct_count")
    op.drop_column("wrong_book_items", "wrong_count")
    op.drop_column("wrong_book_items", "status")
    op.drop_index("ix_learning_events_student_created", table_name="learning_events")
    op.drop_table("learning_events")
