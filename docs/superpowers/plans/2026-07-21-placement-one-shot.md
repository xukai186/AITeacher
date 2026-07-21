# Placement One-Shot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each placement subject one-shot: block re-start after submit, expose `submitted` on list API, and show a disabled「已完成」button on the student workspace.

**Architecture:** Harden `PlacementService.start` / `list_papers` / `submit` for Chinese one-shot errors and accurate status labels; Workspace loads `GET /student/placement` and gates the start button by current subject status. No new tables; track-change invalidation remains the only retake path.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-07-15-placement-one-shot-design.md`

## Global Constraints

- Per-subject one-shot only; unfinished subjects remain startable
- Workspace completed CTA is gray「已完成」, not clickable, does not open the old paper
- Results stay on report / wrong-book / paper center — no new workspace「查看结果」
- Structure-change invalidation via `invalidate_placement_on_track_change` remains the retake exception
- `GET /student/placement/{paper_id}` direct links may still open (scheme 1)

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/placement.py` | Reject start when submitted; list status via `_paper_status_label`; Chinese submit error |
| `backend/tests/test_placement_flow.py` | API tests for one-shot start / list status |
| `frontend/src/pages/student/Workspace.tsx` | Load placement list; disable button when current subject submitted |
| `frontend/src/api/placement.ts` | Existing `listPlacementPapers` (no schema change required if status string is enough) |
| `frontend/tests/WorkspaceTasks.test.tsx` | Mock placement list; assert「已完成」disabled |

---

### Task 1: Backend reject re-start and expose `submitted` status

**Files:**
- Modify: `backend/app/services/placement.py`
- Modify: `backend/tests/test_placement_flow.py`
- Test: `backend/tests/test_placement_flow.py`

