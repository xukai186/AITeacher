# Question Bank Concurrent Exact Dedupe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce exact question-bank dedupe under concurrent writes via a partial unique index on `active`/`pending_review` rows, with migration auto-merge of historical duplicates (soft-delete losers) and `IntegrityError → 409` on create/approve/update.

**Architecture:** Add PostgreSQL partial unique index `uq_qbi_exact_dedupe` on `(scope, COALESCE(org_id, sentinel), q_type, btrim(stem)) WHERE status IN ('active','pending_review')`. Alembic migration merges existing duplicate groups first, then creates the index. `QuestionBankService` keeps `find_exact_duplicate` pre-check and wraps `db.flush()` in `_flush_or_raise_duplicate()` for race-safe 409 responses.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, pytest

**Spec:** `docs/superpowers/specs/2026-08-20-question-bank-concurrent-dedupe-design.md`

## Global Constraints

- Partial unique index applies only to `status IN ('active', 'pending_review')`
- Dedupe key: `scope + org_id + q_type + btrim(stem)` (stem stored stripped)
- `global` scope uses `COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid)` in index
- Historical duplicates: keep winner (`active` > `pending_review` > `created_at DESC` > `id DESC`); losers → `status = deleted`
- Conflict response: HTTP **409**, detail `"exact question bank duplicate"` (unchanged)
- Keep `find_exact_duplicate`, `allow_inactive_duplicate`, soft-delete recreate semantics unchanged
- Keep non-unique `ix_qbi_exact_lookup` index
- No frontend changes
- Python tests: `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest …`

## File map

| File | Responsibility |
|------|----------------|
| `backend/alembic/versions/d3e4f5a6b7c8_question_bank_exact_dedupe_unique.py` | Merge duplicates + create partial unique index |
| `backend/app/models/question_bank.py` | Declare `uq_qbi_exact_dedupe` in `__table_args__` |
| `backend/app/services/question_bank.py` | `_flush_or_raise_duplicate`; wire create/approve/update |
| `backend/tests/conftest.py` | Ensure test DB has partial unique index (like other schema patches) |
| `backend/tests/test_question_bank_service.py` | Concurrent create, approve/update conflict, global dedupe |
| `backend/tests/test_question_bank_exact_dedupe_migration.py` | Migration merge SQL behavior |
| `docs/superpowers/specs/2026-08-20-question-bank-concurrent-dedupe-design.md` | Mark 已实现 when done |

---

### Task 1: Alembic migration — merge duplicates + partial unique index

**Files:**
- Create: `backend/alembic/versions/d3e4f5a6b7c8_question_bank_exact_dedupe_unique.py`

**Interfaces:**
- Consumes: existing table `question_bank_items`, index `ix_qbi_exact_lookup`
- Produces: index `uq_qbi_exact_dedupe`; duplicate `active`/`pending_review` rows merged to single survivor

- [ ] **Step 1: Create migration file**

```python
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
```

- [ ] **Step 2: Run migration on dev DB (optional sanity)**

Run:

```bash
cd /Users/bytedance/cursor/AITeacher/backend
.venv/bin/alembic upgrade head
```

Expected: completes without unique-violation error.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/d3e4f5a6b7c8_question_bank_exact_dedupe_unique.py
git commit -m "feat(question-bank): migration for exact dedupe unique index"
```

---

### Task 2: Model — declare partial unique index

**Files:**
- Modify: `backend/app/models/question_bank.py`

**Interfaces:**
- Consumes: migration from Task 1 (same index name `uq_qbi_exact_dedupe`)
- Produces: SQLAlchemy metadata index used by `create_all` / schema sync

- [ ] **Step 1: Add imports and index to `QuestionBankItem`**

At top of `backend/app/models/question_bank.py`, add `text` to sqlalchemy imports:

```python
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
```

Replace/add in `__table_args__` (keep existing indexes):

```python
_GLOBAL_ORG_SENTINEL = "00000000-0000-0000-0000-000000000000"

