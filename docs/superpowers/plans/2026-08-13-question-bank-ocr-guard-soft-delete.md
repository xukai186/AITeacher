# Question Bank OCR Guard + Soft Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block OCR-mode create until recognition succeeded with a valid org image asset, and let admin/staff soft-delete non-active question bank items (`status=deleted`) so they disappear from list, dedupe, and selection.

**Architecture:** Enforce `ocr_import` asset ownership in `QuestionBankService.create`. Add `delete()` that sets `status=deleted` for `pending_review`/`rejected`/`disabled` only; `_get_mutable_item` rejects already-deleted rows; `list` and `find_exact_duplicate` always exclude `deleted`. Frontend disables「智能补全」until OCR success, and adds a confirmed「删除」action via existing `POST /{id}/{action}` review pattern.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest; React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-08-13-question-bank-ocr-guard-soft-delete-design.md`

## Global Constraints

- Soft delete only: `status = deleted` (no hard delete, no `deleted_at`)
- Deletable statuses: `pending_review` / `rejected` / `disabled`; `active` must be disabled first (409)
- `deleted` items: any further mutate (edit/approve/reject/disable/delete) → 409
- List always excludes `deleted` (including `?status=deleted` → empty; no recycle bin)
- Exact dedupe ignores `deleted` (same stem may be recreated)
- Do not mutate historical `SelfTestQuestion` snapshots
- `ocr_import` requires `source_image_asset_id` belonging to `actor.org_id` (422 otherwise)
- OCR frontend: 「智能补全」disabled until OCR mutation succeeded and `sourceImageAssetId` is set
- Permissions: reuse `_get_mutable_item` (staff: org only; admin: org + global)
- Python tests: `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest …`
- No restore UI/API this phase

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/question_bank.py` | OCR asset check on create; `delete()`; list/dedupe exclude deleted; block mutate of deleted |
| `backend/app/routers/org_question_bank.py` | `POST /{item_id}/delete` via existing `_review` |
| `backend/tests/test_question_bank_service.py` | Service tests + MediaAsset helper for ocr_import |
| `backend/tests/test_question_bank_api.py` | HTTP delete + ocr_import 422/201 |
| `frontend/src/api/questionBank.ts` | `deleted` status; `reviewQuestion` accepts `"delete"` |
| `frontend/src/components/questionBank/QuestionBankPage.tsx` | OCR enrich gate; list/detail delete + confirm |
| `frontend/tests/QuestionBankOcr.test.tsx` | Enrich disabled until OCR success |
| `frontend/tests/QuestionBank.test.tsx` | Delete confirm + POST |
| `docs/superpowers/specs/2026-08-13-question-bank-ocr-guard-soft-delete-design.md` | Mark 已实现 when done |

---

### Task 1: Service — OCR import requires org-owned image asset

**Files:**
- Modify: `backend/app/services/question_bank.py`
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Consumes: existing `QuestionBankService.create(..., source_type, source_image_asset_id, actor)`
- Produces: create raises HTTP 422 when `source_type == "ocr_import"` and asset is missing or `asset.org_id != actor.org_id`

- [ ] **Step 1: Add MediaAsset helper and failing OCR validation tests**

In `backend/tests/test_question_bank_service.py`, import `MediaAsset` and add helpers after `_create`:

```python
from app.models import MediaAsset, SyllabusNode, UserRole


def _media_asset(db_session, actor, org_id=None):
    asset = MediaAsset(
        org_id=org_id or actor.org_id,
        created_by=actor.id,
        content_type="image/png",
        storage_path=f"/tmp/{uuid.uuid4()}.png",
    )
    db_session.add(asset)
    db_session.flush()
    return asset
```

Update `_create` so existing `ocr_import` tests keep passing once validation exists: if `source_type == "ocr_import"` and `source_image_asset_id` is not in overrides, attach `_media_asset(db_session, actor).id`.

Then add:

