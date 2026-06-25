# 学生报考档案与总计划个性化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让老师录入学生报考专业、英/数卷种与基础水平，驱动摸底卷种、考纲过滤、初始总计划与摸底后修订；自测组卷仍只参考学情与薄弱点。

**Architecture:** 新增平台专业目录表 + `StudentExamProfile`；`ExamProfileService` 输出 `EffectiveExamProfile` 供 placement / planning 只读消费；老师通过 admin/staff API 确认档案后同步 `StudentSubject` 并触发 `PlanningService.create_initial_plans` 与摸底生成。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL JSONB, React + TanStack Query, Vitest/pytest

**Spec:** `docs/superpowers/specs/2026-06-02-student-exam-profile-master-plan-design.md`

---

## File map


| File                                                 | Responsibility                                        |
| ---------------------------------------------------- | ----------------------------------------------------- |
| `backend/app/models/exam_major.py`                   | `ExamMajorCategory`, `ExamMajor`                      |
| `backend/app/models/student_exam_profile.py`         | `StudentExamProfile`                                  |
| `backend/app/services/exam_profile.py`               | `EffectiveExamProfile`, merge defaults, sync subjects |
| `backend/app/schemas/exam_profile.py`                | Pydantic in/out for catalog + profile                 |
| `backend/app/routers/exam_majors.py`                 | 公开目录 GET                                              |
| `backend/app/routers/admin_exam_profile.py`          | 管理员档案 CRUD + confirm                                  |
| `backend/app/routers/staff_exam_profile.py`          | 员工档案 CRUD + confirm（`StaffStudent` 校验）                |
| `backend/app/routers/student_exam_profile.py`        | 学生只读                                                  |
| `backend/app/seed_exam_majors.py`                    | 大类 + 专业种子                                             |
| `backend/app/services/placement_paper_context.py`    | 按 track 选模板、过滤考纲                                      |
| `backend/app/services/plan_draft.py`                 | 初始计划上下文含档案字段                                          |
| `backend/app/services/placement.py`                  | 档案未完成 gate；submit 后修订保留                               |
| `frontend/src/pages/admin/StudentExamProfile.tsx`    | 管理员向导                                                 |
| `frontend/src/pages/staff/StudentExamProfile.tsx`    | 员工向导（复用组件）                                            |
| `frontend/src/components/exam/ExamProfileWizard.tsx` | 共享五步向导                                                |


---

### Task 1: 数据模型与 migration

**Files:**

- Create: `backend/app/models/exam_major.py`
- Create: `backend/app/models/student_exam_profile.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/c3d4e5f6a7b8_exam_major_and_student_exam_profile.py`
- Test: `backend/tests/test_exam_profile_models.py`
- **Step 1: Write failing model smoke test**

```python
# backend/tests/test_exam_profile_models.py
from app.models import ExamMajor, ExamMajorCategory, StudentExamProfile


def test_exam_major_tables_exist(db_session):
    db_session.add(
        ExamMajorCategory(code="academic_master", name="学硕", sort_order=1)
    )
    db_session.add(
        ExamMajor(
            code="cs_academic",
            category_code="academic_master",
            name="计算机科学与技术",
            default_english_track="english_1",
            default_math_track="math_1",
            default_subject_codes=["english", "math", "politics"],
        )
    )
    db_session.flush()
    db_session.add(
        StudentExamProfile(
            user_id=...,  # use factory student id
            major_category_code="academic_master",
            major_code="cs_academic",
            english_track="english_1",
            math_track="math_1",
            subject_codes=["english", "math", "politics"],
        )
    )
    db_session.commit()
```

- **Step 2: Run test — expect FAIL** (tables missing)

Run: `cd backend && uv run pytest tests/test_exam_profile_models.py -v`

- **Step 3: Add models + migration**

`ExamMajorCategory`: `code` PK, `name`, `sort_order`

`ExamMajor`: `code` PK, `category_code` FK, `name`, `default_english_track`, `default_math_track`, `default_subject_codes` JSONB, `notes` nullable

`StudentExamProfile`: `user_id` PK FK users, fields per spec, `profile_completed_at` nullable, timestamps

- **Step 4: Run test — expect PASS**
- **Step 5: Commit**

```bash
git add backend/app/models/exam_major.py backend/app/models/student_exam_profile.py \
  backend/app/models/__init__.py backend/alembic/versions/c3d4e5f6a7b8_*.py \
  backend/tests/test_exam_profile_models.py
git commit -m "feat: add exam major catalog and student exam profile models"
```