__table_args__ = (
    Index(
        "ix_qbi_selection",
        "status",
        "subject_code",
        "scope",
        "org_id",
    ),
    Index(
        "ix_qbi_exact_lookup",
        "scope",
        "org_id",
        "q_type",
        func.btrim(stem),
    ),
    Index(
        "uq_qbi_exact_dedupe",
        "scope",
        func.coalesce(org_id, text(f"'{_GLOBAL_ORG_SENTINEL}'::uuid")),
        "q_type",
        func.btrim(stem),
        unique=True,
        postgresql_where=text("status IN ('active', 'pending_review')"),
    ),
)
```

Note: module-level `_GLOBAL_ORG_SENTINEL` constant above the class is fine.

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/question_bank.py
git commit -m "feat(question-bank): declare partial unique dedupe index on model"
```

---

### Task 3: Test schema sync — ensure index exists in pytest DB

**Files:**
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: index DDL from Task 1
- Produces: test DB with `uq_qbi_exact_dedupe` so service tests hit real constraint

- [ ] **Step 1: Patch `_sync_test_schema` for question bank dedupe index**

Inside `_sync_test_schema`, after question bank table exists, add:

```python
    if "question_bank_items" in insp.get_table_names():
        index_names = {idx["name"] for idx in insp.get_indexes("question_bank_items")}
        if "uq_qbi_exact_dedupe" not in index_names:
            connection.execute(
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
```

- [ ] **Step 2: Verify schema sync**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_bank_service.py::test_create_rejects_exact_duplicate -v
```

Expected: PASS (existing test still green).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: sync question bank dedupe unique index in pytest schema"
```

---

### Task 4: Service — `_flush_or_raise_duplicate` + wire flush sites

**Files:**
- Modify: `backend/app/services/question_bank.py`
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Consumes: PostgreSQL index `uq_qbi_exact_dedupe`
- Produces:
  - `QuestionBankService._flush_or_raise_duplicate(db: Session) -> None`
  - `create` / `approve` / `update` call it instead of bare `db.flush()`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_question_bank_service.py`:

```python
from sqlalchemy.orm import Session, sessionmaker