```python
def test_ocr_import_requires_source_image_asset(db_session):
    admin, _ = _admin(db_session)
    with pytest.raises(HTTPException) as exc:
        _create(
            QuestionBankService(),
            db_session,
            admin,
            source_type="ocr_import",
            source_image_asset_id=None,
        )
    assert exc.value.status_code == 422


def test_ocr_import_rejects_foreign_org_asset(db_session):
    admin, _ = _admin(db_session)
    other = make_org(db_session, "Other")
    foreign_admin = make_user(db_session, other, UserRole.org_admin)
    asset = _media_asset(db_session, foreign_admin, org_id=other.id)
    with pytest.raises(HTTPException) as exc:
        _create(
            QuestionBankService(),
            db_session,
            admin,
            source_type="ocr_import",
            source_image_asset_id=asset.id,
        )
    assert exc.value.status_code == 422


def test_ocr_import_accepts_actor_org_asset(db_session):
    admin, _ = _admin(db_session)
    asset = _media_asset(db_session, admin)
    item = _create(
        QuestionBankService(),
        db_session,
        admin,
        source_type="ocr_import",
        source_image_asset_id=asset.id,
    )
    assert item.status == "pending_review"
    assert item.source_image_asset_id == asset.id
```

`_create` must **not** auto-create an asset when `source_image_asset_id=None` is explicitly passed (use `"source_image_asset_id" not in overrides` for auto-attach).

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_service.py::test_ocr_import_requires_source_image_asset -v`

Expected: FAIL (create succeeds / no 422)

- [ ] **Step 3: Validate OCR asset in create**

In `question_bank.py`, import `MediaAsset`. After `_authorize_create(...)` and before duplicate check:

```python
if source_type == "ocr_import":
    if source_image_asset_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "ocr import requires source image asset",
        )
    asset = db.get(MediaAsset, source_image_asset_id)
    if asset is None or asset.org_id != actor.org_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid source image asset",
        )
```

- [ ] **Step 4: Run OCR-related service tests**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_service.py -q`

Expected: PASS (including existing `ocr_import` creates via helper)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question_bank.py backend/tests/test_question_bank_service.py
git commit -m "feat(question-bank): require org image asset for ocr import"
```

---

### Task 2: Service — soft delete, hide from list/dedupe, block mutate

**Files:**
- Modify: `backend/app/services/question_bank.py`
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Produces:
  - `QuestionBankService.delete(db, *, actor: User, item_id: UUID) -> QuestionBankItem`
  - Allowed from `pending_review` / `rejected` / `disabled` → `deleted` (keep `reviewed_by` / `reviewed_at`)
  - `active` or already `deleted` → 409
  - `list(...)` always `status != "deleted"`
  - `find_exact_duplicate(...)` ignores `deleted`

- [ ] **Step 1: Write failing service tests**

```python
def test_delete_pending_review_sets_deleted(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    deleted = svc.delete(db_session, actor=admin, item_id=item.id)
    assert deleted.status == "deleted"


def test_delete_active_is_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin)
    with pytest.raises(HTTPException) as exc:
        svc.delete(db_session, actor=admin, item_id=item.id)
    assert exc.value.status_code == 409


def test_delete_already_deleted_is_rejected(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    item = _create(svc, db_session, admin, source_type="ocr_import")
    svc.delete(db_session, actor=admin, item_id=item.id)
    with pytest.raises(HTTPException) as exc:
        svc.delete(db_session, actor=admin, item_id=item.id)
    assert exc.value.status_code == 409


def test_list_excludes_deleted_even_when_status_filter_is_deleted(db_session):
    admin, _ = _admin(db_session)
    svc = QuestionBankService()
    live = _create(svc, db_session, admin, stem="Keep me")
    doomed = _create(svc, db_session, admin, source_type="ocr_import", stem="Drop me")
    svc.delete(db_session, actor=admin, item_id=doomed.id)
    db_session.flush()

    ids = {item.id for item in svc.list(db_session, viewer=admin)}
    assert live.id in ids
    assert doomed.id not in ids
    assert svc.list(db_session, viewer=admin, status="deleted") == []


def test_dedupe_ignores_deleted_so_stem_can_be_recreated(db_session):
    admin, org = _admin(db_session)
    svc = QuestionBankService()
    original = _create(svc, db_session, admin, source_type="ocr_import", stem="Same stem")
    svc.delete(db_session, actor=admin, item_id=original.id)
    db_session.flush()

    assert (
        svc.find_exact_duplicate(
            db_session, scope="org", org_id=org.id, q_type="single_choice", stem="Same stem"
        )
        is None
    )
    recreated = _create(svc, db_session, admin, stem="Same stem")
    assert recreated.status == "active"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_service.py::test_delete_pending_review_sets_deleted -v`

Expected: FAIL (`delete` missing)

- [ ] **Step 3: Implement delete + list/dedupe/mutate guards**

In `_get_mutable_item`, after the org/global permission checks and before `return item`:

```python
if item.status == "deleted":
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        "question bank item is deleted",
    )
