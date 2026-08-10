# Question Bank Edit + Knowledge Node Picker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admin/staff edit non-active question bank items (stem, type, choices, answer, subject, knowledge node, difficulty, analysis) and pick knowledge nodes via a searchable subject-scoped dropdown on create-confirm and edit flows.

**Architecture:** Add `QuestionBankService.update` with status transitions (`rejected`/`disabled` → `pending_review`; block `active`), plus `GET /org/question-bank/knowledge-nodes` returning leaf syllabus nodes with parent names. Frontend extracts `KnowledgeNodeSelect` and an edit modal reusing create-confirm field layout + `MathText` previews; `PATCH` refreshes paginated list.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest; React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-08-10-question-bank-edit-node-picker-design.md`

## Global Constraints

- Editable statuses: `pending_review` / `rejected` / `disabled` only; `active` must be disabled first
- After edit: `rejected` / `disabled` → `pending_review` (clear `reviewed_by` / `reviewed_at`); `pending_review` unchanged
- Editable fields: stem, q_type, choices, answer_key, subject_code, knowledge_node_id, difficulty, analysis_text; **not** `scope`
- Knowledge node must be a **leaf** node matching effective subject; explicit `null` clears; subject-only change auto-clears mismatched node
- Do not mutate historical `SelfTestQuestion` snapshots
- Register `GET /knowledge-nodes` **before** `/{item_id}/...` routes
- Reuse existing `_get_mutable_item` permission rules (staff: org only; admin: org + global)

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/schemas/question_bank.py` | `QuestionBankUpdateRequest`, `KnowledgeNodeOptionOut` |
| `backend/app/services/question_bank.py` | `update()`, `list_leaf_knowledge_nodes()` |
| `backend/app/routers/org_question_bank.py` | `GET knowledge-nodes`, `PATCH {id}` |
| `backend/tests/test_question_bank_service.py` | Service update + leaf list tests |
| `backend/tests/test_question_bank_api.py` | HTTP PATCH + knowledge-nodes tests |
| `frontend/src/api/questionBank.ts` | `updateQuestion`, `listKnowledgeNodes`, types |
| `frontend/src/components/questionBank/KnowledgeNodeSelect.tsx` | Searchable select |
| `frontend/src/components/questionBank/QuestionBankEditForm.tsx` | Shared edit/create-confirm fields |
| `frontend/src/components/questionBank/QuestionBankPage.tsx` | Edit entry + picker on create confirm |
| `frontend/tests/QuestionBank.test.tsx` | Edit + picker tests |
| `docs/superpowers/specs/2026-08-10-question-bank-edit-node-picker-design.md` | Mark 已实现 when done |

---

### Task 1: Schemas — update request + knowledge node option

**Files:**
- Modify: `backend/app/schemas/question_bank.py`

**Interfaces:**
- Produces:
  - `QuestionBankUpdateRequest(stem?, q_type?, choices?, answer_key?, subject_code?, knowledge_node_id?, difficulty?, analysis_text?)`
  - `KnowledgeNodeOptionOut(id: UUID, name: str, parent_name: str | None)`

- [ ] **Step 1: Add schemas**

```python
class QuestionBankUpdateRequest(BaseModel):
    stem: str | None = None
    q_type: str | None = None
    choices: list[dict] | None = None
    answer_key: str | None = None
    subject_code: str | None = None
    knowledge_node_id: uuid.UUID | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    analysis_text: str | None = None


class KnowledgeNodeOptionOut(BaseModel):
    id: uuid.UUID
    name: str
    parent_name: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/question_bank.py
git commit -m "feat(question-bank): add update and knowledge-node schemas"
```

---

### Task 2: Service — leaf nodes + update with status rules

**Files:**
- Modify: `backend/app/services/question_bank.py`
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Consumes: `QuestionBankUpdateRequest` fields (passed as kwargs/dataclass in service)
- Produces:
  - `QuestionBankService.list_leaf_knowledge_nodes(db, *, subject_code: str) -> list[SyllabusNode]`
  - `QuestionBankService.update(db, *, actor: User, item_id: UUID, **fields) -> QuestionBankItem`

