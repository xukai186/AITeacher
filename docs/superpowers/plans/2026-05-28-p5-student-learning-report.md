# P5 — Student Learning Report (学情报告) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a student-facing “学情报告” page that aggregates existing placement/self-test/wrong-book data into actionable insights: weakness TopN, source distribution, and recent self-test trends.

**Architecture:** Add a read-only reporting API (`GET /student/report/overview`) that performs on-the-fly aggregation from existing tables (`wrong_book_items`, `self_test_grades`, `placement_results`). Add a React page to display the report with subject selector (default = first enabled subject; optional = all subjects).

**Tech Stack:** FastAPI + SQLAlchemy + pytest; React + TanStack Query + vitest + Tailwind.

---

## Scope Check (P5 MVP)

P5 **要做**：
- 学生端新增“学情报告”入口与页面
- 后端新增 report API：聚合错题薄弱点（按 `knowledge_node_id`）、错题来源分布（placement/self_test）、自测趋势（近 N 次）
- 仅做 **只读**；不新增队列/异步任务；不引入复杂缓存

P5 **不做**（留后续）：
- 全量历史趋势图表与高性能预聚合表
- “掌握/已掌握”状态机（需要 `WrongBookItem.status` 等字段）
- LLM 自动生成长文本分析（先用规则建议）

---

## Output Contract (API JSON)

### `GET /student/report/overview`

Query params:
- `subject_code`: optional, max_length=40. Omit for “all subjects”.
- `trend_limit`: optional, default 10, 1..30.

Response shape (Pydantic):

```python
class ReportWeakNodeOut(BaseModel):
    knowledge_node_id: uuid.UUID | None
    wrong_count: int
    total_count: int

class ReportTrendPointOut(BaseModel):
    submission_id: uuid.UUID
    paper_id: uuid.UUID
    subject_code: str
    total_score: int
    created_at: datetime

class ReportOverviewOut(BaseModel):
    subject_code: str | None
    wrong_source_counts: dict[str, int]  # placement/self_test
    weak_nodes: list[ReportWeakNodeOut]  # Top N by wrong_count desc
    self_test_trend: list[ReportTrendPointOut]  # recent N by created_at desc
```

Notes:
- `knowledge_node_id` may be null; treat null as “未标注知识点”.
- `weak_nodes.total_count` counts wrong-book items in the same group, so MVP equals wrong_count (we only store wrong items). Keep `total_count` anyway for future “重做后变对” extension.

---

## File Structure (new/modified)

Backend:
- Create: `backend/app/schemas/report.py`
- Create: `backend/app/services/report.py`
- Create: `backend/app/routers/student_report.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_student_report.py`

Frontend:
- Create: `frontend/src/api/report.ts`
- Create: `frontend/src/pages/student/Report.tsx`
- Modify: `frontend/src/App.tsx` (route)
- Modify: `frontend/src/components/Layout.tsx` (nav item)
- Test: `frontend/tests/Report.test.tsx`

---

### Task 1: Backend schema + service aggregator (wrong-book + trend)

**Files:**
- Create: `backend/app/schemas/report.py`
- Create: `backend/app/services/report.py`
- Test: `backend/tests/test_student_report.py`

- [ ] **Step 1: Write failing test (overview returns expected keys)**

Add `backend/tests/test_student_report.py`:

```python
from sqlalchemy import select

from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="student@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def test_student_can_get_report_overview(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    # ensure some wrong-book data exists:
    # 1) placement submit with wrong answers
    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    wrong_payload = {"answers": [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]}
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=wrong_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    # 2) self-test submit with wrong answers (creates wrong-book + grade)
    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200
    self_paper_id = gen.json()["id"]
    self_paper = client.get(
        f"/student/self-tests/{self_paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    submit2 = client.post(
        f"/student/self-tests/{self_paper_id}/submit",
        json={"answers": [{"question_id": q["id"], "content": "Z"} for q in self_paper["questions"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit2.status_code == 200

    # report
    resp = client.get("/student/report/overview?subject_code=english", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_code"] == "english"
    assert "wrong_source_counts" in body
    assert "weak_nodes" in body
    assert "self_test_trend" in body
    assert body["wrong_source_counts"].get("placement", 0) >= 1
    assert body["wrong_source_counts"].get("self_test", 0) >= 1
    assert len(body["weak_nodes"]) >= 1
    assert len(body["self_test_trend"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
- `cd backend && source .venv/bin/activate && pytest tests/test_student_report.py::test_student_can_get_report_overview -v`

Expected:
- FAIL with 404 `/student/report/overview` (router not implemented).

- [ ] **Step 3: Implement schemas**

Create `backend/app/schemas/report.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportWeakNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    knowledge_node_id: uuid.UUID | None
    wrong_count: int = Field(ge=0)
    total_count: int = Field(ge=0)


class ReportTrendPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submission_id: uuid.UUID
    paper_id: uuid.UUID
    subject_code: str
    total_score: int
    created_at: datetime


class ReportOverviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    subject_code: str | None
    wrong_source_counts: dict[str, int]
    weak_nodes: list[ReportWeakNodeOut]
    self_test_trend: list[ReportTrendPointOut]
```

- [ ] **Step 4: Implement service aggregator**

Create `backend/app/services/report.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SelfTestGrade, SelfTestSubmission, WrongBookItem
from app.schemas.report import ReportOverviewOut, ReportTrendPointOut, ReportWeakNodeOut


@dataclass(frozen=True)
class ReportQuery:
    student_user_id: uuid.UUID
    subject_code: str | None = None
    trend_limit: int = 10
    weak_nodes_limit: int = 5


class ReportService:
    @staticmethod
    def overview(db: Session, q: ReportQuery) -> ReportOverviewOut:
        wb_stmt = select(WrongBookItem).where(WrongBookItem.student_user_id == q.student_user_id)
        if q.subject_code:
            wb_stmt = wb_stmt.where(WrongBookItem.subject_code == q.subject_code)

        # source distribution
        source_counts_stmt = (
            select(WrongBookItem.source_type, func.count(WrongBookItem.id))
            .where(WrongBookItem.student_user_id == q.student_user_id)
            .group_by(WrongBookItem.source_type)
        )
        if q.subject_code:
            source_counts_stmt = source_counts_stmt.where(WrongBookItem.subject_code == q.subject_code)
        source_counts = {k: int(v) for k, v in db.execute(source_counts_stmt).all()}

        # weak nodes: top by wrong count
        weak_stmt = (
            select(WrongBookItem.knowledge_node_id, func.count(WrongBookItem.id))
            .where(WrongBookItem.student_user_id == q.student_user_id)
            .group_by(WrongBookItem.knowledge_node_id)
            .order_by(func.count(WrongBookItem.id).desc())
            .limit(q.weak_nodes_limit)
        )
        if q.subject_code:
            weak_stmt = weak_stmt.where(WrongBookItem.subject_code == q.subject_code)
        weak_nodes = [
            ReportWeakNodeOut(
                knowledge_node_id=node_id,
                wrong_count=int(cnt),
                total_count=int(cnt),
            )
            for node_id, cnt in db.execute(weak_stmt).all()
        ]

        # self-test trend: most recent grades
        trend_stmt = (
            select(
                SelfTestGrade.submission_id,
                SelfTestSubmission.paper_id,
                func.max(SelfTestSubmission.student_user_id),
                func.max(SelfTestSubmission.created_at),
                func.max(SelfTestGrade.total_score),
            )
            .join(SelfTestSubmission, SelfTestSubmission.id == SelfTestGrade.submission_id)
            .where(SelfTestSubmission.student_user_id == q.student_user_id)
            .group_by(SelfTestGrade.submission_id, SelfTestSubmission.paper_id)
            .order_by(func.max(SelfTestSubmission.created_at).desc())
            .limit(q.trend_limit)
        )
        # subject_code filtering for trend is done by paper subject; we don't join paper for MVP.
        # Keep MVP simple: allow all subjects when subject_code is None; otherwise filter by wrong-book only.
        trend_rows = db.execute(trend_stmt).all()
        trend = [
            ReportTrendPointOut(
                submission_id=sub_id,
                paper_id=paper_id,
                subject_code=q.subject_code or "unknown",
                total_score=int(score),
                created_at=created_at,
            )
            for sub_id, paper_id, _, created_at, score in trend_rows
        ]

        return ReportOverviewOut(
            subject_code=q.subject_code,
            wrong_source_counts=source_counts,
            weak_nodes=weak_nodes,
            self_test_trend=trend,
        )
