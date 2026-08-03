# Weekly Goals → Daily Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist structured weekly focus goals (subject + syllabus leaf IDs from the roadmap month slice) on `MasterPlanVersion.weekly_goals_json`, and generate daily tasks primarily from those nodes—with at most one weak-point review—defaulting to today.

**Architecture:** Extend `PlanDraftService._apply_month_slice` to emit `kind=focus` weekly goals with `syllabus_node_ids`. Change `SubjectAgentService.apply_report_recommendations` to prefer focus nodes when present, else fall back to report recommendations. Align default `target_date` to `date.today()` across agent/cron entry points. Light UI labels + report button copy.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, Vitest

**Spec:** `docs/superpowers/specs/2026-08-03-weekly-goals-to-daily-cascade-design.md`

## Global Constraints

- Weekly KP only from roadmap month-slice leaf `syllabus_node_ids` (do not merge wrong-book weak nodes into weekly goals)
- Daily: prioritize weekly focus study tasks; at most **one** `review_wrong` from weak points per subject/day when focus exists
- Default `target_date` = **today** (not tomorrow)
- Old weekly goals without IDs → fall back to existing report recommendations
- No new WeeklyPlan table; no auto-rewrite of weekly goals on mastery events
- Self-test paper generation remains decoupled from daily task payload

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/plan_draft.py` | Emit structured focus weekly goals in `_apply_month_slice` |
| `backend/tests/test_roadmap.py` or `test_plan_draft.py` | Assert focus goals with IDs |
| `backend/app/services/subject_agent.py` | Cascade daily generation + default today |
| `backend/app/services/daily_task_generation.py` | Default target today; docstring |
| `backend/app/routers/student_agent.py` | Query default today |
| `backend/tests/test_subject_agent_tasks.py` | Cascade + fallback + weak cap |
| `frontend/src/pages/student/Workspace.tsx` | Optional source labels on tasks |
| `frontend/src/pages/student/Report.tsx` | Button/copy「生成今日任务」 |
| `frontend/src/api/tasks.ts` / types if needed | payload typing optional |
| `docs/superpowers/specs/2026-08-03-*.md` | Mark 已实现; cross-link roadmap spec |

---

### Task 1: Structured weekly goals from month slice

**Files:**
- Modify: `backend/app/services/plan_draft.py` (`_apply_month_slice`)
- Modify: `backend/tests/test_roadmap.py` (extend `test_apply_month_slice_appends_leaf_names` or add sibling test)

**Interfaces:**
- Consumes: `MonthSlice.subjects[code].syllabus_node_ids`, `resolve_syllabus_nodes`
- Produces: `weekly_goals_json` entries with `kind`, `subject_code`, `syllabus_node_ids` (string UUIDs), `title`, `description`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_roadmap.py`:

```python
def test_apply_month_slice_emits_focus_weekly_goals_with_node_ids(db_session):
    student = _seed_student(db_session)
    draft_rm = RoadmapDraftService().draft(db_session, student_user_id=student.id)
    month0 = draft_rm.months_json["months"][0]
    code, block = next(iter(month0["subjects"].items()))
    ids = list(block["syllabus_node_ids"])
    assert ids
    base = PlanDraft(
        weekly_goals_json=[{"title": "旧目标", "description": "仅文案"}],
        daily_time_budget_json=[],
        subject_phases_json={},
    )
    slice_ = MonthSlice(
        month=month0["month"],
        label=month0["label"],
        subjects={code: block},
        milestones=[],
    )
    out = PlanDraftService()._apply_month_slice(base, slice_, date.today(), db=db_session)
    focus = [
        g
        for g in out.weekly_goals_json
        if g.get("kind") == "focus" and g.get("subject_code") == code
    ]
    assert len(focus) == 1
    assert focus[0]["syllabus_node_ids"] == [str(x) for x in ids] or set(focus[0]["syllabus_node_ids"]) == {
        str(x) for x in ids
    }
    assert focus[0]["title"]
    # month banner / support goals may still exist without IDs
    assert any(g.get("title", "").startswith("本月：") for g in out.weekly_goals_json)
```

