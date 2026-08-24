# Question Bank Global Scope Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let org admins filter the existing question-bank list by scope (all / org / global) with a visible scope column, via a server-side `scope` query param so pagination stays correct.

**Architecture:** Extend `QuestionBankService.list` and `GET /org/question-bank` with optional `scope=org|global`. Frontend adds an Admin-only scope filter (default all = omit param) and a scope column; Staff UI unchanged (no filter, no scope column).

**Tech Stack:** FastAPI, SQLAlchemy, pytest; React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-08-24-question-bank-global-scope-filter-design.md`

## Global Constraints

- Product shape: existing question-bank page only (no dedicated platform page)
- Default filter: **全部** (omit `scope` query param — same visibility as today)
- No org ↔ global ownership transfer
- Staff still cannot see global (Staff `scope=global` → empty list, not 403)
- Admin without `scope`: org ∪ global; Staff without `scope`: org only
- Always exclude `deleted`
- Create-form `scope` state in `QuestionBankPage` already exists — list filter must use a **different** state name (e.g. `listScope`)
- Python tests: `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest …`
- Frontend tests: `cd frontend && npx vitest run tests/QuestionBank.test.tsx`

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/question_bank.py` | `list(..., scope: str \| None = None)` filter |
| `backend/app/routers/org_question_bank.py` | Query param `scope` |
| `backend/tests/test_question_bank_service.py` | Service scope filter tests |
| `backend/tests/test_question_bank_api.py` | HTTP scope filter tests |
| `frontend/src/api/questionBank.ts` | `QuestionFilters.scope` |
| `frontend/src/components/questionBank/QuestionBankPage.tsx` | Admin filter + scope column |
| `frontend/tests/QuestionBank.test.tsx` | Admin scope filter behavior |
| `docs/superpowers/specs/2026-08-24-question-bank-global-scope-filter-design.md` | Mark 已实现 |

---

### Task 1: Service — `list` accepts optional `scope`

**Files:**
- Modify: `backend/app/services/question_bank.py`
- Test: `backend/tests/test_question_bank_service.py`

**Interfaces:**
- Consumes: existing `QuestionBankService.list(db, *, viewer, status, subject_code, pending_only, limit, offset)`
- Produces: `list(..., scope: str | None = None)` where `scope` is `"org"`, `"global"`, or `None`

- [ ] **Step 1: Write failing service tests**

Append to `backend/tests/test_question_bank_service.py` (reuse helpers from `test_list_visibility_and_filters`):

```python
def test_list_scope_filter_for_admin_and_staff(db_session):
    admin, org = _admin(db_session)
    staff = _staff(db_session, org)
    svc = QuestionBankService()
    own = _create(svc, db_session, admin, stem="Org only")
    global_item = _create(
        svc,
        db_session,
        admin,
        scope="global",
        org_id=None,
        stem="Global only",
        source_type="admin_manual",
    )
    db_session.flush()

    admin_all = {i.id for i in svc.list(db_session, viewer=admin)}
    admin_org = {i.id for i in svc.list(db_session, viewer=admin, scope="org")}
    admin_global = {i.id for i in svc.list(db_session, viewer=admin, scope="global")}
    staff_global = list(svc.list(db_session, viewer=staff, scope="global"))
    staff_org = {i.id for i in svc.list(db_session, viewer=staff, scope="org")}

    assert admin_all == {own.id, global_item.id}
    assert admin_org == {own.id}
    assert admin_global == {global_item.id}
    assert staff_global == []
    assert staff_org == {own.id}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/bytedance/cursor/AITeacher/backend
.venv/bin/python -m pytest tests/test_question_bank_service.py::test_list_scope_filter_for_admin_and_staff -v
```

Expected: FAIL (`list() got an unexpected keyword argument 'scope'` or assertion fail).

- [ ] **Step 3: Implement `scope` on `list`**

In `QuestionBankService.list`, add parameter `scope: str | None = None`.

After building `visibility` and excluding `deleted`, apply:

```python
        if scope == "org":
            stmt = stmt.where(
                QuestionBankItem.scope == "org",
                QuestionBankItem.org_id == viewer.org_id,
            )
        elif scope == "global":
            if viewer.role != UserRole.org_admin:
                return []
            stmt = stmt.where(QuestionBankItem.scope == "global")
        elif scope is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "unsupported question bank scope filter",
            )
```

Keep existing visibility for `scope is None`. Do not weaken Staff default visibility.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_question_bank_service.py::test_list_scope_filter_for_admin_and_staff tests/test_question_bank_service.py::test_list_visibility_and_filters -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/question_bank.py backend/tests/test_question_bank_service.py
git commit -m "$(cat <<'EOF'
feat(question-bank): filter list by scope in service