def test_concurrent_create_second_request_gets_409(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    stem = "Concurrent duplicate stem"

    bind = db_session.get_bind()
    SessionLocal = sessionmaker(bind=bind, future=True, join_transaction_mode="create_savepoint")

    session_a: Session = SessionLocal()
    session_b: Session = SessionLocal()
    try:
        _create(svc, session_a, admin, stem=stem)
        session_a.flush()

        with pytest.raises(HTTPException) as exc:
            _create(svc, session_b, admin, stem=stem)
        assert exc.value.status_code == 409
        assert exc.value.detail == "exact question bank duplicate"
    finally:
        session_a.close()
        session_b.close()


def test_approve_conflicts_with_existing_active_duplicate(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    stem = "Approve conflict stem"
    active = _create(svc, db_session, admin, stem=stem, source_type="admin_manual")
    pending = _create(
        svc,
        db_session,
        admin,
        stem=stem,
        source_type="ai_generated",
    )
    svc.reject(db_session, actor=admin, item_id=pending.id)
    pending = _create(
        svc,
        db_session,
        admin,
        stem=stem,
        source_type="ai_generated",
        allow_inactive_duplicate=True,
    )
    db_session.flush()

    with pytest.raises(HTTPException) as exc:
        svc.approve(db_session, actor=admin, item_id=pending.id)
    assert exc.value.status_code == 409
    assert active.status == "active"


def test_update_stem_conflicts_with_existing_active(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    _create(svc, db_session, admin, stem="Taken stem", source_type="admin_manual")
    pending = _create(
        svc,
        db_session,
        admin,
        stem="Other stem",
        source_type="ai_generated",
    )

    with pytest.raises(HTTPException) as exc:
        svc.update(db_session, actor=admin, item_id=pending.id, stem="Taken stem")
    assert exc.value.status_code == 409


def test_global_duplicate_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    stem = "Global duplicate stem"
    _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        stem=stem,
        source_type="admin_manual",
    )

    with pytest.raises(HTTPException) as exc:
        _create(
            svc,
            db_session,
            admin,
            scope="global",
            org_id=None,
            stem=stem,
            source_type="admin_manual",
        )
    assert exc.value.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  backend/tests/test_question_bank_service.py::test_concurrent_create_second_request_gets_409 \
  backend/tests/test_question_bank_service.py::test_approve_conflicts_with_existing_active_duplicate \
  backend/tests/test_question_bank_service.py::test_update_stem_conflicts_with_existing_active \
  backend/tests/test_question_bank_service.py::test_global_duplicate_rejected \
  -v
```

Expected: concurrent/global may pass via app check; approve/update conflict tests FAIL until `_flush_or_raise_duplicate` on those paths (or all fail if index not wired on create flush).

- [ ] **Step 3: Implement `_flush_or_raise_duplicate` and wire callers**

Add imports at top of `question_bank.py`:

```python
from sqlalchemy.exc import IntegrityError
```

Add module-level constant and helper on the class:

```python
_EXACT_DEDUPE_INDEX = "uq_qbi_exact_dedupe"


@staticmethod
def _flush_or_raise_duplicate(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        orig = getattr(exc, "orig", None)
        constraint = getattr(orig, "constraint_name", None) or getattr(orig, "diag", None)
        constraint_name = constraint.constraint_name if hasattr(constraint, "constraint_name") else constraint
        if constraint_name == _EXACT_DEDUPE_INDEX or (
            isinstance(exc.orig.args[0], str) and _EXACT_DEDUPE_INDEX in exc.orig.args[0]
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "exact question bank duplicate",
            ) from exc
        raise
```

Simpler robust version (prefer this):

```python
@staticmethod
def _flush_or_raise_duplicate(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        message = str(exc.orig) if exc.orig is not None else str(exc)
        if _EXACT_DEDUPE_INDEX in message:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "exact question bank duplicate",
            ) from exc
        raise
```

Replace bare `db.flush()` in:
- `create()` (return path)
- `approve()`
- `update()`

With `self._flush_or_raise_duplicate(db)`.

**Important:** In `create()`, keep the existing `find_exact_duplicate` check before insert; only replace the final flush.

**Rollback note:** On IntegrityError, call `db.rollback()` before raising 409 so the session is usable for error responses in tests/API. Verify this does not break callers that expect the item to remain pending in-session on 409 (callers should not use the returned item on 409 anyway).

- [ ] **Step 4: Run all question bank service tests**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_bank_service.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question_bank.py backend/tests/test_question_bank_service.py
git commit -m "feat(question-bank): enforce concurrent exact dedupe via unique index"
```

---

### Task 5: Migration merge behavior test

**Files:**
- Create: `backend/tests/test_question_bank_exact_dedupe_migration.py`

**Interfaces:**
- Consumes: merge SQL from Task 1 migration
- Produces: confidence that historical duplicates are soft-deleted correctly before index creation

- [ ] **Step 1: Write migration merge test**

```python
import uuid

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
```

- [ ] **Step 2: Run test**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  backend/tests/test_question_bank_exact_dedupe_migration.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_question_bank_exact_dedupe_migration.py
git commit -m "test: question bank dedupe migration merge SQL"
```

---

### Task 6: Final verification + spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-question-bank-concurrent-dedupe-design.md`

- [ ] **Step 1: Run full backend test suite (question bank + assembler regression)**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  backend/tests/test_question_bank_service.py \
  backend/tests/test_question_bank_api.py \
  backend/tests/test_question_bank_exact_dedupe_migration.py \
  backend/tests/test_self_test_assembler.py -v
```

Expected: all PASS.

- [ ] **Step 2: Update spec status**

In `docs/superpowers/specs/2026-08-20-question-bank-concurrent-dedupe-design.md`, change:

```markdown
**状态：** 已实现
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-20-question-bank-concurrent-dedupe-design.md
git commit -m "docs: mark concurrent dedupe spec implemented"
```

---

## Spec coverage checklist

| Spec section | Task |
|--------------|------|
| §3 partial unique index + COALESCE | Task 1, 2 |
| §3.3 keep `ix_qbi_exact_lookup` | Task 1 (no drop) |
| §4 migration merge + index | Task 1, 5 |
| §5.2 IntegrityError on create/approve/update | Task 4 |
| §6 behavior matrix | Task 4 tests |
| §7 regression | Task 6 |
| §8 success criteria | Task 6 |

## Spec → plan traceability

| Spec § | Task |
|--------|------|
| §3 去重键与索引 | 1, 2 |
| §4 迁移 | 1, 5 |
| §5 Service 层 | 4 |
| §6 行为矩阵 | 4 |
| §7 测试要点 | 4, 5, 6 |
| §8 成功标准 | 6 |