**Interfaces:**
- Consumes: `PlacementService._is_submitted`, `_paper_status_label`, `_prepare_paper_for_start`
- Produces: `start(...)` raises 400 with `该科摸底已完成` / `全部科目摸底已完成`; `list_papers` returns `status="submitted"` when submission exists; `submit` detail `该科摸底已完成`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_placement_flow.py` (reuse `_seed_student`, `start_placement_and_wait`, `_token`, `_placement_answer_content`):

```python
def test_start_rejects_already_submitted_subject(client, db_session):
    student = _seed_student(db_session)
    token = _token(client, student.email)
    headers = {"Authorization": f"Bearer {token}"}
    start_placement_and_wait(client, token, db_session=db_session, subject_code="english")
    paper_id = client.get("/student/placement", headers=headers).json()[0]["id"]
    questions = (
        db_session.execute(select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id))
        .scalars()
        .all()
    )
    client.post(
        f"/student/placement/{paper_id}/submit",
        headers=headers,
        json={
            "answers": [
                {"question_id": str(q.id), "content": _placement_answer_content(q)}
                for q in questions
            ]
        },
    )
    again = client.post(
        "/student/placement/start",
        headers=headers,
        json={"subject_code": "english"},
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "该科摸底已完成"

    listed = client.get("/student/placement", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "submitted"

    no_subject = client.post("/student/placement/start", headers=headers, json={})
    assert no_subject.status_code == 400
    assert no_subject.json()["detail"] == "全部科目摸底已完成"
```

If `start_placement_and_wait` does not accept `subject_code`, pass it via the existing start payload helper in `tests/paper_gen_job_helpers.py` or hardcode the English-only seed student path (seed already enables only `english`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_placement_flow.py::test_start_rejects_already_submitted_subject -q`

Expected: FAIL — start still returns 200 and/or list status is not `submitted`.

- [ ] **Step 3: Implement placement service changes**

In `PlacementService.start`, after resolving `target_code` and before `_prepare_paper_for_start`:

```python
        existing_paper = db.execute(
            select(PlacementPaper).where(
                PlacementPaper.student_user_id == student_user_id,
                PlacementPaper.subject_code == target_code,
            )
        ).scalar_one_or_none()
        if existing_paper is not None and cls._is_submitted(
            db, existing_paper.id, student_user_id
        ):
            if subject_code is not None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "该科摸底已完成")
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "全部科目摸底已完成")
```

Also change the auto-pick branch so when every subject is submitted it raises instead of falling back to `enabled_codes[0]`:

```python
        if target_code is None:
            for code in enabled_codes:
                paper = db.execute(
                    select(PlacementPaper).where(
                        PlacementPaper.student_user_id == student_user_id,
                        PlacementPaper.subject_code == code,
                    )
                ).scalar_one_or_none()
                if paper is None or not cls._is_submitted(db, paper.id, student_user_id):
                    target_code = code
                    break
            if target_code is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "全部科目摸底已完成")
```

In `list_papers`, replace `status=p.status` with:

```python
                status=cls._paper_status_label(db, p, student_user_id),
```

In `submit`, change:

```python
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "该科摸底已完成")
```

Remove or bypass the early `return paper, None` path in `_prepare_paper_for_start` for submitted papers only if `start` now never calls it for submitted subjects (preferred: keep the guard but make it unreachable from `start`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_placement_flow.py -q`

Expected: PASS (including the new one-shot test and existing submit/roadmap regressions).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/placement.py backend/tests/test_placement_flow.py
git commit -m "$(cat <<'EOF'
fix: reject placement re-start after subject is submitted

EOF
)"
```

---

### Task 2: Workspace shows disabled「已完成」for submitted subjects

**Files:**
- Modify: `frontend/src/pages/student/Workspace.tsx`
- Modify: `frontend/tests/WorkspaceTasks.test.tsx`
- Test: `frontend/tests/WorkspaceTasks.test.tsx`

**Interfaces:**
- Consumes: `listPlacementPapers()` from `@/api/placement` returning `{ subject_code, status }[]`
- Produces: Workspace start button label/disabled state driven by current subject `status === "submitted"`

- [ ] **Step 1: Extend WorkspaceTasks mocks and add failing assertion**

In `frontend/tests/WorkspaceTasks.test.tsx`, update `mockFetchRouter` to also handle:

```typescript
      if (url.includes("/api/student/roadmap")) {
        return new Response(
          JSON.stringify({
            roadmap_id: null,
            status: null,
            active_version: null,
            pending_version: null,
            generation_job: null,
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/api/student/placement") || /\/api\/student\/placement\?/.test(url)) {
        return new Response(
          JSON.stringify([
            {
              id: "p1",
              subject_code: "english",
              status: "submitted",
              title: "英语摸底",
              created_at: "2026-05-28T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
```

Add test:

```typescript
  it("shows completed placement button when subject is submitted", async () => {
    mockFetchRouter();
    renderWorkspace();
    const btn = await screen.findByRole("button", { name: "已完成" });
    expect(btn).toBeDisabled();
  });
```

Keep existing task/profile tests working (they now need the placement + roadmap mocks too).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run WorkspaceTasks`

Expected: FAIL — button still says「开始摸底测评」or query missing.

- [ ] **Step 3: Implement Workspace gating**

In `Workspace.tsx`:

1. Import `listPlacementPapers` from `@/api/placement`.
2. Add query:

```tsx
  const placements = useQuery({
    queryKey: ["student", "placement", "list"],
    queryFn: listPlacementPapers,
  });
```

3. Derive:

```tsx
  const currentPlacementStatus = (placements.data ?? []).find(
    (p) => p.subject_code === current,
  )?.status;
  const placementDone = currentPlacementStatus === "submitted";
```

4. Update the placement button:

```tsx
          <button
            className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
            disabled={paperGenBusy || !current || profileIncomplete || placementDone}
            onClick={() => start.mutate()}
          >
            {paperGenBusy
              ? "生成题目中…"
              : placementDone
                ? "已完成"
                : "开始摸底测评"}
          </button>
```

5. On successful start navigation unchanged; ensure start mutation `onError` surfaces message (existing error render is fine). After start mutation success path that navigates away is OK; when returning to workspace, list query refetch on mount updates the button. Also invalidate placement list after start succeeds only if still on page — optional. Prefer invalidating in Placement submit success if that page exists; if not in scope, workspace remount/refocus is enough. Minimal: invalidate on Workspace when `start` errors with 400 so stale UI recovers:

```tsx
    onError: () => {
      qc.invalidateQueries({ queryKey: ["student", "placement", "list"] });
    },
```

(Requires `useQueryClient` if not already present.)

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npx vitest run WorkspaceTasks`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/student/Workspace.tsx frontend/tests/WorkspaceTasks.test.tsx
git commit -m "$(cat <<'EOF'
feat: show completed placement state on student workspace

EOF
)"
```

---

### Task 3: Regression sweep and mark spec implemented

**Files:**
- Modify: `docs/superpowers/specs/2026-07-15-placement-one-shot-design.md` (status → 已实现)
- Test: backend placement + frontend WorkspaceTasks

- [ ] **Step 1: Run backend placement-related suite**

Run: `cd backend && uv run pytest tests/test_placement_flow.py tests/test_placement_paper_context.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend WorkspaceTasks**

Run: `cd frontend && npx vitest run WorkspaceTasks`

Expected: PASS.

- [ ] **Step 3: Update spec status**

Change the spec header status from `待实现` to `已实现`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-15-placement-one-shot-design.md
git commit -m "$(cat <<'EOF'
docs: mark placement one-shot spec implemented

EOF
)"
```

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| start submitted subject → 400 `该科摸底已完成` | Task 1 |
| all subjects submitted, no subject_code → 400 `全部科目摸底已完成` | Task 1 |
| list status `submitted` | Task 1 |
| submit Chinese detail | Task 1 |
| Workspace「已完成」disabled | Task 2 |
| No new「查看结果」/ no retake UI | OUT OF SCOPE (no task) |
| Track-change invalidate unchanged | OUT OF SCOPE (no task) |