---

### Task 2: 专业目录种子数据

**Files:**

- Create: `backend/app/seed_exam_majors.py`
- Modify: `backend/app/seed.py`（或 `main.py` lifespan 调用）
- Test: `backend/tests/test_exam_major_seed.py`
- **Step 1: Write failing seed test**

```python
def test_seed_exam_majors_populates_categories(db_session):
    from app.seed_exam_majors import seed_exam_majors
    seed_exam_majors(db_session)
    db_session.commit()
    cats = db_session.execute(select(ExamMajorCategory)).scalars().all()
    assert {c.code for c in cats} >= {"academic_master", "professional_master", "management_joint"}
    majors = db_session.execute(select(ExamMajor)).scalars().all()
    assert len(majors) >= 20
```

- **Step 2: Run — FAIL**
- **Step 3: Implement seed**

至少包含：

- `academic_master`：计算机、软件工程、电子信息…（默认英一+数一）
- `professional_master`：会计、法律…（英二+数二 等）
- `management_joint`：MBA、MPAcc…（英二+`math_track=none`）
- **Step 4: Run — PASS**
- **Step 5: Commit**

```bash
git commit -m "feat: seed exam major catalog for placement and planning"
```

---

### Task 3: ExamProfileService

**Files:**

- Create: `backend/app/services/exam_profile.py`
- Create: `backend/app/schemas/exam_profile.py`（`EffectiveExamProfile`, enums）
- Test: `backend/tests/test_exam_profile_service.py`
- **Step 1: Write failing tests**

```python
def test_get_effective_merges_major_defaults(db_session):
    # major defaults english_1; profile overrides english_2 only
    eff = ExamProfileService().get_effective(db, student_user_id)
    assert eff.english_track == "english_2"
    assert eff.math_track == "math_1"  # from major default

def test_sync_subjects_enables_and_disables(db_session):
    # math_track=none -> StudentSubject math disabled
    ExamProfileService().sync_student_subjects(db, student_user_id, ["english", "politics"])
    ...

def test_is_profile_complete_requires_major_and_confirm(db_session):
    assert ExamProfileService().is_complete(db, student_user_id) is False
```

- **Step 2: Run — FAIL**
- **Step 3: Implement service**

```python
@dataclass(frozen=True)
class EffectiveExamProfile:
    major_category_code: str
    major_code: str
    major_name: str
    english_track: Literal["english_1", "english_2"]
    math_track: Literal["math_1", "math_2", "none"]
    subject_codes: list[str]
    cet_status: str | None
    cet_score: int | None
    math_mastery_level: str | None
    profile_completed_at: datetime | None
```

`get_effective`: join `StudentExamProfile` + `ExamMajor`; null track 字段用 major default

`sync_student_subjects`: upsert `StudentSubject.enabled` for org student's all known subjects

`is_complete`: `profile_completed_at is not None` and required fields present

- **Step 4: Run — PASS**
- **Step 5: Commit**

---

### Task 4: 目录与档案 API

**Files:**

- Create: `backend/app/routers/exam_majors.py`
- Create: `backend/app/routers/admin_exam_profile.py`
- Create: `backend/app/routers/staff_exam_profile.py`
- Create: `backend/app/routers/student_exam_profile.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_exam_profile_api.py`
- **Step 1: Write failing API tests**

```python
def test_list_majors_by_category(client, db_session):
    seed_exam_majors(db_session); db_session.commit()
    r = client.get("/exam-majors?category=academic_master")
    assert r.status_code == 200
    assert r.json()[0]["default_english_track"] == "english_1"

def test_staff_cannot_edit_unassigned_student(client, db_session):
    # staff A tries PUT staff/students/{B}/exam-profile -> 404

def test_confirm_triggers_plan_and_sets_completed_at(client, db_session, monkeypatch):
    called = {}
    def fake_create(db, student_user_id):
        called["yes"] = student_user_id
    monkeypatch.setattr("app.services.planning.PlanningService.create_initial_plans", fake_create)
    r = client.post(f"/admin/students/{sid}/exam-profile/confirm", headers=admin_token)
    assert r.status_code == 200
    assert called.get("yes") == sid
```

- **Step 2: Run — FAIL**
- **Step 3: Implement routers**

`PUT exam-profile`: validate major_code belongs to category; persist overrides; **不**自动 confirm

`POST confirm`:

1. `sync_student_subjects`
2. set `profile_completed_at=now()`
3. `PlanningService().create_initial_plans(db, student_user_id)`
4. `PlacementService.start` 各科 enqueue（或专用 `enqueue_placement_for_profile`）
5. `record_audit`

Staff 路由复用 `assert_can_access_student`（见 `org_students.py`）

- **Step 4: Run — PASS**
- **Step 5: Commit**

---

### Task 5: 摸底模板按卷种匹配

**Files:**

- Modify: `backend/app/models/past_exam_template.py` — add `english_track`, `math_track` nullable columns
- Create: `backend/alembic/versions/d4e5f6a7b8c9_past_exam_template_tracks.py`
- Modify: `backend/app/seed_past_exam_templates.py` — 英二、数二模板
- Modify: `backend/app/services/placement_paper_context.py` — `load_paper_template(..., english_track, math_track)`
- Test: `backend/tests/test_placement_paper_context.py`
- **Step 1: Write failing test**

```python
def test_load_template_prefers_english_2_track(db_session):
    seed templates for english_1 and english_2
    ctx = build_placement_context(..., english_track="english_2")
    assert "英语二" in ctx.paper_title or ctx uses english_2 sections
```

- **Step 2: Run — FAIL**
- **Step 3: Implement**

`load_paper_template` 查询加 filter：

- `english` → `english_track`
- `math` → `math_track`
- `politics` → track columns NULL（通用）

无匹配时 fallback 仅 `subject_code` + log warning（spec §7）

- **Step 4: Run placement context tests — PASS**
- **Step 5: Commit**

---

### Task 6: 考纲 track 过滤

**Files:**

- Modify: `backend/app/seed_syllabus.py` — 节点 `meta_json={"tracks": ["math_1"]}` 等
- Modify: `backend/app/services/placement_paper_context.py` — `leaf_nodes_for_placement(..., math_track, english_track)`
- Test: `backend/tests/test_placement_paper_context.py`
- **Step 1: Test math_2 student excludes math_1-only nodes**
- **Step 2: Implement filter** — 节点无 `tracks` 元数据则视为通用
- **Step 3: Commit**

---

### Task 7: 总计划接入档案上下文

**Files:**

- Modify: `backend/app/services/plan_draft.py` — `_build_context` 加入 `EffectiveExamProfile`
- Modify: `backend/app/services/planning.py` — `create_initial_plans` 在无科目时 early return；有档案才 draft
- Test: `backend/tests/test_plan_draft.py`
- **Step 1: Write failing test**

```python
def test_draft_initial_plans_uses_math_none_for_management_major(db_session):
  # profile: management_joint major, math_track none
  draft = PlanDraftService().draft_initial_plans(...)
  assert "math" not in draft.subject_phases_json
  assert any("英语" in g for g in draft.weekly_goals_json)  # english still present
```

- **Step 2: Update `_build_context`**

```python
exam = ExamProfileService().get_effective(db, student_user_id)
return {
    "exam_year": profile.exam_year,
    "major_name": exam.major_name,
    "english_track": exam.english_track,
    "math_track": exam.math_track,
    "cet_status": exam.cet_status,
    "math_mastery_level": exam.math_mastery_level,
    "subjects": subjects,
}
```

- **Step 3: Update rule fallback** in `_rule_draft` for math_mastery / cet / math_none
- **Step 4: Run plan_draft tests — PASS**
- **Step 5: Commit**

---

### Task 8: 摸底 gate 与卷种变更作废

**Files:**

- Modify: `backend/app/services/placement.py` — `start` 检查 `ExamProfileService.is_complete`
- Modify: `backend/app/services/exam_profile.py` — `invalidate_placement_on_track_change`
- Test: `backend/tests/test_placement_flow.py`
- **Step 1: Test placement start without profile → 400**

```python
def test_placement_start_requires_complete_exam_profile(db_session):
    with pytest.raises(HTTPException) as exc:
        PlacementService.start(db, student.id, subject_code="math")
    assert exc.value.status_code == 400
```

- **Step 2: Test track change voids unsubmitted papers**
- **Step 3: Implement**

`PlacementService.start`: 开头 `if not ExamProfileService().is_complete(...): raise 400 "请先完善报考档案"`

`exam_profile` update 检测 `english_track`/`math_track`/`subject_codes` 变更 → 删除未提交 `PlacementQuestion` + reset paper `generating` + enqueue jobs

- **Step 4: Run placement_flow tests — PASS**
- **Step 5: Commit**

---