EOF
)"
```

---

### Task 2: API — wire `scope` query param

**Files:**
- Modify: `backend/app/routers/org_question_bank.py`
- Test: `backend/tests/test_question_bank_api.py`

**Interfaces:**
- Consumes: `QuestionBankService.list(..., scope=)`
- Produces: `GET /org/question-bank?scope=org|global`

- [ ] **Step 1: Write failing API tests**

In `backend/tests/test_question_bank_api.py`, add helpers as needed (`_seed_user`, `_question_payload`, login headers) following existing patterns:

```python
def test_list_filters_by_scope_for_admin(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="scope-admin@example.com")
    headers = _auth_headers(client, admin.email)
    org_item = client.post(
        "/org/question-bank",
        headers=headers,
        json=_question_payload(scope="org", stem="Org stem"),
    )
    global_item = client.post(
        "/org/question-bank",
        headers=headers,
        json=_question_payload(scope="global", stem="Global stem"),
    )
    assert org_item.status_code == 201
    assert global_item.status_code == 201

    all_ids = {row["id"] for row in client.get("/org/question-bank", headers=headers).json()}
    org_ids = {
        row["id"]
        for row in client.get("/org/question-bank?scope=org", headers=headers).json()
    }
    global_ids = {
        row["id"]
        for row in client.get("/org/question-bank?scope=global", headers=headers).json()
    }

    assert org_item.json()["id"] in all_ids and global_item.json()["id"] in all_ids
    assert org_ids == {org_item.json()["id"]}
    assert global_ids == {global_item.json()["id"]}


def test_staff_scope_global_returns_empty(client, db_session):
    admin = _seed_user(db_session, UserRole.org_admin, email="scope-admin2@example.com")
    staff = _seed_user(
        db_session,
        UserRole.org_staff,
        email="scope-staff@example.com",
        org=admin.org_id,  # adjust to factory pattern used in this file
    )
    admin_headers = _auth_headers(client, admin.email)
    staff_headers = _auth_headers(client, staff.email)
    created = client.post(
        "/org/question-bank",
        headers=admin_headers,
        json=_question_payload(scope="global", stem="Hidden from staff"),
    )
    assert created.status_code == 201
    resp = client.get("/org/question-bank?scope=global", headers=staff_headers)
    assert resp.status_code == 200
    assert resp.json() == []
```

Adapt `_seed_user` / `_auth_headers` / org wiring to match existing helpers in the file (do not invent a new factory style).

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_question_bank_api.py::test_list_filters_by_scope_for_admin tests/test_question_bank_api.py::test_staff_scope_global_returns_empty -v
```

Expected: FAIL (param ignored → wrong ids / non-empty staff list).

- [ ] **Step 3: Wire router**

In `list_questions`:

```python
    scope: str | None = Query(default=None),
```

Pass `scope=scope` into `QuestionBankService().list(...)`.

- [ ] **Step 4: Run API + service tests**

```bash
.venv/bin/python -m pytest tests/test_question_bank_api.py tests/test_question_bank_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/org_question_bank.py backend/tests/test_question_bank_api.py
git commit -m "$(cat <<'EOF'
feat(question-bank): expose scope filter on list API

EOF
)"
```

---

### Task 3: Frontend API client — `scope` on `listQuestions`

**Files:**
- Modify: `frontend/src/api/questionBank.ts`

**Interfaces:**
- Produces: `QuestionFilters.scope?: "org" | "global"`; `listQuestions` appends `scope` query param when set

- [ ] **Step 1: Extend filters**

```typescript
export type QuestionFilters = {
  subject_code?: string;
  status?: string;
  pending?: boolean;
  scope?: "org" | "global";
  limit?: number;
  offset?: number;
};

export function listQuestions(filters: QuestionFilters) {
  const params = new URLSearchParams();
  if (filters.subject_code) params.set("subject_code", filters.subject_code);
  if (filters.status) params.set("status", filters.status);
  if (filters.pending) params.set("pending", "true");
  if (filters.scope) params.set("scope", filters.scope);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const query = params.toString();
  return api<QuestionBankItem[]>(`/org/question-bank${query ? `?${query}` : ""}`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/questionBank.ts
git commit -m "$(cat <<'EOF'
feat(question-bank): pass scope filter in listQuestions client

EOF
)"
```

---

### Task 4: Frontend UI — Admin scope filter + column