- [ ] **Step 1: Write failing service tests**

Add to `backend/tests/test_question_bank_service.py`:

```python
def test_list_leaf_knowledge_nodes_returns_only_leaves(db_session):
    parent = SyllabusNode(subject_code="math", name="高数", parent_id=None, weight=1)
    db_session.add(parent)
    db_session.flush()
    leaf = SyllabusNode(subject_code="math", name="多元函数", parent_id=parent.id, weight=1)
    mid = SyllabusNode(subject_code="math", name="章节", parent_id=None, weight=1)
    child = SyllabusNode(subject_code="math", name="小节", parent_id=mid.id, weight=1)
    db_session.add_all([leaf, mid, child])
    db_session.flush()

    svc = QuestionBankService()
    leaves = svc.list_leaf_knowledge_nodes(db_session, subject_code="math")
    ids = {n.id for n in leaves}
    assert leaf.id in ids
    assert child.id in ids
    assert mid.id not in ids
    assert parent.id not in ids


def test_update_pending_review_keeps_status(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    db_session.flush()

    updated = svc.update(
        db_session,
        actor=admin,
        item_id=item.id,
        stem="Updated stem",
    )
    assert updated.status == "pending_review"
    assert updated.stem == "Updated stem"


def test_update_rejected_returns_to_pending_review(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    svc.reject(db_session, actor=admin, item_id=item.id)
    db_session.flush()
    assert item.reviewed_by is not None

    updated = svc.update(db_session, actor=admin, item_id=item.id, stem="Fix it")
    assert updated.status == "pending_review"
    assert updated.reviewed_by is None
    assert updated.reviewed_at is None


def test_update_active_is_rejected(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin)
    db_session.flush()

    with pytest.raises(HTTPException) as exc:
        svc.update(db_session, actor=admin, item_id=item.id, stem="Nope")
    assert exc.value.status_code == 409
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_question_bank_service.py::test_list_leaf_knowledge_nodes_returns_only_leaves -v`
Expected: FAIL (`list_leaf_knowledge_nodes` missing)

- [ ] **Step 3: Implement leaf helper + update**

In `question_bank.py`, import `SyllabusNode` and add:

```python
def list_leaf_knowledge_nodes(self, db: Session, *, subject_code: str) -> list[SyllabusNode]:
    nodes = list(
        db.execute(
            select(SyllabusNode)
            .where(SyllabusNode.subject_code == subject_code)
            .order_by(SyllabusNode.name)
        ).scalars().all()
    )
    if not nodes:
        return []
    parent_ids = {n.parent_id for n in nodes if n.parent_id is not None}
    return [n for n in nodes if n.id not in parent_ids]

def update(
    self,
    db: Session,
    *,
    actor: User,
    item_id: uuid.UUID,
    stem: str | None = None,
    q_type: str | None = None,
    choices_json: list[dict] | None = None,
    answer_key: str | None = None,
    subject_code: str | None = None,
    knowledge_node_id: uuid.UUID | None | object = _UNSET,
    difficulty: int | None = None,
    analysis_text: str | None | object = _UNSET,
) -> QuestionBankItem:
    item = self._get_mutable_item(db, actor=actor, item_id=item_id)
    if item.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "disable question before editing")

    if not any(v is not _UNSET for v in (stem, q_type, choices_json, answer_key, subject_code, knowledge_node_id, difficulty, analysis_text)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no fields to update")

    effective_subject = subject_code if subject_code is not None else item.subject_code

    if stem is not None:
        item.stem = stem.strip()
    if q_type is not None:
        item.q_type = q_type
    if choices_json is not None:
        item.choices_json = choices_json
    if answer_key is not None:
        item.answer_key = answer_key
    if subject_code is not None:
        item.subject_code = subject_code
    if difficulty is not None:
        item.difficulty = difficulty
    if analysis_text is not _UNSET:
        item.analysis_text = analysis_text

    if knowledge_node_id is not _UNSET:
        if knowledge_node_id is None:
            item.knowledge_node_id = None
        else:
            node = db.get(SyllabusNode, knowledge_node_id)
            if node is None or node.subject_code != effective_subject:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid knowledge node for subject")
            leaves = {n.id for n in self.list_leaf_knowledge_nodes(db, subject_code=effective_subject)}
            if node.id not in leaves:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "knowledge node must be a leaf")
            item.knowledge_node_id = node.id
    elif subject_code is not None and item.knowledge_node_id is not None:
        node = db.get(SyllabusNode, item.knowledge_node_id)
        if node is None or node.subject_code != effective_subject:
            item.knowledge_node_id = None

    if item.status in ("rejected", "disabled"):
        item.status = "pending_review"
        item.reviewed_by = None
        item.reviewed_at = None

    db.flush()
    return item
```

