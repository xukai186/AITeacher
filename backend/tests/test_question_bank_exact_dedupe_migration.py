from sqlalchemy import text

from app.models import QuestionBankItem, UserRole
from tests.factories import make_org, make_user


def _insert_raw(db_session, *, admin, scope, org_id, stem, status, source_type="admin_manual"):
    item = QuestionBankItem(
        scope=scope,
        org_id=org_id,
        subject_code="english",
        knowledge_node_id=None,
        q_type="single_choice",
        stem=stem,
        choices_json=[{"key": "A", "text": "1"}],
        answer_key="A",
        source_type=source_type,
        status=status,
        created_by=admin.id,
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_migration_merge_keeps_active_over_pending(db_session):
    org = make_org(db_session)
    admin = make_user(db_session, org, UserRole.org_admin)
    stem = "Migration merge stem"

    db_session.execute(text("DROP INDEX IF EXISTS uq_qbi_exact_dedupe"))

    pending = _insert_raw(
        db_session,
        admin=admin,
        scope="org",
        org_id=org.id,
        stem=stem,
        status="pending_review",
        source_type="ai_generated",
    )
    active = _insert_raw(
        db_session,
        admin=admin,
        scope="org",
        org_id=org.id,
        stem=stem,
        status="active",
        source_type="admin_manual",
    )

    db_session.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            scope,
                            COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
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
    )
    db_session.expire_all()

    refreshed_active = db_session.get(QuestionBankItem, active.id)
    refreshed_pending = db_session.get(QuestionBankItem, pending.id)
    assert refreshed_active.status == "active"
    assert refreshed_pending.status == "deleted"

    db_session.execute(
        text(
            """
            CREATE UNIQUE INDEX uq_qbi_exact_dedupe
            ON question_bank_items (
                scope,
                COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
                q_type,
                (btrim(stem))
            )
            WHERE status IN ('active', 'pending_review')
            """
        )
    )
