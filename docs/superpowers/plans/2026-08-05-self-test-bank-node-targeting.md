# Self-Test Bank Node Targeting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SelfTestAssembler.select_from_bank` prefer bank questions tagged to weak syllabus nodes, then weekly focus nodes, then other subject items—strict waterfall—while keeping org→global priority and AI gap fill unchanged.

**Architecture:** Extend `select_from_bank` with layered node filters. Resolve L1 IDs from `ReportService.overview(...).weak_nodes`; L2 from active `MasterPlanVersion.weekly_goals_json` (`kind=focus` + matching `subject_code`). Reuse existing submitted-item exclusion and FIFO `created_at` ordering within each layer×scope. `assemble` and `paper_gen_jobs` need little change beyond calling the enhanced selector (AI still uses existing `target_nodes`).

**Tech Stack:** FastAPI, SQLAlchemy, pytest

**Spec:** `docs/superpowers/specs/2026-08-05-self-test-bank-node-targeting-design.md`

## Global Constraints

- Waterfall layers: **L1 weak → L2 weekly focus → L3 other** (strict: fill layer before next)
- Within each layer: **org active before global active**
- Exclude student-submitted `bank_item_id`s (existing rule)
- `knowledge_node_id IS NULL` items **only in L3**
- AI gap fill / `ai_generated` pending ingest / `selection_source` values **unchanged**
- No UI strategy picker; no difficulty weighting; no vector search
- On overview/plan read failure or empty IDs: treat that layer as empty (do not fail assembly)

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/self_test_assembler.py` | Resolve weak/focus IDs; layered `select_from_bank` |
| `backend/tests/test_self_test_assembler.py` | Waterfall + L3 null-node + fallback tests |
| `backend/app/services/paper_gen_jobs.py` | No behavior change expected; verify still passes `target_nodes` to AI only |
| Spec markdown | Mark 已实现 when done |

---

### Task 1: Resolve weak + focus node ID helpers

**Files:**
- Modify: `backend/app/services/self_test_assembler.py`
- Test: `backend/tests/test_self_test_assembler.py`

**Interfaces:**
- Produces:
  ```python
  def _weak_node_ids(
      self, db: Session, *, student_user_id: uuid.UUID, subject_code: str
  ) -> set[uuid.UUID]: ...

  def _weekly_focus_node_ids(
      self, db: Session, *, student_user_id: uuid.UUID, subject_code: str
  ) -> set[uuid.UUID]: ...
  ```
- Consumes: `ReportService.overview` + `ReportQuery`; `MasterPlanActivationService().get_state(db, student_user_id=...).get("active_version")` → `weekly_goals_json`

- [ ] **Step 1: Write failing tests for helpers**

Add to `backend/tests/test_self_test_assembler.py` (reuse `_people` / factories; seed wrong-book weak node and master plan focus goals as other tests do—or construct overview via DB wrong book + mastery patterns used in `test_report.py`):

```python
def test_weak_node_ids_from_overview(db_session):
    org, admin, student = _people(db_session)
    # seed one SyllabusNode leaf for english + active WrongBookItem pointing at it
    # (mirror report weak_nodes setup if a helper exists; otherwise minimal insert)
    node = _english_leaf(db_session)  # local helper or seed_minimal_syllabus + pick leaf
    _wrong_book_item(db_session, student.id, node.id)
    db_session.commit()
    ids = SelfTestAssembler()._weak_node_ids(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert node.id in ids


def test_weekly_focus_node_ids_from_active_master(db_session):
    org, admin, student = _people(db_session)
    node_id = uuid.uuid4()
    # create MasterPlan + MasterPlanVersion with current_version_id and
    # weekly_goals_json=[{"kind":"focus","subject_code":"english","syllabus_node_ids":[str(node_id)],"title":"t","description":"d"}]
    _seed_master_with_focus(db_session, student.id, "english", [node_id])
    db_session.commit()
    ids = SelfTestAssembler()._weekly_focus_node_ids(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert node_id in ids


def test_weekly_focus_ignores_other_subject(db_session):
    org, admin, student = _people(db_session)
    math_id = uuid.uuid4()
    _seed_master_with_focus(db_session, student.id, "math", [math_id])
    db_session.commit()
    ids = SelfTestAssembler()._weekly_focus_node_ids(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert math_id not in ids
```

Implement `_seed_master_with_focus` / `_wrong_book_item` / `_english_leaf` as private test helpers in the same file, following existing model constructors in `tests/factories.py` and report tests.

- [ ] **Step 2: Run — expect FAIL (methods missing)**

```bash
cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  tests/test_self_test_assembler.py::test_weak_node_ids_from_overview \
  tests/test_self_test_assembler.py::test_weekly_focus_node_ids_from_active_master \
  tests/test_self_test_assembler.py::test_weekly_focus_ignores_other_subject -v
```

Expected: AttributeError / FAIL

- [ ] **Step 3: Implement helpers**

```python
def _weak_node_ids(self, db, *, student_user_id, subject_code) -> set[uuid.UUID]:
    try:
        overview = ReportService.overview(
            db,
            ReportQuery(student_user_id=student_user_id, subject_code=subject_code),
        )
    except Exception:
        return set()
    out: set[uuid.UUID] = set()
    for w in overview.weak_nodes or []:
        if w.knowledge_node_id is not None:
            out.add(w.knowledge_node_id)
    return out

def _weekly_focus_node_ids(self, db, *, student_user_id, subject_code) -> set[uuid.UUID]:
    try:
        state = MasterPlanActivationService().get_state(db, student_user_id=student_user_id)
        active = state.get("active_version") if isinstance(state, dict) else None
    except Exception:
        return set()
    if active is None:
        return set()
    goals = active.weekly_goals_json or []
    out: set[uuid.UUID] = set()
    for g in goals:
        if not isinstance(g, dict):
            continue
        if g.get("kind") != "focus":
            continue
        if g.get("subject_code") != subject_code:
            continue
        for raw in g.get("syllabus_node_ids") or []:
            try:
                out.add(uuid.UUID(str(raw)))
            except (ValueError, TypeError):
                continue
    return out
```

Import `ReportService`, `ReportQuery`, `MasterPlanActivationService`. Confirm `get_state` return shape in `master_plan_activation.py`; if key differs (e.g. returns a dataclass), adapt to the real attribute—**read the file before coding**.

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/self_test_assembler.py backend/tests/test_self_test_assembler.py
git commit -m "feat(self-test): resolve weak and weekly focus node ids for bank select"
```

---

### Task 2: Layered waterfall `select_from_bank`

**Files:**
- Modify: `backend/app/services/self_test_assembler.py` (`select_from_bank`)
- Test: `backend/tests/test_self_test_assembler.py`

**Interfaces:**
- `select_from_bank` signature **unchanged** (still takes org/student/subject/count/exclude)
- Internally calls `_weak_node_ids` / `_weekly_focus_node_ids`, then for each layer × scope fills remaining slots

Layer filters:
- L1: `knowledge_node_id.in_(weak_ids)` (skip layer if `weak_ids` empty)
- L2: `knowledge_node_id.in_(focus_ids)` (skip if empty); still exclude already-selected ids
- L3: `or_(knowledge_node_id.is_(None), knowledge_node_id.not_in(weak_ids | focus_ids))` — if both sets empty, L3 is all active subject items (current behavior)

- [ ] **Step 1: Write failing waterfall tests**

```python
def test_select_prefers_weak_then_focus_then_other(db_session):
    org, admin, student = _people(db_session)
    weak_node, focus_node, other_node = _three_english_leaves(db_session)
    # seed wrong book → weak; master focus → focus_node
    _wrong_book_item(db_session, student.id, weak_node.id)
    _seed_master_with_focus(db_session, student.id, "english", [focus_node.id])

    weak_item = _bank_item(db_session, admin, org.id, stem="W", knowledge_node_id=weak_node.id)
    focus_item = _bank_item(db_session, admin, org.id, stem="F", knowledge_node_id=focus_node.id)
    other_item = _bank_item(db_session, admin, org.id, stem="O", knowledge_node_id=other_node.id)
    null_item = _bank_item(db_session, admin, org.id, stem="N", knowledge_node_id=None)
    # make other/null older so FIFO would pick them first without layering
    db_session.commit()

    picked = SelfTestAssembler().select_from_bank(
        db_session, org_id=org.id, student_user_id=student.id,
        subject_code="english", count=3,
    )
    assert [p.bank_item_id for p in picked] == [weak_item.id, focus_item.id, other_item.id]
    # null_item not among first 3 when other_node fills L3 before needing null? 
    # With count=3 and other_node present, null may or may not be 4th — assert null not in first three if other fills L3:
    assert null_item.id not in {p.bank_item_id for p in picked}


def test_null_node_only_in_l3_when_weak_fills(db_session):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    w1 = _bank_item(db_session, admin, org.id, stem="W1", knowledge_node_id=weak_node.id)
    w2 = _bank_item(db_session, admin, org.id, stem="W2", knowledge_node_id=weak_node.id)
    null_item = _bank_item(db_session, admin, org.id, stem="N", knowledge_node_id=None)
    db_session.commit()
    picked = SelfTestAssembler().select_from_bank(
        db_session, org_id=org.id, student_user_id=student.id,
        subject_code="english", count=2,
    )
    assert {p.bank_item_id for p in picked} == {w1.id, w2.id}
    assert null_item.id not in {p.bank_item_id for p in picked}


def test_org_before_global_within_weak_layer(db_session):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    global_item = _bank_item(
        db_session, admin, None, stem="G", scope="global",
        knowledge_node_id=weak_node.id, created_earlier=True,
    )
    org_item = _bank_item(
        db_session, admin, org.id, stem="O", knowledge_node_id=weak_node.id,
    )
    db_session.commit()
    picked = SelfTestAssembler().select_from_bank(
        db_session, org_id=org.id, student_user_id=student.id,
        subject_code="english", count=1,
    )
    assert picked[0].bank_item_id == org_item.id
    assert picked[0].selection_source == "bank_org"
```

Extend `_bank_item` helper to accept `knowledge_node_id` and optional `scope`/`org_id=None` for global (match existing `_bank_item` in file).

- [ ] **Step 2: Run — FAIL (order still FIFO)**

```bash
cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  tests/test_self_test_assembler.py::test_select_prefers_weak_then_focus_then_other \
  tests/test_self_test_assembler.py::test_null_node_only_in_l3_when_weak_fills \
  tests/test_self_test_assembler.py::test_org_before_global_within_weak_layer -v
```

- [ ] **Step 3: Implement layered selection**

Replace the body of `select_from_bank` with:

```python
weak_ids = self._weak_node_ids(db, student_user_id=student_user_id, subject_code=subject_code)
focus_ids = self._weekly_focus_node_ids(db, student_user_id=student_user_id, subject_code=subject_code)
# submitted exclusion unchanged...
selected: list[AssembledQuestion] = []
selected_ids: set[uuid.UUID] = set()

def _append_from_query(node_clause, remaining: int) -> None:
    nonlocal selected, selected_ids
    for scope, source in (("org", "bank_org"), ("global", "bank_global")):
        rem = remaining - (len(selected) - start_len)  # or pass remaining carefully
        ...

# Cleaner: loop layers explicitly
layers: list[tuple[str, set[uuid.UUID] | None]] = [
    ("weak", weak_ids),
    ("focus", focus_ids),
    ("other", None),
]
for _name, layer_ids in layers:
    if layer_ids is not None and len(layer_ids) == 0:
        continue
    for scope, source in (("org", "bank_org"), ("global", "bank_global")):
        remaining = count - len(selected)
        if remaining <= 0:
            break
        conditions = [
            QuestionBankItem.scope == scope,
            QuestionBankItem.subject_code == subject_code,
            QuestionBankItem.status == "active",
        ]
        if scope == "org":
            conditions.append(QuestionBankItem.org_id == org_id)
        if layer_ids is not None:
            conditions.append(QuestionBankItem.knowledge_node_id.in_(layer_ids))
        else:
            banned = weak_ids | focus_ids
            if banned:
                conditions.append(
                    or_(
                        QuestionBankItem.knowledge_node_id.is_(None),
                        QuestionBankItem.knowledge_node_id.not_in(banned),
                    )
                )
        blocked = excluded_ids | selected_ids
        stmt = (
            select(QuestionBankItem)
            .where(*conditions)
            .order_by(QuestionBankItem.created_at.asc(), QuestionBankItem.id.asc())
            .limit(remaining)
        )
        if blocked:
            stmt = stmt.where(QuestionBankItem.id.not_in(blocked))
        for item in db.execute(stmt).scalars():
            selected_ids.add(item.id)
            selected.append(AssembledQuestion(... selection_source=source, seq=len(selected)+1))
    if count - len(selected) <= 0:
        break
return selected
```

Import `or_` from SQLAlchemy. Keep `AssembledQuestion` fields unchanged.

- [ ] **Step 4: Run new + existing assembler tests — PASS**

```bash
cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_self_test_assembler.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(self-test): waterfall bank select by weak then weekly focus"
```

---

### Task 3: Regression — assemble + job path still works

**Files:**
- Test: extend `backend/tests/test_self_test_assembler.py` and/or `backend/tests/test_self_test_flow.py` / `test_paper_gen_jobs.py` if a bank-full job test exists
- Modify: only if a bug surfaces in `paper_gen_jobs.py` (prefer zero changes)

**Interfaces:** unchanged `assemble(...)` / job runner

- [ ] **Step 1: Test assemble with weak bank stock avoids AI**

```python
def test_assemble_uses_weak_bank_without_llm(db_session, monkeypatch):
    org, admin, student = _people(db_session)
    weak_node = _english_leaf(db_session)
    _wrong_book_item(db_session, student.id, weak_node.id)
    items = [
        _bank_item(db_session, admin, org.id, stem=f"W{i}", knowledge_node_id=weak_node.id)
        for i in range(DEFAULT_QUESTION_COUNT)  # import from paper_gen
    ]
    db_session.commit()

    def boom(*args, **kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr(PaperGenService, "generate_prepared_self_test", boom)
    out = SelfTestAssembler().assemble(
        db_session,
        org_id=org.id,
        student_user_id=student.id,
        subject_code="english",
        question_count=DEFAULT_QUESTION_COUNT,
        provider=None, model=None, params=None,
        target_nodes=[],
    )
    assert len(out) == DEFAULT_QUESTION_COUNT
    assert all(q.selection_source == "bank_org" for q in out)
```

- [ ] **Step 2: Run — PASS (or fix wiring)**

```bash
cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  tests/test_self_test_assembler.py tests/test_self_test_flow.py -q --tb=short
```

- [ ] **Step 3: Mark spec implemented**

In `docs/superpowers/specs/2026-08-05-self-test-bank-node-targeting-design.md`, set **状态：** `已实现`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests docs/superpowers/specs/2026-08-05-self-test-bank-node-targeting-design.md
git commit -m "test(self-test): cover weak bank assemble without LLM; mark spec done"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| L1 weak → L2 focus → L3 other waterfall | T2 |
| Org before global within layer | T2 |
| Null node only L3 | T2 |
| Submitted bank_item exclusion | T2 (retain) |
| Empty layers skip / no hard fail | T1–T2 |
| AI gap unchanged | T3 |
| No strategy UI / no vector / no difficulty | out of scope |

No TBD placeholders. Helper return types are `set[uuid.UUID]`. `get_state` shape must be verified against live `master_plan_activation.py` during Task 1.
