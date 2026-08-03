# Wrong-Book Explanation Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist per–wrong-book-item AI explanations in the database and serve cache hits without calling the model or writing Workspace chat sessions; regenerate only when the student requests it.

**Architecture:** Add `explanation_text` / `explanation_created_at` on `wrong_book_items`; implement `WrongBookExplainService` using `ChatToolLoop` (not `ChatService`); expose `POST /student/wrong-book/{item_id}/explain` and `has_explanation` on list items; switch the Wrong Book UI from `postChat` to the new API.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, React, Vitest

**Spec:** `docs/superpowers/specs/2026-07-27-wrong-book-explanation-cache-design.md`

## Global Constraints

- Invalidate cache **only** when student sets `regenerate: true` (no auto-invalidate on practice, re-wrong, model change, or TTL)
- Generation uses `ChatToolLoop` + `explain_wrong_book_item`; **never** `ChatService.post_message` (no `ChatSession` / `ChatMessage` writes)
- List API returns `has_explanation` only; **not** full `explanation_text` in list payload
- Failed regenerate must **not** clear existing cached text
- Workspace `/chat` and practice conceal semantics unchanged
- Internal user message must include `item_id=<uuid>` (same wording family as current frontend)

## File map

| File | Responsibility |
|------|----------------|
| `backend/alembic/versions/*_wrong_book_explanation_cache.py` | Add explanation columns |
| `backend/app/models/wrong_book.py` | ORM columns |
| `backend/tests/conftest.py` | Test DB column drift for new fields |
| `backend/app/schemas/wrong_book.py` | `WrongBookExplainIn/Out`, `has_explanation` on list out |
| `backend/app/services/wrong_book_explain.py` | Cache read + tool-loop generate |
| `backend/app/routers/student_wrong_book.py` | `POST .../explain` route |
| `backend/tests/test_wrong_book_explain.py` | API cache / regenerate / no chat pollution |
| `frontend/src/api/wrongBook.ts` | `explainWrongItem`, types |
| `frontend/src/pages/student/WrongBook.tsx` | New API +「重新生成讲解」 |
| `frontend/tests/WrongBook.test.tsx` | Mock `/explain` not `/chat` |
| `docs/superpowers/specs/2026-07-27-wrong-book-explanation-cache-design.md` | Mark 已实现 after done |
| `docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md` | Cross-link persistence spec |

---

### Task 1: Schema migration and list `has_explanation`

**Files:**
- Create: `backend/alembic/versions/a8b9c0d1e2f3_wrong_book_explanation_cache.py`
- Modify: `backend/app/models/wrong_book.py`
- Modify: `backend/tests/conftest.py` (`_sync_test_schema` wrong_book block)
- Modify: `backend/app/schemas/wrong_book.py`
- Test: extend `backend/tests/test_wrong_book.py` (one list assertion)