**Files:**
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBank.test.tsx`

**Interfaces:**
- Consumes: `listQuestions` with optional `scope`
- State: `listScope: "" | "org" | "global"` (empty = 全部). Do **not** reuse create-form `scope` state.

- [ ] **Step 1: Write failing frontend tests**

In `frontend/tests/QuestionBank.test.tsx`, add:

```typescript
it("admin can filter list by scope and shows scope column", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => {
    const url = String(input);
    if (url.includes("/org/question-bank?") || url.endsWith("/org/question-bank")) {
      const u = new URL(url, "http://localhost");
      const scope = u.searchParams.get("scope");
      const items = [
        {
          id: "q-org",
          scope: "org",
          org_id: "org-1",
          subject_code: "english",
          knowledge_node_id: null,
          q_type: "short_answer",
          stem: "Org question",
          choices: null,
          answer_key: "a",
          analysis_text: null,
          difficulty: 2,
          source_type: "admin_manual",
          status: "active",
          created_at: "2026-08-01T00:00:00Z",
        },
        {
          id: "q-global",
          scope: "global",
          org_id: null,
          subject_code: "english",
          knowledge_node_id: null,
          q_type: "short_answer",
          stem: "Global question",
          choices: null,
          answer_key: "a",
          analysis_text: null,
          difficulty: 2,
          source_type: "admin_manual",
          status: "active",
          created_at: "2026-08-01T00:00:00Z",
        },
      ];
      const filtered =
        scope === "org"
          ? items.filter((i) => i.scope === "org")
          : scope === "global"
            ? items.filter((i) => i.scope === "global")
            : items;
      return new Response(JSON.stringify(filtered), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  // render Admin page (role=org_admin) using existing render helper pattern
  // assert column header 范围 and labels 本机构 / 平台公共 visible for default all
  // change 范围 select to 平台公共
  // await waitFor: fetch URL includes scope=global; Org question gone; Global question remains
});

it("staff does not show scope filter", async () => {
  // render Staff page; mock list returning org items
  // expect(screen.queryByLabelText("范围")).not.toBeInTheDocument()
  // expect no scope= in list URL
});
```

Match existing `render` helpers / field labels in the file (use `getByLabelText` / `getByRole` consistent with other tests). Fill in realistic fixture fields if the table requires them.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/bytedance/cursor/AITeacher/frontend
npx vitest run tests/QuestionBank.test.tsx -t "scope"
```

Expected: FAIL (no 范围 control).

- [ ] **Step 3: Implement UI**

In `QuestionBankPage.tsx`:

1. Add state:

```typescript
  const [listScope, setListScope] = useState<"" | "org" | "global">("");
```

2. Include in filters only when set:

```typescript
  const filters = {
    subject_code: subject,
    status,
    pending: pendingOnly,
    ...(listScope ? { scope: listScope } : {}),
    limit,
    offset,
  };
```

3. Reset pagination when `listScope` changes (add to the existing `useEffect` deps with `subject, status, pendingOnly`).

4. In filter section, only if `role === "org_admin"`:

```tsx
        <label className="space-y-1 text-sm">
          <span className="block text-slate-600">范围</span>
          <select
            value={listScope}
            onChange={(event) =>
              setListScope(event.target.value as "" | "org" | "global")
            }
            className="rounded border px-3 py-2"
            aria-label="范围"
          >
            <option value="">全部</option>
            <option value="org">本机构</option>
            <option value="global">平台公共</option>
          </select>
        </label>
```

5. In table `<thead>`, for admin only add `<th>范围</th>`; in body:

```tsx
                      {role === "org_admin" && (
                        <td className="px-4 py-3">
                          {SCOPE_LABELS[item.scope] ?? item.scope}
                        </td>
                      )}
```

Staff: no filter, no column.

- [ ] **Step 4: Run frontend tests**

```bash
npx vitest run tests/QuestionBank.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/questionBank/QuestionBankPage.tsx frontend/tests/QuestionBank.test.tsx
git commit -m "$(cat <<'EOF'
feat(question-bank): admin scope filter and column on list

EOF
)"
```

---

### Task 5: Final verification + spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-08-24-question-bank-global-scope-filter-design.md`

- [ ] **Step 1: Run regression**

```bash
cd /Users/bytedance/cursor/AITeacher/backend
.venv/bin/python -m pytest tests/test_question_bank_service.py tests/test_question_bank_api.py -v

cd /Users/bytedance/cursor/AITeacher/frontend
npx vitest run tests/QuestionBank.test.tsx tests/QuestionBankOcr.test.tsx
```

Expected: all PASS.

- [ ] **Step 2: Mark spec implemented**

Change status line to:

```markdown
**状态：** 已实现
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-08-24-question-bank-global-scope-filter-design.md docs/superpowers/plans/2026-08-24-question-bank-global-scope-filter.md
git commit -m "$(cat <<'EOF'
docs: mark global scope filter spec implemented

EOF
)"
```

---

## Spec coverage checklist

| Spec section | Task |
|--------------|------|
| §4.1 `scope` API | 1, 2 |
| §5.1 Admin filter + column | 4 |
| §5.2 Staff no filter/column | 4 |
| §5.3 client `scope` | 3 |
| §7 tests | 1, 2, 4, 5 |
| §8 success criteria | 5 |
| §6 non-goals | enforced by omitting features |

## Spec → plan traceability

| Spec § | Task |
|--------|------|
| §3 权限不变 | 1 (staff empty on global) |
| §4 API | 1–2 |
| §5 前端 | 3–4 |
| §7–8 测试与成功标准 | 5 |
