# P3 — Placement Assessment + Versioned Planning + Daily Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the “摸底测评 → 掌握度初始化 → 生成总/分科计划版本 → 生成首周每日任务”闭环，并在学生工作台能看到摸底入口、摸底试卷、以及“今日计划”任务列表（先不做错题/自测/批阅）。

**Architecture:** Add DB models for syllabus knowledge tree, placement papers, submissions/results, mastery snapshots, plan/version tables, and daily tasks. Implement service layer pipelines that: (1) generate placement papers per enabled subject, (2) accept student submissions, (3) grade placement deterministically (P3 先用 mock 规则/网关生成，结构化落库), (4) derive an initial mastery snapshot, (5) create `MasterPlanVersion` + `SubjectPlanVersion` as `active`, and (6) generate 7 days of `DailyTask`. Keep AI involvement minimal: only use existing `ModelGateway` in `planning` scene to draft plan text blocks, but enforce DB shape and constraints in code.

**Tech Stack:** Existing P1/P2 stack (FastAPI + SQLAlchemy + Alembic + pytest; React + TanStack Query + vitest).

---

## Scope Check (P3)

P3 **不做**（留到 P4/P5）：
- 自测组卷、批阅 pipeline、错题集、学情图表、计划复审调度（PlanReviewJob）
- 真实题库与复杂题型：P3 摸底题目用极简题型（选择题/填空题）+ 可确定评分

P3 **要做**：
- 考纲（知识点树）最小化落库（内置 2–3 科公共课）
- 摸底试卷生成、作答提交、评分与结果落库
- 掌握度快照初始化（按知识点）
- 总计划/分科计划的**版本化**与 `active` 指针
- 每日任务生成（未来 7 天）
- 学生端能看到：摸底入口、摸底卷页面、今日任务列表
- 机构后台可查看某学员摸底结果概览（只读即可）

---

## File Structure (P3)

Backend new/modified files:

- Create: `backend/app/models/syllabus.py`
- Create: `backend/app/models/placement.py`
- Create: `backend/app/models/mastery.py`
- Create: `backend/app/models/plan.py`
- Create: `backend/app/models/task.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/app/schemas/syllabus.py`
- Create: `backend/app/schemas/placement.py`
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/services/placement.py`
- Create: `backend/app/services/mastery.py`
- Create: `backend/app/services/planning.py`
- Create: `backend/app/services/tasks.py`
- Create: `backend/app/routers/student_placement.py`
- Create: `backend/app/routers/student_tasks.py`
- Create: `backend/app/routers/admin_student_progress.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/seed_syllabus.py` (CLI: seed minimal syllabus)
- Tests:
  - `backend/tests/test_syllabus_seed.py`
  - `backend/tests/test_placement_flow.py`
  - `backend/tests/test_planning_versions.py`
  - `backend/tests/test_daily_tasks.py`

Frontend new/modified files:

- Create: `frontend/src/api/placement.ts`
- Create: `frontend/src/api/tasks.ts`
- Modify: `frontend/src/pages/student/Workspace.tsx` (今日任务列表 + 摸底状态)
- Create: `frontend/src/pages/student/Placement.tsx`
- Modify: `frontend/src/App.tsx` (route)
- Tests:
  - `frontend/tests/Placement.test.tsx`
  - `frontend/tests/WorkspaceTasks.test.tsx`

---

## Domain Model (P3)

### Knowledge / Syllabus

- `SyllabusNode(id, subject_code, parent_id, name, weight, created_at)`

### Placement assessment

- `PlacementPaper(id, student_user_id, subject_code, status, created_at)`
- `PlacementQuestion(id, paper_id, seq, knowledge_node_id, q_type, stem, choices_json, answer_key, points)`
- `PlacementSubmission(id, paper_id, student_user_id, status, submitted_at)`
- `PlacementAnswer(id, submission_id, question_id, content, is_correct, score)`
- `PlacementResult(id, paper_id, total_score, mastery_json)`  # mastery_json: { knowledge_node_id: level }

### Mastery

- `MasterySnapshot(id, student_user_id, subject_code, version, mastery_json, created_at)`

### Plans (versioned)

- `MasterPlan(id, student_user_id, status, current_version_id)`
- `MasterPlanVersion(id, master_plan_id, version, source, weekly_goals_json, daily_time_budget_json, created_at)`
- `SubjectPlan(id, student_user_id, subject_code, current_version_id)`
- `SubjectPlanVersion(id, subject_plan_id, version, source, phases_json, created_at)`

### Daily tasks

- `DailyTask(id, student_user_id, date, subject_code, type, ref_id, status, est_minutes, title, created_at)`

---

## Task 1: Models + migration for syllabus + placement + mastery + plans + daily tasks

**Files:**
- Create: `backend/app/models/syllabus.py`
- Create: `backend/app/models/placement.py`
- Create: `backend/app/models/mastery.py`
- Create: `backend/app/models/plan.py`
- Create: `backend/app/models/task.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Migration: `backend/alembic/versions/*_p3_models.py`
- Test: `backend/tests/test_p3_models_smoke.py`