### Task 9: 自测组卷回归（不使用四六级/数学自评）

**Files:**

- Modify: `backend/app/services/paper_gen.py` — `generate_for_self_test` prompt 仅注入 `english_track`/`math_track`（从 `EffectiveExamProfile`），**不**注入 cet/math_mastery
- Test: `backend/tests/test_paper_gen.py`
- **Step 1: Write regression test**

```python
def test_self_test_prompt_excludes_cet_and_math_mastery(db_session, monkeypatch):
    captured = {}
    def fake_call(self, req):
        captured["prompt"] = req.prompt
        return ModelGatewayResponse(text="...")
    monkeypatch.setattr(ModelGateway, "generate", fake_call)
    # student has cet4 + math basic in profile
    PaperGenService().generate_for_self_test(...)
    assert "cet" not in captured["prompt"].lower() or "四六级" not in captured["prompt"]
    assert "math_mastery" not in captured["prompt"]
```

- **Step 2: Run — verify behavior**
- **Step 3: Commit**

---

### Task 10: 前端报考档案向导

**Files:**

- Create: `frontend/src/api/examProfile.ts`
- Create: `frontend/src/components/exam/ExamProfileWizard.tsx`
- Create: `frontend/src/pages/admin/StudentExamProfile.tsx`
- Create: `frontend/src/pages/staff/StudentExamProfile.tsx`
- Modify: `frontend/src/pages/admin/StudentsList.tsx` — 链接「完善档案」+ `exam_profile_complete` 列
- Modify: `frontend/src/pages/staff/MyStudents.tsx`
- Modify: `frontend/src/App.tsx` — routes
- Modify: `frontend/src/pages/student/Workspace.tsx` — 未完成档案提示 + 摸底按钮禁用
- Test: `frontend/tests/ExamProfileWizard.test.tsx`
- **Step 1: API client**

```typescript
export type ExamMajor = { code: string; name: string; default_english_track: string; ... };
export function listExamMajorCategories() { return api("/exam-majors/categories"); }
export function saveExamProfile(studentId: string, body: ExamProfileIn) { ... }
export function confirmExamProfile(studentId: string) { ... }
```

- **Step 2: Wizard component** — 5 步；Step 3 折叠覆盖；提交调 `confirm`
- **Step 3: Wire admin/staff pages** — 复用 `ExamProfileWizard`，API 前缀不同
- **Step 4: Student workspace** — `GET /student/exam-profile` 展示摘要；`!profile_completed_at` 时禁用摸底
- **Step 5: Vitest** — 选专业后展示推荐英一数一

Run: `cd frontend && npm test -- ExamProfileWizard`

- **Step 6: Commit**

---

### Task 11: 学员列表信号与文档

**Files:**

- Modify: `backend/app/schemas/student.py` — `exam_profile_complete: bool`
- Modify: `backend/app/routers/admin_students.py`, `staff_students.py`
- Modify: `docs/superpowers/specs/2026-06-02-student-exam-profile-master-plan-design.md` — 状态改为「已实现」
- Test: `backend/tests/test_admin_students.py`
- **Step 1: Add `exam_profile_complete` to list responses**
- **Step 2: Full test suite**

Run: `cd backend && uv run pytest -q`  
Run: `cd frontend && npm test`

- **Step 3: Commit**

```bash
git commit -m "feat: surface exam profile completion in student lists and docs"
```

---

## Spec coverage checklist


| Spec §                   | Task                    |
| ------------------------ | ----------------------- |
| 3 数据模型                   | Task 1                  |
| 3.1 专业目录种子               | Task 2                  |
| 3.3 EffectiveExamProfile | Task 3                  |
| 4 录入流程 API               | Task 4, 10              |
| 5.1 摸底模板                 | Task 5, 8               |
| 5.2 考纲过滤                 | Task 6                  |
| 5.3 自测不参考四六级/数学          | Task 9                  |
| 5.4 总计划                  | Task 7                  |
| 6 权限                     | Task 4                  |
| 7 异常边界                   | Task 5 fallback, Task 8 |
| 8 测试要点                   | 各 Task                  |


---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-student-exam-profile-master-plan.md`.

**推荐在独立 worktree 上执行**（`using-git-worktrees` skill）：

```bash
git worktree add ../AITeacher-exam-profile -b feature/student-exam-profile
```

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 Task 派生子 agent，任务间人工 review
2. **Inline Execution** — 本会话用 executing-plans 按 Task 批量执行

你选哪种？