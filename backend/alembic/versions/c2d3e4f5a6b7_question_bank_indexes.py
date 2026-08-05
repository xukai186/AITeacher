"""add question bank lookup indexes

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-05 14:30:00.000000

"""
from alembic import op


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_qbi_selection",
        "question_bank_items",
        ["status", "subject_code", "scope", "org_id"],
    )
    op.execute(
        "CREATE INDEX ix_qbi_exact_lookup "
        "ON question_bank_items (scope, org_id, q_type, (btrim(stem)))"
    )


def downgrade() -> None:
    op.drop_index("ix_qbi_exact_lookup", table_name="question_bank_items")
    op.drop_index("ix_qbi_selection", table_name="question_bank_items")