- [ ] **Step 1: Write failing model smoke test**

Create `backend/tests/test_p3_models_smoke.py`:

```python
from app.models import (
    DailyTask,
    MasterPlan,
    MasterPlanVersion,
    MasterySnapshot,
    PlacementPaper,
    SyllabusNode,
    SubjectPlan,
    SubjectPlanVersion,
)


def test_imports_exist():
    assert SyllabusNode
    assert PlacementPaper
    assert MasterySnapshot
    assert MasterPlan
    assert MasterPlanVersion
    assert SubjectPlan
    assert SubjectPlanVersion
    assert DailyTask
```

- [ ] **Step 2: Run and confirm it fails**

Run: `cd backend && pytest tests/test_p3_models_smoke.py -v`  
Expected: ImportError (models not present).

- [ ] **Step 3: Implement models**

Implement each file with UUID PKs, `created_at` default `func.now()`, and the minimal constraints:
- `SyllabusNode.parent_id` nullable FK self-reference
- `PlacementQuestion.seq` unique per paper
- `DailyTask` unique per `(student_user_id, date, subject_code, type, ref_id)` (allow `ref_id` null for reading tasks)
- Plan versions unique per `(plan_id, version)`

Use JSONB for `choices_json`, `weekly_goals_json`, etc.

- [ ] **Step 4: Wire imports**

Update `backend/app/models/__init__.py` and `backend/alembic/env.py` to import the new model modules.

- [ ] **Step 5: Autogenerate migration + apply**

Run:

```bash
cd backend
alembic revision --autogenerate -m "add p3 syllabus placement plans tasks"
alembic upgrade head
AITEACHER_DATABASE_URL=postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test alembic upgrade head
```

Expected: success.

- [ ] **Step 6: Run test**

Run: `cd backend && pytest tests/test_p3_models_smoke.py -v`  
Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models backend/app/models/__init__.py backend/alembic/env.py backend/alembic/versions backend/tests/test_p3_models_smoke.py
git commit -m "feat(p3): add syllabus, placement, plan, and daily task models"
```

---

## Task 2: Seed minimal syllabus (CLI + test)

**Files:**
- Create: `backend/app/seed_syllabus.py`
- Test: `backend/tests/test_syllabus_seed.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_syllabus_seed.py`:

```python
from sqlalchemy import select

from app.models import SyllabusNode
from app.seed_syllabus import seed_minimal_syllabus


def test_seed_minimal_syllabus_idempotent(db_session):
    seed_minimal_syllabus(db_session)
    seed_minimal_syllabus(db_session)
    rows = db_session.execute(select(SyllabusNode)).scalars().all()
    assert len(rows) > 0
```

- [ ] **Step 2: Implement `seed_minimal_syllabus`**

Seed at least these subject codes with a 2-level tree:
- `english`: 阅读、翻译、写作
- `math`: 高数、线代、概率
- `politics`: 马原、毛中特、史纲、思修

Implementation rule: identify nodes by `(subject_code, parent_id, name)` and only insert if missing.

- [ ] **Step 3: Run test**

Run: `cd backend && pytest tests/test_syllabus_seed.py -v`  
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/seed_syllabus.py backend/tests/test_syllabus_seed.py
git commit -m "feat(p3): add minimal syllabus seeding"
```

---

