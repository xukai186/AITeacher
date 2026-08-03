"""wrong book explanation cache columns

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-07-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a8b9c0d1e2f3"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wrong_book_items", sa.Column("explanation_text", sa.Text(), nullable=True))
    op.add_column(
        "wrong_book_items",
        sa.Column("explanation_created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wrong_book_items", "explanation_created_at")
    op.drop_column("wrong_book_items", "explanation_text")