Add module-level sentinel `_UNSET = object()` so PATCH can distinguish omitted vs explicit `null` for optional nullable fields.

- [ ] **Step 4: Run service tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_question_bank_service.py -q -k "leaf or update"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question_bank.py backend/tests/test_question_bank_service.py
git commit -m "feat(question-bank): add update service and leaf node listing"
```

---

### Task 3: HTTP API — knowledge-nodes + PATCH

**Files:**
- Modify: `backend/app/routers/org_question_bank.py`
- Test: `backend/tests/test_question_bank_api.py`

**Interfaces:**
- Consumes: `QuestionBankService.update`, `list_leaf_knowledge_nodes`, existing `_single_item_out`
- Produces routes:
  - `GET /org/question-bank/knowledge-nodes?subject_code=math` → `list[KnowledgeNodeOptionOut]`
  - `PATCH /org/question-bank/{item_id}` → `QuestionBankItemOut`

- [ ] **Step 1: Write failing API tests**

```python
def test_list_knowledge_nodes_returns_leaves(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="nodes-admin@example.com")
    parent = SyllabusNode(subject_code="math", name="高数", parent_id=None, weight=1)
    db_session.add(parent)
    db_session.flush()
    leaf = SyllabusNode(subject_code="math", name="多元函数", parent_id=parent.id, weight=1)
    db_session.add(leaf)
    db_session.commit()
    headers = _headers(client, admin.email)

    resp = client.get("/org/question-bank/knowledge-nodes?subject_code=math", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["id"] == str(leaf.id))
    assert row["name"] == "多元函数"
    assert row["parent_name"] == "高数"