## Task 3: Placement generation service (per-student, per-subject) + API

**Files:**
- Create: `backend/app/schemas/placement.py`
- Create: `backend/app/services/placement.py`
- Create: `backend/app/routers/student_placement.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_placement_flow.py`

- [ ] **Step 1: Write failing integration test**

Create `backend/tests/test_placement_flow.py`:

```python
from sqlalchemy import select

from app.auth.security import hash_password
from app.models import PlacementPaper, StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(db, org, role=UserRole.student, email="student@demo.example", password_hash=hash_password("pw"))
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()["access_token"]


def test_student_can_start_placement_and_get_paper(client, db_session):
    _seed_student(db_session)
    token = _token(client)
    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200

    papers = db_session.execute(select(PlacementPaper)).scalars().all()
    assert len(papers) == 1
```

- [ ] **Step 2: Implement schemas**

Define response payloads for:
- placement status (per subject)
- paper structure (questions list)
- submission request (answers list)

- [ ] **Step 3: Implement service**

`PlacementService.start(db, student_user_id)` should:
- ensure syllabus seeded (or error instructing admin to seed)
- for each enabled `StudentSubject`, create `PlacementPaper(status="ready")` if missing
- generate N=10 questions per subject using deterministic rules:
  - pick 10 leaf `SyllabusNode`s (or repeat if fewer)
  - q_type fixed: `single_choice`
  - `answer_key` among A/B/C/D

- [ ] **Step 4: Implement router**

Endpoints (student role):
- `POST /student/placement/start`
- `GET /student/placement` (list papers)
- `GET /student/placement/{paper_id}` (paper detail)

- [ ] **Step 5: Run test**

Run: `cd backend && pytest tests/test_placement_flow.py -v`  
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/placement.py backend/app/services/placement.py backend/app/routers/student_placement.py backend/app/main.py backend/tests/test_placement_flow.py
git commit -m "feat(p3): add placement paper generation and student api"
```

---

## Task 4: Placement submission + grading + result + mastery snapshot

**Files:**
- Modify: `backend/app/services/placement.py`
- Create: `backend/app/services/mastery.py`
- Modify: `backend/app/routers/student_placement.py`
- Test: extend `backend/tests/test_placement_flow.py`

- [ ] **Step 1: Extend failing test**

Add to `backend/tests/test_placement_flow.py`:

```python
from app.models import MasterySnapshot, PlacementResult


def test_submit_placement_creates_result_and_mastery(db_session, client):
    _seed_student(db_session)
    token = _token(client)
    client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})

    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    answers = [{"question_id": q["id"], "content": q["answer_key"]} for q in paper["questions"]]

    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200
    assert db_session.query(PlacementResult).count() == 1
    assert db_session.query(MasterySnapshot).count() == 1
```

- [ ] **Step 2: Implement submit endpoint**

`POST /student/placement/{paper_id}/submit`:
- create submission + answers
- grade: correct if `content == answer_key`
- create `PlacementResult` with `total_score` and `mastery_json` mapping nodes to level:
  - level 1 if incorrect, level 3 if correct (simple)
- create `MasterySnapshot(version=1)` per subject

- [ ] **Step 3: Run tests**

Run: `cd backend && pytest tests/test_placement_flow.py -v`  
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/placement.py backend/app/services/mastery.py backend/app/routers/student_placement.py backend/tests/test_placement_flow.py
git commit -m "feat(p3): grade placement and initialize mastery snapshot"
```

---

## Task 5: Planning service — create active plan versions after placement completion

**Files:**
- Create: `backend/app/schemas/plan.py`
- Create: `backend/app/services/planning.py`
- Test: `backend/tests/test_planning_versions.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_planning_versions.py`:

```python
from app.models import MasterPlan, SubjectPlan
from app.services.planning import PlanningService
from tests.test_placement_flow import _seed_student


def test_planning_creates_master_and_subject_plans(db_session):
    student = _seed_student(db_session)
    svc = PlanningService()
    svc.create_initial_plans(db_session, student_user_id=student.id)
    assert db_session.query(MasterPlan).count() == 1
    assert db_session.query(SubjectPlan).count() == 1
```

- [ ] **Step 2: Implement minimal planning**