```

Add `delete` next to `disable`:

```python
def delete(
    self,
    db: Session,
    *,
    actor: User,
    item_id: uuid.UUID,
) -> QuestionBankItem:
    item = self._get_mutable_item(db, actor=actor, item_id=item_id)
    if item.status not in ("pending_review", "rejected", "disabled"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "disable question before deleting",
        )
    item.status = "deleted"
    db.flush()
    return item
```

In `list`, after `stmt = select(QuestionBankItem).where(visibility)`:

```python
stmt = stmt.where(QuestionBankItem.status != "deleted")
```

In `find_exact_duplicate` `.where(...)` add:

```python
QuestionBankItem.status != "deleted",
```

- [ ] **Step 4: Run service tests**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_service.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question_bank.py backend/tests/test_question_bank_service.py
git commit -m "feat(question-bank): soft-delete non-active items"
```

---

### Task 3: HTTP API — POST delete + ocr_import asset errors

**Files:**
- Modify: `backend/app/routers/org_question_bank.py`
- Test: `backend/tests/test_question_bank_api.py`

**Interfaces:**
- Consumes: `QuestionBankService.delete`, existing `_review`
- Produces: `POST /org/question-bank/{item_id}/delete` → `QuestionBankItemOut`

- [ ] **Step 1: Write failing API tests**

In `backend/tests/test_question_bank_api.py`, import `MediaAsset` and add:

```python
def _media_asset(db_session, actor):
    asset = MediaAsset(
        org_id=actor.org_id,
        created_by=actor.id,
        content_type="image/png",
        storage_path=f"/tmp/{actor.id}.png",
    )
    db_session.add(asset)
    db_session.commit()
    return asset


def test_ocr_import_without_asset_returns_422(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="ocr-no-asset@example.com")
    headers = _headers(client, admin.email)
    resp = client.post(
        "/org/question-bank",
        json=_question_payload(source_type="ocr_import"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_ocr_import_with_org_asset_returns_201(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="ocr-asset@example.com")
    asset = _media_asset(db_session, admin)
    headers = _headers(client, admin.email)
    resp = client.post(
        "/org/question-bank",
        json=_question_payload(
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending_review"
    assert resp.json()["source_image_asset_id"] == str(asset.id)


def test_delete_pending_question(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="delete-admin@example.com")
    asset = _media_asset(db_session, admin)
    headers = _headers(client, admin.email)
    created = client.post(
        "/org/question-bank",
        json=_question_payload(
            source_type="ocr_import",
            source_image_asset_id=str(asset.id),
        ),
        headers=headers,
    )
    item_id = created.json()["id"]

    deleted = client.post(f"/org/question-bank/{item_id}/delete", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"

    listed = client.get("/org/question-bank", headers=headers)
    assert listed.status_code == 200
    assert item_id not in {row["id"] for row in listed.json()}


def test_delete_active_question_returns_409(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="delete-active@example.com")
    headers = _headers(client, admin.email)
    created = client.post("/org/question-bank", json=_question_payload(), headers=headers)
    resp = client.post(
        f"/org/question-bank/{created.json()['id']}/delete",
        headers=headers,
    )
    assert resp.status_code == 409
```

