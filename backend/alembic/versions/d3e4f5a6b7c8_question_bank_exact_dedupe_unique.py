"""question bank partial unique index for exact dedupe

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-20 12:00:00.000000

"""
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

_SENTINEL = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    op.execute(
        f"""
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        scope,
                        COALESCE(org_id, '{_SENTINEL}'::uuid),
                        q_type,
                        btrim(stem)
                    ORDER BY
                        CASE status
                            WHEN 'active' THEN 0
                            WHEN 'pending_review' THEN 1
                            ELSE 2
                        END,
                        created_at DESC,
                        id DESC
                ) AS rn
            FROM question_bank_items
            WHERE status IN ('active', 'pending_review')
        )
        UPDATE question_bank_items AS q
        SET status = 'deleted', updated_at = now()
        FROM ranked
        WHERE q.id = ranked.id
          AND ranked.rn > 1
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_qbi_exact_dedupe
        ON question_bank_items (
            scope,
            COALESCE(org_id, '{_SENTINEL}'::uuid),
            q_type,
            (btrim(stem))
        )
        WHERE status IN ('active', 'pending_review')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_qbi_exact_dedupe")