Normalize ID comparison to strings in the assertion to match JSON storage.

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend && .venv/bin/python -m pytest tests/test_roadmap.py::test_apply_month_slice_emits_focus_weekly_goals_with_node_ids -v
```

- [ ] **Step 3: Implement `_apply_month_slice` focus goals**

In `_apply_month_slice`, after building `weekly_goals` month banner insert, for each subject block with non-empty `syllabus_node_ids`:

```python
            id_strs = [str(x) for x in ids]
            names = leaf_names  # already resolved above in the phases loop — refactor to resolve once per code
            label = SUBJECT_LABELS.get(code, code)
            name_bit = "、".join(names[:4]) if names else focus or "本周节点"
            weekly_goals.append(
                {
                    "kind": "focus",
                    "subject_code": code,
                    "syllabus_node_ids": id_strs,
                    "title": f"本周：{label} — {name_bit}",
                    "description": notes or (f"本月重点：{focus}" if focus else "推进当月路线图叶子节点"),
                }
            )
```

Refactor the method so leaf ID resolution happens once per subject (shared by phases notes + focus goal). Keep existing month banner goal (`本月：{label}`) without `kind`/`syllabus_node_ids` (acts as support/banner).

Preserve existing daily budget and phases behavior.

- [ ] **Step 4: Run tests — PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/test_roadmap.py::test_apply_month_slice_emits_focus_weekly_goals_with_node_ids tests/test_roadmap.py::test_apply_month_slice_appends_leaf_names tests/test_plan_draft.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_draft.py backend/tests/test_roadmap.py
git commit -m "$(cat <<'EOF'
feat(plan): emit structured weekly focus goals from roadmap month slice

EOF
)"
```

---

### Task 2: Daily cascade from weekly focus + default today

**Files:**
- Modify: `backend/app/services/subject_agent.py`
- Modify: `backend/app/services/daily_task_generation.py` (default day = today; comment)
- Modify: `backend/app/routers/student_agent.py` (`target_date or date.today()`)
- Modify: `backend/tests/test_subject_agent_tasks.py` (+ helpers for master plan focus goals / wrong book)
- Possibly touch: `backend/tests/test_exam_profile_weights.py` if it assumed tomorrow

**Interfaces:**
- Consumes: active `MasterPlan` → `MasterPlanVersion.weekly_goals_json`; `ReportService.overview` weak nodes
- Produces: `DailyTask` with `payload.source=weekly_goal` or `report_weak`; default day today

Helper to load focus node IDs for subject (inline or small function in `subject_agent.py`):

```python
def _focus_node_ids_for_subject(db, student_user_id, subject_code) -> list[str]:
    # load MasterPlan.current_version_id → weekly_goals_json
    # return first focus goal's syllabus_node_ids for subject_code, else []
```

- [ ] **Step 1: Write failing tests**

In `test_subject_agent_tasks.py` (reuse seeding patterns from existing tests / factories):

```python
def test_apply_recommendations_defaults_to_today(db_session):
    # seed student + wrong book weak so recommendations non-empty OR seed focus goals
    ...
    out = SubjectAgentService().apply_report_recommendations(
        db_session, student_user_id=student.id, subject_code="english"
    )
    assert out.target_date == date.today()


def test_apply_uses_weekly_focus_nodes_and_one_weak_review(db_session):
    # 1) Create MasterPlanVersion with focus goal for english with node_ids [A, B]
    # 2) Create active WrongBookItem on node A (or unrelated weak C)
    # 3) apply_report_recommendations(..., target_date=date.today())
    # Assert: at least one study task with payload.source == "weekly_goal" and syllabus_node_id in {A,B}
    # Assert: at most one review_wrong with payload.source == "report_weak"
    # Assert: titles non-empty


def test_apply_falls_back_to_report_when_no_focus(db_session):
    # No structured focus on master plan; active wrong book with knowledge_node_id
    # Expect review_wrong (or existing recommendation types) with source report_recommendation
```

Ensure master plan seeding matches how other tests create `MasterPlan` / version (see `test_master_plan_pending.py` or planning helpers).

- [ ] **Step 2: Run tests — FAIL**

```bash
cd backend && .venv/bin/python -m pytest tests/test_subject_agent_tasks.py -v
```

- [ ] **Step 3: Implement cascade + today default**

1. Change default: `day = target_date or date.today()` in `apply_report_recommendations`.
2. Same for `DailyTaskGenerationService.run`: `day = target_date or today` (not `today + 1`).
3. Same for `student_agent.py` enqueue: `day = target_date or date.today()`.
4. In `apply_report_recommendations`:

```python
        focus_ids = _focus_node_ids_for_subject(db, student_user_id, subject_code)
        if focus_ids:
            # pick 1–2 nodes: index by weekday % len
            picks = ...
            for node_id in picks:
                # create study task, payload source weekly_goal, syllabus_node_id
                # resolve SyllabusNode.name for title: f"推进：{name}"
            weak = overview.weak_nodes  # already filtered by subject in overview
            if weak:
                # prefer weak.knowledge_node_id in focus_ids else weak[0]
                # create at most one review_wrong, source report_weak
            # optionally still append self_test/check_result from overview.recommendations
            # AFTER study/weak, only if budget allows — simplest: skip auto self_test when focus path used (YAGNI: skip self_test/check in focus path this period per plan priority)
        else:
            # existing loop over overview.recommendations
```

Spec allows self_test after advance under budget; **implement focus path without self_test/check_result first** (YAGNI) — only study + optional one weak. Document in commit. Fallback path keeps full recommendations.

5. `_maybe_add_profile_boost`: keep after either branch.

6. Resolve node names via `db.get(SyllabusNode, uuid)` or existing resolve helper.

- [ ] **Step 4: Run tests — PASS**

```bash
cd backend && .venv/bin/python -m pytest tests/test_subject_agent_tasks.py tests/test_exam_profile_weights.py tests/test_planner_chat_tools.py -q
```

Fix any tests that asserted `date.today() + timedelta(days=1)`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/subject_agent.py backend/app/services/daily_task_generation.py \
  backend/app/routers/student_agent.py backend/tests/test_subject_agent_tasks.py \
  backend/tests/test_exam_profile_weights.py
git commit -m "$(cat <<'EOF'
feat(tasks): generate daily work from weekly focus nodes

EOF
)"
```

---

### Task 3: Frontend labels and copy

**Files:**
- Modify: `frontend/src/pages/student/Workspace.tsx`
- Modify: `frontend/src/pages/student/Report.tsx`
- Modify: `frontend/src/api/tasks.ts` if `DailyTaskOut` needs `payload_json` typed (check existing type)
- Test: add/adjust `frontend/tests/WorkspaceTasks.test.tsx` if present; else skip FE test if none covers today list

**Interfaces:**
- Consumes: task `payload_json.source` (`weekly_goal` | `report_weak` | …)
- Produces: badge text; Report button「生成今日任务」

- [ ] **Step 1: Inspect task type + write/adjust test if WorkspaceTasks exists**

```bash
ls frontend/tests/*Workspace* frontend/tests/*Task* 2>/dev/null; rg -n "payload|今日任务|生成明日" frontend/src frontend/tests
```

If `WorkspaceTasks.test.tsx` exists, assert badge or button text. Else update Report test if any.

- [ ] **Step 2: Implement UI**

Workspace task row: if `payload_json?.source === "weekly_goal"` show「本周推进」; if `report_weak` show「薄弱复习」.

Report.tsx: change button label from「生成明日任务」to「生成今日任务」.

- [ ] **Step 3: Run FE tests**

```bash
cd frontend && npm test -- --run tests/WorkspaceTasks.test.tsx tests/Report.test.tsx 2>/dev/null || npm test -- --run tests/Report.test.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/student/Workspace.tsx frontend/src/pages/student/Report.tsx frontend/tests
git commit -m "$(cat <<'EOF'
feat(ui): label weekly vs weak daily tasks; generate-for-today copy

EOF
)"
```

---

### Task 4: Spec status + cross-link

**Files:**
- Modify: `docs/superpowers/specs/2026-08-03-weekly-goals-to-daily-cascade-design.md` → 已实现
- Modify: `docs/superpowers/specs/2026-06-25-annual-study-roadmap-design.md` — one-line cross-link under architecture or related work
- Add if missing from commits: this plan file under `docs/superpowers/plans/`

- [x] **Step 1: Update docs**
- [x] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-08-03-weekly-goals-to-daily-cascade-design.md \
  docs/superpowers/specs/2026-06-25-annual-study-roadmap-design.md \
  docs/superpowers/plans/2026-08-03-weekly-goals-to-daily-cascade.md
git commit -m "$(cat <<'EOF'
docs: mark weekly-to-daily cascade spec implemented

EOF
)"
```

---

## Spec coverage self-review

| Spec item | Task |
|-----------|------|
| Focus weekly goals with IDs from month slice | 1 |
| Weak not in weekly list | 1 |
| Daily prefer focus; ≤1 weak review | 2 |
| Fallback without focus | 2 |
| Default target today | 2 (+ router/cron) |
| UI labels / 今日文案 | 3 |
| Docs | 4 |

Placeholder scan: none intentional.