Fix existing API tests that POST `source_type="ocr_import"` without an asset (`test_staff_can_enrich_create_and_reject_org_question`, `test_patch_question_bank_item`) to attach `_media_asset` the same way.

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_api.py::test_delete_pending_question -v`

Expected: FAIL (404, no `/delete` route)

- [ ] **Step 3: Add delete route**

After `disable_question`, add:

```python
@router.post("/{item_id}/delete", response_model=QuestionBankItemOut)
def delete_question(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionBankItemOut:
    return _review("delete", item_id, db, actor)
```

`_review` already does `getattr(service, action)(...)`.

- [ ] **Step 4: Run API tests**

Run: `cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_api.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/org_question_bank.py backend/tests/test_question_bank_api.py
git commit -m "feat(question-bank): add delete API and ocr-import asset HTTP checks"
```

---

### Task 4: Frontend API client — delete action + deleted status

**Files:**
- Modify: `frontend/src/api/questionBank.ts`

**Interfaces:**
- Produces: `QuestionStatus` includes `"deleted"`; `reviewQuestion(itemId, "delete")`

- [ ] **Step 1: Extend types**

```typescript
export type QuestionStatus = "pending_review" | "active" | "rejected" | "disabled" | "deleted";
```

```typescript
export function reviewQuestion(
  itemId: string,
  action: "approve" | "reject" | "disable" | "delete",
) {
  return api<QuestionBankItem>(`/org/question-bank/${itemId}/${action}`, {
    method: "POST",
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/questionBank.ts
git commit -m "feat(question-bank): add delete action to API client"
```

---

### Task 5: Frontend — OCR enrich guard

**Files:**
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBankOcr.test.tsx`

**Interfaces:**
- Consumes: `sourceImageAssetId`, `ocrMutation.isSuccess`, `createMode`
- Produces: OCR mode disables「智能补全」until recognition succeeded with an asset id

- [ ] **Step 1: Write failing test**

Add to `QuestionBankOcr.test.tsx` (keep existing happy-path test; its fetch mock already covers upload/ocr/enrich/create):

```typescript
it("disables enrich until OCR recognition succeeds", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/org/question-bank")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
  fireEvent.click(screen.getByRole("button", { name: "图片识别添加" }));
  fireEvent.change(screen.getByLabelText("题干"), {
    target: { value: "手工填的题干" },
  });
  fireEvent.change(screen.getByLabelText("参考答案"), {
    target: { value: "1" },
  });

  const enrich = screen.getByRole("button", { name: "智能补全" });
  expect(enrich).toBeDisabled();
  expect(screen.getByText("请先完成图片识别")).toBeTruthy();
});
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm test -- --run tests/QuestionBankOcr.test.tsx -t "disables enrich"`

Expected: FAIL (button still enabled / hint missing)

- [ ] **Step 3: Gate enrich in QuestionBankPage**

Before `onEnrich`, compute:

```typescript
const ocrReady = createMode !== "ocr" || Boolean(sourceImageAssetId);

const onEnrich = (event: FormEvent) => {
  event.preventDefault();
  if (!ocrReady) return;
  enrichMutation.mutate(questionDraft());
};
```

On the enrich submit button:

```tsx
<button
  type="submit"
  disabled={enrichMutation.isPending || !ocrReady}
  className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
>
  {enrichMutation.isPending ? "补全中…" : "智能补全"}
</button>
{createMode === "ocr" && !ocrReady ? (
  <p className="text-sm text-slate-500">请先完成图片识别</p>
) : null}
```

`selectCreateMode("manual")` already clears `sourceImageAssetId` and resets `ocrMutation`.

- [ ] **Step 4: Run OCR tests**

Run: `cd frontend && npm test -- --run tests/QuestionBankOcr.test.tsx`

Expected: PASS (guard + existing upload/recognize/create path)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/questionBank/QuestionBankPage.tsx frontend/tests/QuestionBankOcr.test.tsx
git commit -m "feat(question-bank): block enrich until OCR succeeds"
```

---

### Task 6: Frontend — delete entry on list and detail

**Files:**
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

**Interfaces:**
- Consumes: `reviewQuestion(id, "delete")`
- Produces: 「删除」when `canMutate` and status in `pending_review` / `rejected` / `disabled`; confirm copy exactly: `删除后列表不再显示，确认删除？`

- [ ] **Step 1: Write failing test**

Add to `QuestionBank.test.tsx`. Mock `window.confirm` true. List one `pending_review` item; click「删除」; assert POST `.../q-del/delete`.

```typescript
it("soft-deletes a pending question after confirm", async () => {
  const item = {
    id: "q-del",
    scope: "org" as const,
    org_id: "org-1",
    subject_code: "math",
    knowledge_node_id: null,
    q_type: "short_answer",
    stem: "To delete",
    choices: null,
    answer_key: "1",
    analysis_text: null,
    difficulty: 2,
    source_type: "ocr_import",
    status: "pending_review" as const,
    created_at: "2026-01-01T00:00:00Z",
  };
  vi.spyOn(window, "confirm").mockReturnValue(true);

  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/org/question-bank/knowledge-nodes")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }
    if (url.includes("/org/question-bank/q-del/delete") && init?.method === "POST") {
      return new Response(JSON.stringify({ ...item, status: "deleted" }), { status: 200 });
    }
    if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
      return new Response(JSON.stringify([item]), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderPage();
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "删除" })).toBeTruthy(),
  );
  fireEvent.click(screen.getByRole("button", { name: "删除" }));

  await waitFor(() => {
    expect(window.confirm).toHaveBeenCalledWith("删除后列表不再显示，确认删除？");
    const del = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/org/question-bank/q-del/delete") && init?.method === "POST",
    );
    expect(del).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd frontend && npm test -- --run tests/QuestionBank.test.tsx -t "soft-deletes"`

Expected: FAIL (no 删除 button)

- [ ] **Step 3: Wire delete UI**

Extend `reviewMutation` action type to include `"delete"`.

Helper:

```typescript
const DELETABLE = new Set(["pending_review", "rejected", "disabled"]);

const requestDelete = (id: string) => {
  if (!window.confirm("删除后列表不再显示，确认删除？")) return false;
  reviewMutation.mutate({ id, action: "delete" });
  return true;
};
```

In the list actions, after the edit button (same `canMutate` scope):

```tsx
{DELETABLE.has(item.status) && canMutate && (
  <button
    type="button"
    onClick={() => requestDelete(item.id)}
    className="text-red-700 underline"
  >
    删除
  </button>
)}
```

On `QuestionBankItemDetail`, add optional `onDelete` / `canDelete`. In the header next to 编辑:

```tsx
{canDelete && onDelete ? (
  <button type="button" onClick={onDelete} className="text-sm text-red-700 underline">
    删除
  </button>
) : null}
```

When rendering detail:

```tsx
canDelete={
  DELETABLE.has(detailItem.status) &&
  (role === "org_admin" || detailItem.scope === "org")
}
onDelete={() => {
  if (requestDelete(detailItem.id)) setDetailItem(null);
}}
```

Edit remains `status !== "active"`; deleted rows never appear in the list.

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run tests/QuestionBank.test.tsx tests/QuestionBankOcr.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/questionBank/QuestionBankPage.tsx frontend/tests/QuestionBank.test.tsx
git commit -m "feat(question-bank): add confirmed soft-delete action"
```

---

### Task 7: Mark spec implemented + final verification

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-question-bank-ocr-guard-soft-delete-design.md`

- [ ] **Step 1: Update spec status**

Change `**状态：** 待实现` → `**状态：** 已实现`

- [ ] **Step 2: Run full related suites**

```bash
cd backend && /Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_api.py tests/test_question_bank_service.py -q
cd frontend && npm test -- --run tests/QuestionBank.test.tsx tests/QuestionBankOcr.test.tsx
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-13-question-bank-ocr-guard-soft-delete-design.md
git commit -m "docs: mark question bank OCR guard and soft-delete spec implemented"
```

---

## Spec coverage checklist

| Spec § | Task |
|--------|------|
| §3.1 状态机 / 409 | Task 2, 3 |
| §3.2 POST delete | Task 3, 4, 6 |
| §3.3 列表排除 / 去重忽略 | Task 2, 3 |
| §3.3 自测仅 active | already in assembler; no code change |
| §3.4 删除 UI + confirm | Task 6 |
| §4.1 OCR 前端守卫 | Task 5 |
| §4.2 ocr_import 资产校验 | Task 1, 3 |
| §5 错误码 | Tasks 1–3 |
| §7 测试要点 | Tasks 1–6 |
| §9 验收 | Task 7 |