`create_initial_plans` should:
- create `MasterPlan` + `MasterPlanVersion(version=1, source="ai")` with simple defaults:
  - daily_time_budget_json: next 7 days total minutes = 180
- create `SubjectPlan` + `SubjectPlanVersion(version=1, source="ai")` with phases_json placeholder
- set `current_version_id` pointers and status `active`

P3 不做“待确认”，全部自动 active。

- [ ] **Step 3: Run tests**

Run: `cd backend && pytest tests/test_planning_versions.py -v`  
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/plan.py backend/app/services/planning.py backend/tests/test_planning_versions.py
git commit -m "feat(p3): generate initial plan versions"
```

---

## Task 6: Daily task generation (7 days) + student API

**Files:**
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/services/tasks.py`
- Create: `backend/app/routers/student_tasks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_daily_tasks.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_daily_tasks.py`:

```python
from datetime import date, timedelta

from app.auth.security import hash_password
from app.models import DailyTask, StudentProfile, StudentSubject, UserRole
from app.services.tasks import TaskGenerator
from tests.factories import make_org, make_user


def test_generate_7_days_tasks(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.example", password_hash=hash_password("pw"))
    db_session.add(StudentProfile(user_id=student.id, exam_year=2027))
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db_session.commit()

    TaskGenerator().generate_next_7_days(db_session, student_user_id=student.id, today=date.today())
    assert db_session.query(DailyTask).count() == 7
```

- [ ] **Step 2: Implement generator**

Create exactly 1 task per day for the enabled subject:
- type: `study`
- title: `英语 学习任务`
- est_minutes: 60
- status: `pending`

- [ ] **Step 3: Add student API**

`GET /student/tasks/today` returns today tasks grouped by subject.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_daily_tasks.py -v`  
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/task.py backend/app/services/tasks.py backend/app/routers/student_tasks.py backend/app/main.py backend/tests/test_daily_tasks.py
git commit -m "feat(p3): generate and expose daily tasks"
```

---

## Task 7: Frontend — placement + today tasks surfaces

**Files:**
- Create: `frontend/src/api/placement.ts`
- Create: `frontend/src/api/tasks.ts`
- Create: `frontend/src/pages/student/Placement.tsx`
- Modify: `frontend/src/pages/student/Workspace.tsx`
- Modify: `frontend/src/App.tsx`
- Tests: `frontend/tests/Placement.test.tsx`, `frontend/tests/WorkspaceTasks.test.tsx`

- [ ] **Step 1: Implement minimal APIs**

`placement.ts`: start + list + detail + submit  
`tasks.ts`: fetch today tasks

- [ ] **Step 2: Workspace changes**

In left content area:
- if placement not completed → show CTA button “开始摸底测评”
- show today tasks list (title + status)

Right panel keeps ChatPanel from P2.

- [ ] **Step 3: Placement page**

Render questions and submit (answers auto-filled correct for MVP toggle button “一键填入正确答案（仅开发）”).

- [ ] **Step 4: Tests + build**

Run: `cd frontend && npm test -- --run && npm run build`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/placement.ts frontend/src/api/tasks.ts frontend/src/pages/student/Placement.tsx frontend/src/pages/student/Workspace.tsx frontend/src/App.tsx frontend/tests/Placement.test.tsx frontend/tests/WorkspaceTasks.test.tsx
git commit -m "feat(p3): student placement and today tasks UI"
```

---

## Task 8: Final verification (P3)

- [ ] **Step 1: Backend tests**

Run: `cd backend && pytest -q`

- [ ] **Step 2: Frontend tests**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 3: Manual smoke**

1) `docker compose up -d`\n
2) `cd backend && alembic upgrade head && python -m app.seed && python -m app.seed_syllabus`\n
3) Start backend + frontend\n
4) Login as student → start placement → submit → go back workspace → see today tasks\n

- [ ] **Step 4: Commit**

No commit expected.

---

## Self-Review (controller)

- Spec coverage: placement→mastery→plans→daily tasks matches spec §3.2/§3.3/§6.2/§6.3.\n
- Placeholder scan: no TBD/TODO.\n
- Consistency: endpoints under `/student/*` and models use UUID.\n

