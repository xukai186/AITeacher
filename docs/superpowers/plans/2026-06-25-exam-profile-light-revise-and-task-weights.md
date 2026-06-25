# 报考档案轻量修订与任务权重 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当老师仅更新四六级/数学掌握度时，轻量修订英语/数学分科计划与总计划（P12 阈值控制）；并按档案弱项调整跨科削减权重与次日任务生成。

**Architecture:** 新增 `ExamProfileWeightService` 统一权重；`PlanDraftService` 抽取 `phases_for_subject` / `light_revise_draft` 供初始与轻量修订共用；`PlanningService.light_revise_from_profile` 更新 SubjectPlan + `MasterPlanActivationService.propose_version`；`PUT exam-profile` 在结构不变且档案已确认时触发轻量修订。

**Tech Stack:** FastAPI, SQLAlchemy, pytest; 复用 `AUTO_ACTIVATE_THRESHOLD=0.15`

**Spec:** `docs/superpowers/specs/2026-06-25-exam-profile-light-revise-and-task-weights-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/exam_profile_weights.py` | CET/数学 → 科目权重 |
| `backend/app/services/plan_draft.py` | `phases_for_subject`, `light_revise_draft` |
| `backend/app/services/planning.py` | `light_revise_from_profile` |
| `backend/app/services/exam_profile.py` | `is_baseline_only_change(old, new)` 辅助 |
| `backend/app/services/master_planner.py` | 合并档案权重 |
| `backend/app/services/subject_agent.py` | 弱项 boost study 任务 |
| `backend/app/routers/admin_exam_profile.py` | PUT 后触发轻量修订 + audit |
| `backend/app/routers/staff_exam_profile.py` | 同上 |
| `backend/tests/test_exam_profile_weights.py` | 权重 + trim + boost |
| `backend/tests/test_exam_profile_light_revise.py` | 轻量修订 + P12 阈值 |

---

### Task 1: ExamProfileWeightService

**Files:**
- Create: `backend/app/services/exam_profile_weights.py`
- Test: `backend/tests/test_exam_profile_weights.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_exam_profile_weights.py
from app.services.exam_profile_weights import ExamProfileWeightService
from tests.exam_profile_helpers import add_complete_exam_profile
from tests.factories import make_org, make_user
from app.models import UserRole, StudentExamProfile


def test_english_not_taken_has_higher_weight_than_cet6(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w1@demo.example")
    add_complete_exam_profile(db_session, student.id)
    prof = db_session.get(StudentExamProfile, student.id)
    prof.cet_status = "not_taken"
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w["english"] > w["politics"]

    prof.cet_status = "cet6"
    db_session.flush()
    w2 = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w2["english"] < w["english"]


def test_math_zero_has_higher_weight_than_strong(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w2@demo.example")
    add_complete_exam_profile(db_session, student.id)
    prof = db_session.get(StudentExamProfile, student.id)
    prof.math_mastery_level = "zero"
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    prof.math_mastery_level = "strong"
    db_session.flush()
    w2 = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert w["math"] > w2["math"]


def test_math_none_track_excludes_math_weight(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="w3@demo.example")
    add_complete_exam_profile(db_session, student.id, subject_codes=["english", "politics"])
    prof = db_session.get(StudentExamProfile, student.id)
    prof.math_track = "none"
    prof.subject_codes = ["english", "politics"]
    db_session.flush()
    w = ExamProfileWeightService().subject_weights(db_session, student.id)
    assert "math" not in w
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && uv run pytest tests/test_exam_profile_weights.py -v`

- [ ] **Step 3: Implement**

```python
# backend/app/services/exam_profile_weights.py
ENGLISH_WEIGHTS = {"not_taken": 4, "cet4": 3, "cet6": 2}
MATH_WEIGHTS = {"zero": 4, "basic": 3, "good": 2, "strong": 1}
DEFAULT_ENGLISH = 3
DEFAULT_MATH = 3
POLITICS_BASE = 2

class ExamProfileWeightService:
    def subject_weights(self, db, student_user_id) -> dict[str, int]:
        # read EffectiveExamProfile + enabled StudentSubject codes
        # english: ENGLISH_WEIGHTS.get(cet_status, DEFAULT_ENGLISH)
        # math: skip if math_track==none or not enabled
        # politics: POLITICS_BASE if enabled
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add exam profile subject weights for task trimming"
```

---

### Task 2: PlanDraftService 抽取轻量起草

**Files:**
- Modify: `backend/app/services/plan_draft.py`
- Test: `backend/tests/test_plan_draft.py`

- [ ] **Step 1: Write failing test**

```python
def test_light_revise_draft_boosts_budget_for_cet_not_taken(db_session, student_with_profile):
    from app.services.plan_draft import PlanDraftService
    from datetime import date
    draft = PlanDraftService().light_revise_draft(
        db_session,
        student_user_id=student_with_profile.id,
        today=date(2026, 6, 25),
    )
    total = sum(e["minutes"] for e in draft.daily_time_budget_json)
    assert total > 7 * 180  # +10 min/day for not_taken
    assert "english" in draft.subject_phases_json
    notes = draft.subject_phases_json["english"][0]["notes"]
    assert "CET" in notes or "词汇" in notes
```

- [ ] **Step 2: Refactor `_draft_with_rules`**

提取：
- `phases_for_subject(code, context) -> list[dict]` — 含现有 english/math CET 分支
- `light_revise_draft(db, student_user_id, today) -> PlanDraft` — 仅 enabled 科目的 english/math phases + weekly_goals + budget 调整（`not_taken` / `zero` 各 +10 分钟/天）

- [ ] **Step 3: Run plan_draft tests — PASS**

- [ ] **Step 4: Commit**

---

### Task 3: PlanningService.light_revise_from_profile