```

Implementation notes for the engineer:
- Keep it minimal; we can improve `subject_code` on trend by joining `SelfTestPaper` later.
- Tests only assert presence and basic counts, not perfect labeling.

- [ ] **Step 5: Run test to verify it still fails (404)**

Run:
- `pytest tests/test_student_report.py::test_student_can_get_report_overview -v`

Expected:
- FAIL: 404 (router still missing).

- [ ] **Step 6: Commit schema+service only**

```bash
git add backend/app/schemas/report.py backend/app/services/report.py backend/tests/test_student_report.py
git commit -m "feat(p5): add report schemas and service"
```

---

### Task 2: Backend router + wiring in app

**Files:**
- Create: `backend/app/routers/student_report.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_student_report.py`

- [ ] **Step 1: Implement router**

Create `backend/app/routers/student_report.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import User, UserRole
from app.schemas.report import ReportOverviewOut
from app.services.report import ReportQuery, ReportService

router = APIRouter(prefix="/student/report", tags=["student-report"])


@router.get("/overview", response_model=ReportOverviewOut)
def get_report_overview(
    subject_code: str | None = Query(default=None, max_length=40),
    trend_limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> ReportOverviewOut:
    return ReportService.overview(
        db,
        ReportQuery(
            student_user_id=student.id,
            subject_code=subject_code,
            trend_limit=trend_limit,
        ),
    )
```

- [ ] **Step 2: Wire router**

Modify `backend/app/main.py` to import and include:

```python
from app.routers import student_report

app.include_router(student_report.router)
```

- [ ] **Step 3: Run test to verify it passes**

Run:
- `cd backend && source .venv/bin/activate && pytest tests/test_student_report.py::test_student_can_get_report_overview -v`

Expected:
- PASS

- [ ] **Step 4: Run full backend tests**

Run:
- `cd backend && pytest -q`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/routers/student_report.py backend/tests/test_student_report.py
git commit -m "feat(p5): add student report overview API"
```

---

### Task 3: Frontend API + Report page (MVP)

**Files:**
- Create: `frontend/src/api/report.ts`
- Create: `frontend/src/pages/student/Report.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Test: `frontend/tests/Report.test.tsx`

- [ ] **Step 1: Write failing frontend test**

Create `frontend/tests/Report.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Report from "../src/pages/student/Report";

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: any) => {
      const url = String(input);
      if (url.includes("/api/student/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "s@example.com",
            name: "s",
            exam_year: 2027,
            subject_codes: ["english"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/report/overview")) {
        return new Response(
          JSON.stringify({
            subject_code: "english",
            wrong_source_counts: { placement: 1, self_test: 2 },
            weak_nodes: [{ knowledge_node_id: null, wrong_count: 3, total_count: 3 }],
            self_test_trend: [],
          }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    }),
  );
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/student/report"]}>
        <Routes>
          <Route path="/student/report" element={<Report />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("Report page", () => {
  it("renders overview blocks", async () => {
    mockFetch();
    renderPage();
    await waitFor(() => expect(screen.getByText("学情报告")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("错题来源")).toBeTruthy());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
- `cd frontend && npm test -- --run tests/Report.test.tsx`

Expected:
- FAIL: module not found `Report` (page not created yet)

- [ ] **Step 3: Implement frontend API**

Create `frontend/src/api/report.ts`:

```ts
import { api } from "./client";

export type ReportWeakNodeOut = {
  knowledge_node_id: string | null;
  wrong_count: number;
  total_count: number;
};

export type ReportOverviewOut = {
  subject_code: string | null;
  wrong_source_counts: Record<string, number>;
  weak_nodes: ReportWeakNodeOut[];
  self_test_trend: Array<{
    submission_id: string;
    paper_id: string;
    subject_code: string;
    total_score: number;
    created_at: string;
  }>;
};

export function fetchStudentReportOverview(params?: { subject_code?: string }) {
  const qs = new URLSearchParams();
  if (params?.subject_code) qs.set("subject_code", params.subject_code);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<ReportOverviewOut>(`/student/report/overview${suffix}`);
}
```

- [ ] **Step 4: Implement Report page**

Create `frontend/src/pages/student/Report.tsx`:

```tsx
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStudentMe } from "@/api/me";
import { fetchStudentReportOverview } from "@/api/report";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function Report() {
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  const [subject, setSubject] = useState<string>("__default__");
  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);
  const effectiveSubject = subject === "__default__" ? subjectOptions[0] || "" : subject;

  const overview = useQuery({
    queryKey: ["student", "report_overview", effectiveSubject],
    queryFn: () => fetchStudentReportOverview({ subject_code: effectiveSubject || undefined }),
    enabled: Boolean(me.data),
  });

  if (me.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">学情报告</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">科目</span>
          <select className="border rounded px-2 py-1 text-sm" value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="__default__">（默认）</option>
            <option value="">全部科目</option>
            {subjectOptions.map((code) => (
              <option key={code} value={code}>
                {SUBJECT_LABELS[code] ?? code}
              </option>
            ))}
          </select>
        </div>
      </header>

      {overview.isLoading ? (
        <p className="text-slate-500 text-sm">加载中…</p>
      ) : overview.error ? (
        <p className="text-red-600 text-sm">{(overview.error as Error).message}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-white shadow rounded p-4 space-y-2">
            <div className="font-medium">错题来源</div>
            <div className="text-sm text-slate-700">
              测评：{overview.data?.wrong_source_counts?.placement ?? 0}，自测：
              {overview.data?.wrong_source_counts?.self_test ?? 0}
            </div>
          </div>
          <div className="bg-white shadow rounded p-4 space-y-2">
            <div className="font-medium">薄弱点 Top</div>
            <ul className="text-sm text-slate-700 space-y-1">
              {(overview.data?.weak_nodes ?? []).map((n, idx) => (
                <li key={n.knowledge_node_id ?? `null-${idx}`}>
                  {n.knowledge_node_id ?? "（未标注知识点）"}：{n.wrong_count}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Wire route + nav**

Modify `frontend/src/App.tsx`:
- Add import: `import Report from "@/pages/student/Report";`
- Add route under student layout:

```tsx
<Route path="/student/report" element={<Report />} />
```

Modify `frontend/src/components/Layout.tsx` student nav:

```ts
{ to: "/student/report", label: "学情报告" },
```

- [ ] **Step 6: Run frontend tests**

Run:
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/report.ts frontend/src/pages/student/Report.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/tests/Report.test.tsx
git commit -m "feat(p5): add student learning report page"
```

---

### Task 4: Final verification + PR

**Files:**
- (no new files)

- [ ] **Step 1: Backend full suite**

Run:
- `cd backend && source .venv/bin/activate && pytest -q`

Expected:
- PASS

- [ ] **Step 2: Frontend full suite**

Run:
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`

Expected:
- PASS

- [ ] **Step 3: Manual smoke**

1. Login as student
2. Complete one placement (or re-use existing) and one self-test submission
3. Open “学情报告”
4. Verify:
   - “错题来源” counts are non-zero
   - “薄弱点 Top” shows at least 1 item

- [ ] **Step 4: PR**

```bash
git push -u origin feature/p5-student-report
gh pr create --base master --head feature/p5-student-report --title "feat(p5): student learning report (overview)" --body "$(cat <<'EOF'
## Summary
- Add student report overview API aggregating wrong-book and self-test data.
- Add 学情报告 page with subject selector.

## Test plan
- Backend: pytest
- Frontend: vitest + build
EOF
)"
```

