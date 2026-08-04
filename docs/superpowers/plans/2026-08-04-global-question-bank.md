# Global Question Bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mixed-scope question bank so self-tests prefer bank items (org then global), AI fallbacks auto-ingest as pending review, and teachers/admins can add questions via minimal stem entry (model-enriched attributes) or one-image OCR.

**Architecture:** Introduce `QuestionBankItem` as the asset layer; keep `SelfTestQuestion` as immutable paper snapshots with `bank_item_id` + `selection_source`. A `QuestionBankService` owns CRUD/review/dedupe; a `SelfTestAssembler` selects from the bank then calls existing `PaperGenService` only for gaps. Enrichment and OCR use ModelPolicy (`paper_gen` scene initially) via structured LLM calls. Admin/staff UIs list, confirm-create, and review.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, React, Vitest, existing ModelGateway / paper_gen policies

**Spec:** `docs/superpowers/specs/2026-08-04-global-question-bank-design.md`

## Global Constraints

- Scope: `global` (no org) + `org` (org_id required); self-test select **org active first**, then **global active**, then AI fallback
- Status gate: only `active` is selectable for self-test
- Source review: manual confirm → `active`; `ocr_import` / `ai_generated` → `pending_review` until approve
- Question types (v1): `single_choice` | `multi_choice` | `fill_blank` | `short_answer`
- Difficulty: integer `1`–`5`
- Entry UX: user supplies **stem (+ choices/answer as needed)** only; model suggests subject/node/difficulty/analysis; human confirms before save
- OCR v1: **one image → one question**; no multi-cut / batch
- AI fallback bank rows: `scope=org`, `org_id` = student's org
- Exact dedupe only (same scope/org + stem + q_type); no vector search
- Do not mutate historical `SelfTestQuestion` content when bank items change
- Phases: P1 bank+manual+review → P2 assemble+AI ingest → P3 OCR; each phase must ship testable

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/models/question_bank.py` | `QuestionBankItem`, `MediaAsset` |
| `backend/app/models/self_test.py` | Add `bank_item_id`, `selection_source` on `SelfTestQuestion` |
| `backend/alembic/versions/*_question_bank.py` | Tables + self_test_questions columns |
| `backend/app/models/__init__.py` | Export new models |
| `backend/app/schemas/question_bank.py` | API schemas |
| `backend/app/services/question_bank.py` | CRUD, review, exact dedupe, list filters |
| `backend/app/services/question_enrichment.py` | LLM attribute suggestion from stem |
| `backend/app/services/self_test_assembler.py` | Bank-first selection + AI gap fill + snapshot write |
| `backend/app/services/question_ocr.py` | Image → structured stem (P3) |
| `backend/app/services/media_assets.py` | Store uploaded images (P3) |
| `backend/app/services/paper_gen_jobs.py` | Call assembler for `purpose=self_test` |
| `backend/app/routers/org_question_bank.py` | Shared admin/staff bank routes |
| `backend/app/main.py` | Include router |
| `backend/tests/test_question_bank*.py` | Service + API tests |
| `backend/tests/test_self_test_assembler.py` | Selection order + fallback ingest |
| `backend/tests/conftest.py` | Sync new tables/columns for tests |
| `frontend/src/api/questionBank.ts` | Client |
| `frontend/src/pages/admin/QuestionBank.tsx` | Admin bank UI |
| `frontend/src/pages/staff/QuestionBank.tsx` | Staff bank UI (or shared component) |
| `frontend/src/components/questionBank/*` | List, CreateConfirm, Review shared UI |
| `frontend/src/App.tsx` / `Layout.tsx` | Routes + nav |
| `frontend/tests/QuestionBank*.test.tsx` | UI tests |
| Spec file | Mark 已实现 when all phases done (or per-phase notes) |

---

## Phase P1 — Bank core + manual entry + review

### Task 1: Schema — `QuestionBankItem`, `MediaAsset`, self-test link columns

**Files:**
- Create: `backend/app/models/question_bank.py`
- Create: `backend/alembic/versions/<rev>_question_bank.py` (generate via alembic or hand-write following latest head)
- Modify: `backend/app/models/self_test.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/conftest.py` (`_sync_test_schema` if used)

**Interfaces:**
- Produces ORM:
  - `MediaAsset(id, org_id, created_by, content_type, storage_path, created_at)`
  - `QuestionBankItem(id, scope, org_id, subject_code, knowledge_node_id, q_type, stem, choices_json, answer_key, analysis_text, difficulty, source_type, status, created_by, reviewed_by, reviewed_at, source_image_asset_id, created_at, updated_at)`
  - `SelfTestQuestion.bank_item_id: UUID | None`, `selection_source: str | None`

- [ ] **Step 1: Write failing model/import smoke test**

Create `backend/tests/test_question_bank_model.py`:

```python
from app.models import QuestionBankItem, MediaAsset, SelfTestQuestion

def test_question_bank_models_importable():
    assert QuestionBankItem.__tablename__ == "question_bank_items"
    assert MediaAsset.__tablename__ == "media_assets"
    assert hasattr(SelfTestQuestion, "bank_item_id")
    assert hasattr(SelfTestQuestion, "selection_source")
```

- [ ] **Step 2: Run — expect FAIL (import error)**

```bash
cd backend && .venv/bin/python -m pytest tests/test_question_bank_model.py -v
```

Expected: FAIL importing `QuestionBankItem`

- [ ] **Step 3: Implement models + migration + exports**

`backend/app/models/question_bank.py` (core fields as in Interfaces; `scope`/`source_type`/`status`/`q_type` as `String`; FKs to `organizations`, `users`, `syllabus_nodes`, `media_assets`).

On `SelfTestQuestion` add:

```python
bank_item_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("question_bank_items.id", ondelete="SET NULL"), nullable=True
)
selection_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
```

Export from `__init__.py`. Add Alembic revision after current head. Update `conftest._sync_test_schema` to create new tables/columns the same way other recent migrations are mirrored.

- [ ] **Step 4: Run test — PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/test_question_bank_model.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/question_bank.py backend/app/models/self_test.py backend/app/models/__init__.py backend/alembic/versions backend/tests/test_question_bank_model.py backend/tests/conftest.py
git commit -m "feat(question-bank): add bank item and media asset schema"
```

---

### Task 2: `QuestionBankService` — create, list, review, exact dedupe

**Files:**
- Create: `backend/app/services/question_bank.py`
- Create: `backend/app/schemas/question_bank.py` (minimal domain-facing dataclasses or pydantic used by service)
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Produces:
  - `QuestionBankService.create(db, *, actor: User, payload) -> QuestionBankItem`
  - `QuestionBankService.list(db, *, viewer: User, status=None, subject_code=None, pending_only=False) -> list[QuestionBankItem]`
  - `QuestionBankService.approve(db, *, actor: User, item_id) -> QuestionBankItem`
  - `QuestionBankService.reject(db, *, actor: User, item_id) -> QuestionBankItem`
  - `QuestionBankService.disable(db, *, actor: User, item_id) -> QuestionBankItem`
  - `QuestionBankService.find_exact_duplicate(db, *, scope, org_id, q_type, stem) -> QuestionBankItem | None`
- Create rules: `source_type in (admin_manual, staff_manual)` → `status=active`; `ocr_import|ai_generated` → `pending_review`
- List visibility: staff sees own-org items; admin sees own-org + global; staff cannot mutate global

- [ ] **Step 1: Write failing tests**

```python
def test_manual_create_is_active(db_session):
    admin, org = _admin(db_session)
    item = QuestionBankService().create(
        db_session,
        actor=admin,
        scope="org",
        org_id=org.id,
        subject_code="english",
        knowledge_node_id=None,
        q_type="single_choice",
        stem="What is X?",
        choices_json=[{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
        answer_key="A",
        analysis_text=None,
        difficulty=2,
        source_type="admin_manual",
    )
    db_session.commit()
    assert item.status == "active"
    assert item.org_id == org.id


def test_exact_duplicate_detected(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    svc.create(db_session, actor=admin, scope="org", org_id=org.id, subject_code="english",
               knowledge_node_id=None, q_type="single_choice", stem="Same stem",
               choices_json=[], answer_key="A", analysis_text=None, difficulty=1,
               source_type="admin_manual")
    db_session.commit()
    dup = svc.find_exact_duplicate(
        db_session, scope="org", org_id=org.id, q_type="single_choice", stem="Same stem"
    )
    assert dup is not None


def test_approve_pending_ai_item(db_session):
    admin, org = _admin(db_session)
    item = QuestionBankService().create(
        db_session, actor=admin, scope="org", org_id=org.id, subject_code="english",
        knowledge_node_id=None, q_type="short_answer", stem="Explain Y",
        choices_json=None, answer_key="ref", analysis_text=None, difficulty=3,
        source_type="ai_generated",
    )
    db_session.commit()
    assert item.status == "pending_review"
    approved = QuestionBankService().approve(db_session, actor=admin, item_id=item.id)
    db_session.commit()
    assert approved.status == "active"
    assert approved.reviewed_by == admin.id
```

Helpers `_admin` mirror other tests (`make_org` / `make_user`).

- [ ] **Step 2: Run — expect FAIL**

```bash
cd backend && .venv/bin/python -m pytest tests/test_question_bank_service.py -v
```

- [ ] **Step 3: Implement service**

Raise `HTTPException(409)` from create when exact duplicate exists (callers may catch). Normalize stem with `strip()` for dedupe compare. `approve`/`reject` only from `pending_review`. `disable` only from `active`. Enforce staff cannot set `scope=global` or approve global items.

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(question-bank): service create/list/review and exact dedupe"
```

---

### Task 3: Attribute enrichment service

**Files:**
- Create: `backend/app/services/question_enrichment.py`
- Test: `backend/tests/test_question_enrichment.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class EnrichmentSuggestion:
      subject_code: str
      knowledge_node_id: uuid.UUID | None
      difficulty: int  # 1-5
      analysis_text: str | None
      q_type: str | None  # optional correction/suggestion

  class QuestionEnrichmentService:
      def suggest(
          self,
          db: Session,
          *,
          org_id: uuid.UUID,
          stem: str,
          q_type: str,
          choices_json: list | None,
          answer_key: str | None,
      ) -> EnrichmentSuggestion: ...
  ```
- Uses `ModelPolicy` with `scene="paper_gen"` (same org); if no policy, return heuristic defaults (`subject_code` from stem keywords or `"english"`, `difficulty=3`, `knowledge_node_id=None`) so local tests work without LLM.
- Inject/mock LLM in tests via optional callable or monkeypatch `_call_llm`.

- [ ] **Step 1: Failing test (heuristic path)**

```python
def test_enrichment_heuristic_without_policy(db_session):
    org = make_org(db_session)
    db_session.commit()
    out = QuestionEnrichmentService().suggest(
        db_session,
        org_id=org.id,
        stem="Choose the correct tense: She ___ to school.",
        q_type="single_choice",
        choices_json=[{"key": "A", "text": "go"}, {"key": "B", "text": "goes"}],
        answer_key="B",
    )
    assert out.subject_code
    assert 1 <= out.difficulty <= 5
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement** — parse JSON from LLM when policy exists; clamp difficulty; validate `knowledge_node_id` exists for subject else set `None`.

- [ ] **Step 4: PASS + commit**

```bash
git commit -m "feat(question-bank): attribute enrichment suggestions"
```

---

### Task 4: Org question-bank HTTP API

**Files:**
- Create: `backend/app/schemas/question_bank.py` (if not complete)
- Create: `backend/app/routers/org_question_bank.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_question_bank_api.py`

**Interfaces (routes):**
- `POST /org/question-bank/enrich` → suggestions (roles: `org_admin`, `org_staff`)
- `POST /org/question-bank` → create after confirm body (includes attributes)
- `GET /org/question-bank` → list (`status`, `subject_code`, `pending=1`)
- `POST /org/question-bank/{id}/approve|reject|disable`

Payload example create:

```json
{
  "scope": "org",
  "subject_code": "english",
  "knowledge_node_id": null,
  "q_type": "single_choice",
  "stem": "...",
  "choices": [{"key": "A", "text": "..."}],
  "answer_key": "A",
  "analysis_text": "...",
  "difficulty": 2,
  "source_type": "staff_manual"
}
```

- [ ] **Step 1: API test create + list + approve**

Use `client` + seeded admin/staff tokens like other org tests.

- [ ] **Step 2: FAIL → implement router → PASS → commit**

```bash
git commit -m "feat(question-bank): org admin/staff HTTP API"
```

---

### Task 5: Frontend — bank list, create-confirm, review

**Files:**
- Create: `frontend/src/api/questionBank.ts`
- Create: `frontend/src/components/questionBank/QuestionBankPage.tsx` (shared)
- Create: `frontend/src/pages/admin/QuestionBank.tsx` / `frontend/src/pages/staff/QuestionBank.tsx` (thin wrappers)
- Modify: `frontend/src/App.tsx`, `frontend/src/components/Layout.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

**UI flow:**
1. List with filters (科目 / 状态 / 待审核)
2. 「新建题目」: form with stem + type-dependent fields only → call enrich → show confirm panel with editable subject/node/difficulty/analysis → submit create
3. Pending row actions: 通过 / 驳回; active: 禁用

- [ ] **Step 1: Vitest** — mock enrich + create; assert confirm shows suggested subject; submit posts create

- [ ] **Step 2: Implement pages + nav「题库」 for admin and staff**

- [ ] **Step 3: `npm test -- --run tests/QuestionBank.test.tsx` PASS → commit**

```bash
git commit -m "feat(question-bank): admin/staff bank UI with enrich confirm"
```

---

## Phase P2 — Self-test bank-first assembly + AI ingest

### Task 6: `SelfTestAssembler` — select org then global, student dedupe

**Files:**
- Create: `backend/app/services/self_test_assembler.py`
- Test: `backend/tests/test_self_test_assembler.py`

**Interfaces:**
```python
@dataclass
class AssembledQuestion:
    bank_item_id: uuid.UUID | None
    selection_source: str  # bank_org | bank_global | ai_fallback
    knowledge_node_id: uuid.UUID | None
    q_type: str
    stem: str
    choices_json: list | None
    answer_key: str | None
    points: int
    seq: int

class SelfTestAssembler:
    def select_from_bank(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        count: int,
        exclude_bank_ids: set[uuid.UUID] | None = None,
    ) -> list[AssembledQuestion]: ...
```

Selection: query `active` org items for subject, exclude student recent `bank_item_id`s (from submitted papers via join), fill; then same for `scope=global`. Set `selection_source` accordingly. Do not AI yet in this task.

- [ ] **Step 1: Seed N org + M global active items; assert order org-first and count**

- [ ] **Step 2: Implement → PASS → commit**

```bash
git commit -m "feat(self-test): bank-first question selection"
```

---

### Task 7: Assembler AI gap fill + pending bank ingest

**Files:**
- Modify: `backend/app/services/self_test_assembler.py`
- Modify / reuse: `backend/app/services/paper_gen.py` (`generate_prepared_self_test`)
- Test: extend `backend/tests/test_self_test_assembler.py`

**Interfaces:**
```python
    def assemble(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        student_user_id: uuid.UUID,
        subject_code: str,
        question_count: int,
        # provider/model/params + target_nodes same as current paper gen job
        ...
        on_progress: ProgressCallback | None = None,
    ) -> list[AssembledQuestion]:
```

Logic:
1. `picked = select_from_bank(... count=question_count)`
2. `gap = question_count - len(picked)`
3. If gap > 0: call existing generator for `gap` questions; for each generated Q:
   - `find_exact_duplicate` → reuse id if active/pending else create `ai_generated`/`pending_review`/`scope=org`
   - append `AssembledQuestion(..., selection_source="ai_fallback", bank_item_id=...)`
4. Re-number `seq` 1..N

- [ ] **Step 1: Test with monkeypatched generator returning 1 Q when bank empty → assert bank row pending + assembled ai_fallback**

- [ ] **Step 2: Implement → PASS → commit**

```bash
git commit -m "feat(self-test): AI fallback ingest into question bank"
```

---

### Task 8: Wire `PaperGenJobRunner` self_test path to assembler

**Files:**
- Modify: `backend/app/services/paper_gen_jobs.py` (self_test branch in `_execute_job` and isolated twin if duplicated)
- Test: extend `backend/tests/test_self_test_flow.py` or new `test_self_test_bank_assembly_job.py`

**Behavior:** Replace pure `generate_prepared_self_test` loop with `SelfTestAssembler.assemble`, then write `SelfTestQuestion` including `bank_item_id` and `selection_source`. Keep placement path unchanged.

- [ ] **Step 1: Integration test** — seed enough bank items → generate self-test → paper ready with `selection_source=bank_org` and no LLM call (mock paper_gen to fail if called)

- [ ] **Step 2: Implement wiring → PASS → commit**

```bash
git commit -m "feat(self-test): paper gen job uses bank assembler"
```

---

## Phase P3 — OCR one-image-one-question

### Task 9: Media upload + OCR extract API

**Files:**
- Create: `backend/app/services/media_assets.py`
- Create: `backend/app/services/question_ocr.py`
- Modify: `backend/app/routers/org_question_bank.py`
- Test: `backend/tests/test_question_ocr.py`

**Interfaces:**
- `POST /org/question-bank/upload-image` multipart → `{ asset_id, url_or_path }`
- `POST /org/question-bank/ocr` `{ asset_id }` → structured `{ q_type, stem, choices, answer_key }` (then client calls enrich)
- Store files under `backend/var/media/{org_id}/{uuid}` (gitignore `var/`); persist `MediaAsset`
- OCR: vision/LLM via ModelPolicy `paper_gen`; tests monkeypatch `_extract`

- [ ] **Step 1: Unit test OCR service with stub returning fixed stem**

- [ ] **Step 2: Implement storage + routes → PASS → commit**

```bash
git commit -m "feat(question-bank): image upload and OCR extract"
```

---

### Task 10: Frontend OCR entry on create flow

**Files:**
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Modify: `frontend/src/api/questionBank.ts`
- Test: `frontend/tests/QuestionBankOcr.test.tsx`

**UI:** 「图片识别添加」 next to 「手工添加」 → upload → show OCR stem/choices → enrich → confirm → create with `source_type=ocr_import` (pending_review).

- [ ] **Step 1: Vitest mock upload+ocr+enrich+create**

- [ ] **Step 2: Implement → PASS → commit**

```bash
git commit -m "feat(question-bank): OCR import confirm UI"
```

---

### Task 11: Spec status + smoke checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-08-04-global-question-bank-design.md` → **状态：已实现** (or「P1–P3 已实现」)

- [ ] **Step 1: Manual smoke** (document results in commit body if useful)
  - Manual create → active → appears in list
  - Generate self-test with bank stock → bank_org sources
  - Empty bank subject → AI fallback → pending item
  - OCR path → pending → approve → selectable

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: mark global question bank spec implemented"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Mixed global/org scope | T1–T2, T6 |
| Graded review by source | T2, T4–T5, T7 |
| Types SC/MC/FB/SA | T1–T2 schemas |
| Bank-first then AI | T6–T8 |
| AI ingest pending org | T7 |
| Minimal entry + enrich confirm | T3–T5 |
| OCR one-image | T9–T10 |
| Exact + student dedupe | T2, T6–T7 |
| Snapshot stability | T1 columns; no update of past stems |
| Phased P1–P3 | Task grouping above |

No TBD placeholders. Names consistent: `QuestionBankItem`, `SelfTestAssembler`, `selection_source` values `bank_org|bank_global|ai_fallback`.