**Files:**
- Modify: `backend/app/services/planning.py`
- Modify: `backend/app/services/exam_profile.py` — add `baseline_fields_changed(old, new) -> bool`
- Test: `backend/tests/test_exam_profile_light_revise.py`

- [ ] **Step 1: Write failing tests**

```python
def test_light_revise_bumps_english_subject_version_only(db_session, client, admin_token, student_with_confirmed_profile):
    # setup: confirm profile, create_initial_plans already done
    # record politics SubjectPlanVersion.version
    # PUT cet_status not_taken only
    # assert english version+1, politics unchanged

def test_light_revise_large_budget_sets_pending(db_session, ...):
    # manipulate current budget to 100 min/day x7
    # PUT cet not_taken triggers +10/day -> ratio > 0.15
    # assert master.pending_version_id is not None

def test_light_revise_small_budget_auto_activates(db_session, ...):
    # default 180/day, +10/day -> ratio < 0.15
    # assert pending_version_id is None
```

- [ ] **Step 2: Implement `light_revise_from_profile`**

```python
def light_revise_from_profile(self, db, student_user_id) -> ProposeResult | None:
    master = ...  # must have current_version_id else create_initial_plans and return
    draft = PlanDraftService().light_revise_draft(db, student_user_id=student_user_id)
    for code in ("english", "math"):
        if code not in draft.subject_phases_json:
            continue
        # bump SubjectPlanVersion for code
    current = db.get(MasterPlanVersion, master.current_version_id)
    result = MasterPlanActivationService().propose_version(
        db, plan=master,
        daily_time_budget_json=draft.daily_time_budget_json,
        weekly_goals_json=draft.weekly_goals_json,
        source="ai",
    )
    return result
```

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

---

### Task 4: PUT 路由触发与变更分流

**Files:**
- Modify: `backend/app/routers/admin_exam_profile.py`
- Modify: `backend/app/routers/staff_exam_profile.py`
- Modify: `backend/tests/test_exam_profile_api.py`

- [ ] **Step 1: Add helper `_profile_change_kind(old_eff, new_eff) -> literal["structural","baseline","none"]`**

- structural: major/track/subjects changed
- baseline: only cet_status, cet_score, math_mastery_level
- none: no effective change

- [ ] **Step 2: In PUT after commit path, before final commit:**

```python
if profile.profile_completed_at and kind == "baseline":
    PlanningService().light_revise_from_profile(db, student_id)
    record_audit(..., action="student.exam_profile.light_revise", ...)
```

- [ ] **Step 3: API tests**

```python
def test_put_cet_only_triggers_light_revise(client, db_session, monkeypatch):
    called = {}
    def fake_light(self, db, sid):
        called["yes"] = sid
    monkeypatch.setattr(PlanningService, "light_revise_from_profile", fake_light)
    # PUT only cet_status change on confirmed profile
    assert called.get("yes") == student_id

def test_put_track_change_does_not_light_revise(client, ...):
    # change english_track -> light_revise NOT called
```

- [ ] **Step 4: Run test_exam_profile_api — PASS**

- [ ] **Step 5: Commit**

---

### Task 5: MasterPlanner 合并档案权重

**Files:**
- Modify: `backend/app/services/master_planner.py`
- Test: `backend/tests/test_exam_profile_weights.py` (extend)

- [ ] **Step 1: Test trim prefers high-weight subject**

```python
def test_trim_cancels_low_weight_subject_first(db_session):
    # student with english weight 4, politics 2
    # over budget day with tasks in both subjects
    # assert politics task cancelled before english
```

- [ ] **Step 2: Update `subject_weights_for_student`**

```python
def subject_weights_for_student(db, student_user_id):
    exam = ExamProfileWeightService().subject_weights(db, student_user_id)
    if exam:
        package_rank = ...  # optional tie-break: (exam[code] * 10) + (n - idx)
        return {code: exam.get(code, 0) * 10 + rank for ...}
    # fallback existing package logic
```

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

---

### Task 6: SubjectAgent 弱项 boost 任务

**Files:**
- Modify: `backend/app/services/subject_agent.py`
- Test: `backend/tests/test_exam_profile_weights.py`

- [ ] **Step 1: Failing test**

```python
def test_apply_recommendations_adds_english_boost_for_cet_not_taken(db_session):
    # complete profile cet not_taken
    result = SubjectAgentService().apply_report_recommendations(...)
    titles = [t.title for t in result.created]
    assert any("基础" in t for t in titles)
    # second call skipped_count or no duplicate created
```

- [ ] **Step 2: After report loop, call `_maybe_add_profile_boost(db, student_user_id, subject_code, day, result)`**

```python
BOOST_REF = "exam_profile_boost"
# english + cet not_taken/null -> study 30min 幂等
# math + zero/basic/null -> study 30min 幂等
```

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

---

### Task 7: 全量回归与文档

**Files:**
- Modify: `docs/superpowers/specs/2026-06-25-exam-profile-light-revise-and-task-weights-design.md` — 状态「已实现」

- [ ] **Step 1: Full suite**

Run: `cd backend && uv run pytest -q`

- [ ] **Step 2: Update spec status**

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: mark exam profile light revise spec as implemented"
```

---

## Spec coverage

| Spec § | Task |
|--------|------|
| §3 触发分流 | Task 4 |
| §4 轻量修订 | Task 2, 3 |
| §5 任务权重 | Task 1, 5, 6 |
| §8 测试 | 各 Task |
| P12 阈值 | Task 3 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-exam-profile-light-revise-and-task-weights.md`.

**推荐在独立 worktree 开发：**

```bash
git worktree add ../AITeacher-light-revise -b feature/exam-profile-light-revise
```

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 Task 子 agent + review
2. **Inline Execution** — 本会话连续实现

你选哪种？