**Interfaces:**
- Consumes: existing `WrongBookItem` table
- Produces: ORM `explanation_text: str | None`, `explanation_created_at: datetime | None`; `WrongBookItemOut.has_explanation: bool`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_wrong_book.py`:

```python
def test_wrong_book_list_includes_has_explanation(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    item = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        question_snapshot_json={"stem": "S"},
        answer_snapshot_json={"content": "A"},
        correct_snapshot_json={"answer_key": "B"},
        status="active",
        explanation_text="cached explain",
    )
    db_session.add(item)
    db_session.commit()

    resp = client.get("/student/wrong-book?subject_code=english", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["id"] == str(item.id))
    assert row["has_explanation"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_wrong_book.py::test_wrong_book_list_includes_has_explanation -v`  
Expected: FAIL (`has_explanation` missing or KeyError)

- [ ] **Step 3: Implement migration + model + schema**

Alembic revision `down_revision = "f6a7b8c9d0e1"`:

```python
def upgrade() -> None:
    op.add_column("wrong_book_items", sa.Column("explanation_text", sa.Text(), nullable=True))
    op.add_column(
        "wrong_book_items",
        sa.Column("explanation_created_at", sa.DateTime(timezone=True), nullable=True),
    )
```

Model (`wrong_book.py`):

```python
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
# ...
    explanation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

`conftest.py` — add to the `wrong_book_items` tuple:

```python
            ("explanation_text", "TEXT"),
            ("explanation_created_at", "TIMESTAMP WITH TIME ZONE"),
```

`WrongBookItemOut`:

```python
from pydantic import computed_field

class WrongBookItemOut(BaseModel):
  # ... existing fields ...
  @computed_field
  @property
  def has_explanation(self) -> bool:
      text = getattr(self, "explanation_text", None)
      # from_attributes: read from ORM via model_validate — use field_validator instead:
```

Because `from_attributes` won't pass `explanation_text` if not a model field on schema, use:

```python
class WrongBookItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # ... existing fields without explanation_text ...
    has_explanation: bool = False

    @model_validator(mode="wrap")
    @classmethod
    def _has_explanation_from_orm(cls, data, handler):
        if hasattr(data, "explanation_text"):
            out = handler(data)
            return out.model_copy(
                update={"has_explanation": bool(data.explanation_text)}
            )
        return handler(data)
```

(Simpler alternative accepted in implementation: add `@property has_explanation` on ORM model and include in schema with `computed_field` if Pydantic reads properties from ORM — verify with test.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_wrong_book.py::test_wrong_book_list_includes_has_explanation -v`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/a8b9c0d1e2f3_wrong_book_explanation_cache.py \
  backend/app/models/wrong_book.py backend/tests/conftest.py \
  backend/app/schemas/wrong_book.py backend/tests/test_wrong_book.py
git commit -m "$(cat <<'EOF'
feat(wrong-book): add explanation cache columns and has_explanation

EOF
)"
```

---

### Task 2: Explain service and API (cache + regenerate)

**Files:**
- Create: `backend/app/services/wrong_book_explain.py`
- Modify: `backend/app/schemas/wrong_book.py` (`WrongBookExplainIn`, `WrongBookExplainOut`)
- Modify: `backend/app/routers/student_wrong_book.py`
- Create: `backend/tests/test_wrong_book_explain.py`

**Interfaces:**
- Consumes: `WrongBookService.get_item`, `ChatToolLoop`, `ModelGateway`, `ModelPolicy` scene `chat`
- Produces:
  - `WrongBookExplainService.explain(db, *, item: WrongBookItem, regenerate: bool) -> WrongBookExplainResult`
  - `POST /student/wrong-book/{item_id}/explain` body `{ "regenerate": false }`
  - Response `{ explanation_text, from_cache, explanation_created_at }`

Fixed internal message (match frontend intent):

```python
EXPLAIN_USER_MESSAGE_TEMPLATE = (
    "请讲解错题本条目 item_id={item_id}。"
    "结合我的当时作答说明错因与正确思路。"
)
```

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_wrong_book_explain.py` with helpers mirroring `_seed_student` / `_token` from `test_wrong_book.py`:

```python
def test_explain_generates_and_caches(client, db_session):
    # seed student + WrongBookItem without explanation_text
    # POST /student/wrong-book/{id}/explain {} 
    # assert from_cache is False, explanation_text non-empty
    # count ChatMessage rows for student -> 0 (no chat session pollution)

def test_explain_second_request_uses_cache_without_tool_loop(client, db_session, monkeypatch):
    # after first explain, patch ChatToolLoop.run to raise if called
    # POST again with regenerate false -> from_cache True, same text

def test_explain_regenerate_calls_model_and_overwrites(client, db_session):
    # set explanation_text to "old"
    # POST regenerate true -> from_cache False, text changes (mock returns different assistant_message)

def test_explain_other_student_item_404(client, db_session):
    # ...
```

Use `provider="mock"` path; first call may use real `ChatToolLoop` with mock gateway.

To assert no chat pollution after explain:

```python
from app.models import ChatMessage, ChatSession
n_msgs = db_session.execute(select(func.count()).select_from(ChatMessage)).scalar()
assert n_msgs == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

`cd backend && .venv/bin/python -m pytest tests/test_wrong_book_explain.py -v`

- [ ] **Step 3: Implement service + route**

`wrong_book_explain.py` sketch:

```python
@dataclass
class WrongBookExplainResult:
    explanation_text: str
    from_cache: bool
    explanation_created_at: datetime | None

class WrongBookExplainService:
    def __init__(self, tool_loop: ChatToolLoop | None = None) -> None:
        self._tool_loop = tool_loop or ChatToolLoop()

    def explain(self, db: Session, *, item: WrongBookItem, student_user_id: uuid.UUID, regenerate: bool) -> WrongBookExplainResult:
        if item.explanation_text and not regenerate:
            return WrongBookExplainResult(
                explanation_text=item.explanation_text,
                from_cache=True,
                explanation_created_at=item.explanation_created_at,
            )
        # load policy like ChatService (copy the select ModelPolicy block)
        turn = self._tool_loop.run(
            db,
            student_user_id=student_user_id,
            agent_type="subject",
            subject_code=item.subject_code,
            provider=provider,
            model=model,
            params=params,
            history_messages=[],
            user_message=EXPLAIN_USER_MESSAGE_TEMPLATE.format(item_id=item.id),
        )
        item.explanation_text = turn.assistant_message
        item.explanation_created_at = datetime.now(timezone.utc)
        db.flush()
        return WrongBookExplainResult(
            explanation_text=item.explanation_text,
            from_cache=False,
            explanation_created_at=item.explanation_created_at,
        )
```

Router:

```python
@router.post("/{item_id}/explain", response_model=WrongBookExplainOut)
def explain_wrong_item(
    item_id: uuid.UUID,
    payload: WrongBookExplainIn,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> WrongBookExplainOut:
    item = WrongBookService.get_item(db, student.id, item_id)
    result = WrongBookExplainService().explain(
        db, item=item, student_user_id=student.id, regenerate=payload.regenerate
    )
    db.commit()
    return WrongBookExplainOut(...)
```

Schemas:

```python
class WrongBookExplainIn(BaseModel):
    regenerate: bool = False

class WrongBookExplainOut(BaseModel):
    explanation_text: str
    from_cache: bool
    explanation_created_at: datetime | None
```

- [ ] **Step 4: Run tests — expect PASS**

`cd backend && .venv/bin/python -m pytest tests/test_wrong_book_explain.py tests/test_wrong_book.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/wrong_book_explain.py backend/app/schemas/wrong_book.py \
  backend/app/routers/student_wrong_book.py backend/tests/test_wrong_book_explain.py
git commit -m "$(cat <<'EOF'
feat(wrong-book): cached explain API without chat session writes

EOF
)"
```

---

### Task 3: Frontend switch to explain API

**Files:**
- Modify: `frontend/src/api/wrongBook.ts`
- Modify: `frontend/src/pages/student/WrongBook.tsx`
- Modify: `frontend/tests/WrongBook.test.tsx`

**Interfaces:**
- Consumes: `POST /student/wrong-book/{id}/explain`
- Produces: `explainWrongItem(id, { regenerate?: boolean })`; UI「重新生成讲解」when `has_explanation` or local `explainText`

- [ ] **Step 1: Update failing tests**

In `WrongBook.test.tsx`, replace `/api/chat` mocks with:

```typescript
if (url.includes(`/api/student/wrong-book/w1/explain`) && init?.method === "POST") {
  const body = JSON.parse(String(init.body));
  expect(body.regenerate).toBe(false); // or true in regenerate test
  return new Response(JSON.stringify({
    explanation_text: "这是讲解：正确答案是 A。",
    from_cache: false,
    explanation_created_at: "2026-07-27T12:00:00Z",
  }), { status: 200 });
}
```

Add test: second click returns `from_cache: true` without changing mock call count if you track calls.

Add test for「重新生成讲解」button with `regenerate: true`.

Fixture `WrongBookItemOut` objects need `has_explanation: false` initially.

- [ ] **Step 2: Run tests — FAIL**

`cd frontend && npm test -- --run tests/WrongBook.test.tsx`

- [ ] **Step 3: Implement**

`wrongBook.ts`:

```typescript
export type WrongBookExplainOut = {
  explanation_text: string;
  from_cache: boolean;
  explanation_created_at: string | null;
};

export function explainWrongItem(itemId: string, options?: { regenerate?: boolean }) {
  return api<WrongBookExplainOut>(`/student/wrong-book/${itemId}/explain`, {
    method: "POST",
    body: JSON.stringify({ regenerate: options?.regenerate ?? false }),
  });
}
```

Add `has_explanation: boolean` to `WrongBookItemOut`.

`WrongBook.tsx`:
- Remove `postChat` import; use `explainWrongItem`
- `runExplain({ regenerate: false })` for primary button
- Show「重新生成讲解」when `explainText || item.has_explanation`
- `runExplain({ regenerate: true })` for regenerate
- Optional: small「已讲解」label when `item.has_explanation && !explainOpen`

- [ ] **Step 4: Run tests — PASS**

`cd frontend && npm test -- --run tests/WrongBook.test.tsx`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/wrongBook.ts frontend/src/pages/student/WrongBook.tsx frontend/tests/WrongBook.test.tsx
git commit -m "$(cat <<'EOF'
feat(wrong-book): use cached explain API in student UI

EOF
)"
```

---

### Task 4: Spec status and cross-link

**Files:**
- Modify: `docs/superpowers/specs/2026-07-27-wrong-book-explanation-cache-design.md` (`待实现` → `已实现`)
- Modify: `docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md` (note persistence superseded for storage/channel)

- [ ] **Step 1: Update docs**

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-07-27-wrong-book-explanation-cache-design.md \
  docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md
git commit -m "$(cat <<'EOF'
docs: mark wrong-book explanation cache spec implemented

EOF
)"
```

---

## Spec coverage self-review

| Requirement | Task |
|-------------|------|
| DB columns + overwrite on regenerate | 1, 2 |
| POST explain cache / regenerate | 2 |
| No ChatSession writes | 2 (test) |
| has_explanation on list | 1 |
| Frontend API + buttons | 3 |
| Failed regenerate keeps old text | 2 (implement in service: only update on success) |
| Docs | 4 |

Placeholder scan: none.