def test_patch_question_bank_item(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="patch-admin@example.com")
    headers = _headers(client, admin.email)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(source_type="ocr_import"),
        headers=headers,
    )
    assert created.status_code == 201
    item_id = created.json()["id"]

    patched = client.patch(
        f"/org/question-bank/{item_id}",
        json={"stem": "Patched stem", "difficulty": 4},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["stem"] == "Patched stem"
    assert patched.json()["difficulty"] == 4
    assert patched.json()["status"] == "pending_review"


def test_patch_active_question_returns_409(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="patch-active@example.com")
    headers = _headers(client, admin.email)
    created = client.post("/org/question-bank", json=_question_payload(), headers=headers)
    item_id = created.json()["id"]

    resp = client.patch(
        f"/org/question-bank/{item_id}",
        json={"stem": "Cannot"},
        headers=headers,
    )
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && .venv/bin/python -m pytest tests/test_question_bank_api.py::test_list_knowledge_nodes_returns_leaves -v`
Expected: FAIL (404)

- [ ] **Step 3: Add routes (order matters)**

Place **before** `@router.post("/{item_id}/approve")`:

```python
@router.get("/knowledge-nodes", response_model=list[KnowledgeNodeOptionOut])
def list_knowledge_nodes(
    subject_code: str,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> list[KnowledgeNodeOptionOut]:
    nodes = QuestionBankService().list_leaf_knowledge_nodes(db, subject_code=subject_code)
    parent_ids = {n.parent_id for n in nodes if n.parent_id}
    parents = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(select(SyllabusNode).where(SyllabusNode.id.in_(parent_ids))).scalars()
        }
    out: list[KnowledgeNodeOptionOut] = []
    for node in nodes:
        parent = parents.get(node.parent_id) if node.parent_id else None
        out.append(
            KnowledgeNodeOptionOut(
                id=node.id,
                name=node.name,
                parent_name=parent.name if parent else None,
            )
        )
    return out


@router.patch("/{item_id}", response_model=QuestionBankItemOut)
def update_question(
    item_id: uuid.UUID,
    payload: QuestionBankUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    data = payload.model_dump(exclude_unset=True)
    item = QuestionBankService().update(
        db,
        actor=actor,
        item_id=item_id,
        stem=data.get("stem"),
        q_type=data.get("q_type"),
        choices_json=data.get("choices"),
        answer_key=data.get("answer_key"),
        subject_code=data.get("subject_code"),
        knowledge_node_id=data["knowledge_node_id"] if "knowledge_node_id" in data else _UNSET,
        difficulty=data.get("difficulty"),
        analysis_text=data["analysis_text"] if "analysis_text" in data else _UNSET,
    )
    db.commit()
    db.refresh(item)
    return _single_item_out(db, item)
```

Import `QuestionBankUpdateRequest`, `KnowledgeNodeOptionOut`, `SyllabusNode`, `select`; share `_UNSET` from service or duplicate sentinel in router.

- [ ] **Step 4: Run API tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_question_bank_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/org_question_bank.py backend/tests/test_question_bank_api.py
git commit -m "feat(question-bank): add PATCH and knowledge-nodes API"
```

---

### Task 4: Frontend API client

**Files:**
- Modify: `frontend/src/api/questionBank.ts`

**Interfaces:**
- Produces:
  - `KnowledgeNodeOption { id, name, parent_name }`
  - `listKnowledgeNodes(subject_code: string)`
  - `updateQuestion(itemId: string, body: QuestionBankUpdate)`

- [ ] **Step 1: Add types + functions**

```typescript
export type KnowledgeNodeOption = {
  id: string;
  name: string;
  parent_name: string | null;
};

export type QuestionBankUpdate = {
  stem?: string;
  q_type?: string;
  choices?: Array<{ key: string; text: string }>;
  answer_key?: string;
  subject_code?: string;
  knowledge_node_id?: string | null;
  difficulty?: number;
  analysis_text?: string | null;
};

export function listKnowledgeNodes(subjectCode: string) {
  const params = new URLSearchParams({ subject_code: subjectCode });
  return api<KnowledgeNodeOption[]>(`/org/question-bank/knowledge-nodes?${params}`);
}

export function updateQuestion(itemId: string, body: QuestionBankUpdate) {
  return api<QuestionBankItem>(`/org/question-bank/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/questionBank.ts
git commit -m "feat(question-bank): add update and knowledge-node API client"
```

---

### Task 5: KnowledgeNodeSelect component

**Files:**
- Create: `frontend/src/components/questionBank/KnowledgeNodeSelect.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

**Interfaces:**
- Consumes: `listKnowledgeNodes(subjectCode)`
- Props: `{ subjectCode: string; value: string | null; onChange: (id: string | null) => void; disabled?: boolean }`

- [ ] **Step 1: Write failing test**

```typescript
it("loads knowledge nodes for selected subject", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/org/question-bank/knowledge-nodes")) {
      return new Response(
        JSON.stringify([
          { id: "n1", name: "多元函数", parent_name: "高数" },
        ]),
        { status: 200 },
      );
    }
    if (url.includes("/org/question-bank")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <KnowledgeNodeSelect subjectCode="math" value={null} onChange={() => {}} />
    </QueryClientProvider>,
  );

  await waitFor(() =>
    expect(screen.getByRole("option", { name: "高数 / 多元函数" })).toBeTruthy(),
  );
});
```

- [ ] **Step 2: Implement component**

Use `<select>` with filter `<input>` (native, no new deps): fetch via `useQuery`, options labeled `parent_name ? \`${parent_name} / ${name}\` : name`, include empty option「未标注」.

- [ ] **Step 3: Run test**

Run: `cd frontend && npm test -- --run tests/QuestionBank.test.tsx -t knowledge`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/questionBank/KnowledgeNodeSelect.tsx frontend/tests/QuestionBank.test.tsx
git commit -m "feat(question-bank): add knowledge node select component"
```

---

### Task 6: Edit modal + list/detail entry points

**Files:**
- Create: `frontend/src/components/questionBank/QuestionBankEditForm.tsx`
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

**Interfaces:**
- Consumes: `updateQuestion`, `KnowledgeNodeSelect`, existing `parseChoices`, `MathText`
- Props: `{ item: QuestionBankItem; onClose: () => void; onSaved: () => void }`

- [ ] **Step 1: Extract shared form fields**

`QuestionBankEditForm` holds stem/qType/choicesText/answerKey/subject/difficulty/analysis/knowledgeNodeId state, previews, and `KnowledgeNodeSelect`. On subject change, clear node if incompatible.

- [ ] **Step 2: Wire edit entry**

In `QuestionBankPage`:
- Add `editItem` state
- Show「编辑」when `item.status !== "active"` and `canMutate`
- Detail drawer「编辑」opens modal with `QuestionBankEditForm`
- `updateMutation` calls `updateQuestion`, then `resetList()` + invalidate queries

- [ ] **Step 3: Write test — edit saves via PATCH**

Mock PATCH returning updated item; click「编辑」→ change stem → save; assert fetch called with PATCH.

- [ ] **Step 4: Run tests**

Run: `cd frontend && npm test -- --run tests/QuestionBank.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/questionBank/QuestionBankEditForm.tsx frontend/src/components/questionBank/QuestionBankPage.tsx frontend/tests/QuestionBank.test.tsx
git commit -m "feat(question-bank): add edit modal for non-active items"
```

---

### Task 7: Create-confirm uses KnowledgeNodeSelect

**Files:**
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

- [ ] **Step 1: Replace read-only knowledge display on create confirm**

Use `KnowledgeNodeSelect` bound to `confirmation.knowledge_node_id`; on change update `confirmation` state.

- [ ] **Step 2: Test — enrich flow can change knowledge node before create**

Extend enrich test: after confirm screen, change select, assert create POST body includes chosen `knowledge_node_id`.

- [ ] **Step 3: Run tests + manual smoke**

Run: `cd frontend && npm test -- --run tests/QuestionBank.test.tsx`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/questionBank/QuestionBankPage.tsx frontend/tests/QuestionBank.test.tsx
git commit -m "feat(question-bank): use knowledge node picker on create confirm"
```

---

### Task 8: Mark spec implemented + final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-08-10-question-bank-edit-node-picker-design.md`

- [ ] **Step 1: Update spec status**

Change `**状态：** 待实现` → `**状态：** 已实现`

- [ ] **Step 2: Run full test suites**

```bash
cd backend && .venv/bin/python -m pytest tests/test_question_bank_api.py tests/test_question_bank_service.py -q
cd frontend && npm test -- --run tests/QuestionBank.test.tsx
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-10-question-bank-edit-node-picker-design.md
git commit -m "docs: mark question bank edit and node picker spec implemented"
```

---

## Spec coverage checklist

| Spec § | Task |
|--------|------|
| §3 权限/状态机 | Task 2, 3, 6 |
| §4.1 PATCH | Task 2, 3 |
| §4.2 knowledge-nodes | Task 2, 3, 5 |
| §5.1 编辑入口 | Task 6 |
| §5.2 编辑弹窗 + 预览 | Task 6 |
| §5.3 新建确认选择器 | Task 7 |
| §5.4 错误展示 | Task 3, 6 |
| §7 测试要点 | Tasks 2–7 |
| §9 验收 | Task 8 |
