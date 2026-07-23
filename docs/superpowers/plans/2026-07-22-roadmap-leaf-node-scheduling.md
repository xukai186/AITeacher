# Roadmap Leaf-Node Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Schedule annual study roadmaps at syllabus leaf-node granularity (UUID IDs), deepen seed trees to 3 levels (8+ leaves per L1), inject current-month leaves into 7-day tactical plans, and group leaves by parent chapter in the student UI.

**Architecture:** Extend existing `StudyRoadmap` / `RoadmapDraftService` (no new entities). Seed becomes root → L1 → leaf; draft outline uses `leaf_nodes_for_placement`; `months_json` stores `syllabus_node_ids`; GET enrich + `PlanDraftService` resolve IDs to `{id,name,parent_name}`; MasterPlan groups by `parent_name`.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-07-22-roadmap-leaf-node-scheduling-design.md`

## Global Constraints

- Store leaf UUIDs in `syllabus_node_ids` (new drafts); do not write `syllabus_nodes` names for new versions
- 2–4 leaf IDs per subject per month; no cross-month duplicate leaf IDs
- Invalid LLM IDs / empty month-subject / cross-month dup → discard LLM draft, use full rule draft
- Confirm: whitelist ID check when `syllabus_node_ids` present; old name-only pending may confirm without ID check
- Leaf nodes under tracked L1 (e.g. 高数) must copy parent `meta_json.tracks`
- No week-level scheduling inside a month; no student/staff JSON edit; no monthly LLM full regenerate
- Old name-only roadmaps remain GET-readable

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/seed_syllabus.py` | 3-level tree; ≥8 leaves per L1; leaves copy L1 tracks |
| `backend/app/seed_past_exams.py` | Point samples at real leaf names |
| `backend/app/services/placement_paper_context.py` | `_resolve_node_for_area` match leaf name or parent_name |
| `backend/tests/test_syllabus_seed.py` | Depth / count / track / idempotency |
| `backend/app/services/roadmap_draft.py` | Leaf outline; ID rule/LLM; parse whitelist |
| `backend/app/services/roadmap_resolve.py` | **New** shared resolve helper |
| `backend/app/schemas/roadmap.py` | `syllabus_node_ids` + `syllabus_nodes_resolved` |
| `backend/app/services/roadmap_activation.py` | Confirm whitelist; GET enrich via resolve |
| `backend/app/routers/student_roadmap.py` | Enrich versions in `_state_out` / confirm response |
| `backend/app/routers/org_students.py` | Same enrich for org roadmap GET |
| `backend/app/services/plan_draft.py` | Inject month leaves into phases / LLM prompt |
| `backend/app/services/roadmap_context.py` | MonthSlice subjects already pass dicts through (no change required if resolve is at apply/GET) |
| `frontend/src/api/roadmap.ts` | Types for resolved leaves |
| `frontend/src/pages/student/MasterPlan.tsx` | Grouped leaf display |
| `frontend/tests/` (new or extend) | Grouping render test if pattern exists; else backend-heavy |
| `backend/tests/test_roadmap.py` | Leaf IDs, confirm reject, tactical notes |
| `docs/superpowers/specs/2026-07-22-roadmap-leaf-node-scheduling-design.md` | Status → 已实现 |

---

### Task 1: Deepen syllabus seed to leaf nodes

**Files:**
- Modify: `backend/app/seed_syllabus.py`
- Modify: `backend/app/seed_past_exams.py`
- Modify: `backend/app/services/placement_paper_context.py` (`_resolve_node_for_area`)
- Test: `backend/tests/test_syllabus_seed.py`
- Test: `backend/tests/test_placement_paper_context.py` (regression)

**Interfaces:**
- Consumes: existing `_ensure_node`, `seed_minimal_syllabus`, `leaf_nodes_for_placement`
- Produces: 3-level tree; every L1 has ≥8 leaf children; math 高数 leaves have `meta_json={"tracks":["math_1"]}`; past exams attach to leaf names; `_resolve_node_for_area` matches leaf name OR parent name

- [ ] **Step 1: Write the failing seed depth test**

Replace / extend `backend/tests/test_syllabus_seed.py`:

```python
from sqlalchemy import select

from app.models import SyllabusNode
from app.seed_syllabus import seed_minimal_syllabus
from app.services.placement_paper_context import leaf_nodes_for_placement


def test_seed_minimal_syllabus_idempotent(db_session):
    seed_minimal_syllabus(db_session)
    seed_minimal_syllabus(db_session)
    rows = list(db_session.execute(select(SyllabusNode)).scalars().all())
    assert len(rows) > 0


def test_seed_has_eight_plus_leaves_per_l1(db_session):
    seed_minimal_syllabus(db_session)
    nodes = list(db_session.execute(select(SyllabusNode)).scalars().all())
    by_id = {n.id: n for n in nodes}
    roots = {n.id for n in nodes if n.parent_id is None}
    l1_nodes = [n for n in nodes if n.parent_id in roots]
    assert l1_nodes
    for chapter in l1_nodes:
        leaves = [n for n in nodes if n.parent_id == chapter.id]
        assert len(leaves) >= 8, f"{chapter.subject_code}/{chapter.name} has {len(leaves)} leaves"
        if chapter.meta_json and chapter.meta_json.get("tracks"):
            for leaf in leaves:
                assert leaf.meta_json == chapter.meta_json


def test_math2_excludes_gaoshu_leaves(db_session):
    seed_minimal_syllabus(db_session)
    leaves = leaf_nodes_for_placement(
        db_session,
        subject_code="math",
        exam_year=2027,
        math_track="math_2",
    )
    names = {n.name for n in leaves}
    assert "极限" not in names  # under 高数 / math_1
    assert names  # 线代/概率 leaves remain
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_syllabus_seed.py -q`

Expected: FAIL (current seed has 0 leaves under L1; L1 are themselves leaves)

- [ ] **Step 3: Implement 3-level seed data**

In `backend/app/seed_syllabus.py`, change structure so each L1 has a list of leaf names. Use at least these leaves (add more if needed to reach 8):

```python
# subject -> (root, [(l1_name, meta, [leaf_names...]), ...])
_MINIMAL_SYLLABUS: dict[str, tuple[str, list[tuple[str, dict | None, list[str]]]]] = {
    "english": (
        "英语",
        [
            (
                "阅读",
                None,
                [
                    "细节题",
                    "主旨题",
                    "推断题",
                    "态度题",
                    "词汇题",
                    "例证题",
                    "篇章结构",
                    "长难句",
                ],
            ),
            (
                "翻译",
                None,
                [
                    "词义选择",
                    "长句拆分",
                    "定语从句译",
                    "被动语态译",
                    "名词性从句译",
                    "状语从句译",
                    "增译减译",
                    "语序调整",
                ],
            ),
            (
                "写作",
                None,
                [
                    "图表描述",
                    "图画寓意",
                    "开头段",
                    "中间论证",
                    "结尾段",
                    "连接词",
                    "应用文格式",
                    "书信请求",
                ],
            ),
        ],
    ),
    "math": (
        "数学",
        [
            (
                "高数",
                {"tracks": ["math_1"]},
                ["极限", "连续", "导数", "微分", "不定积分", "定积分", "微分方程", "多元函数"],
            ),
            (
                "线代",
                None,
                ["行列式", "矩阵运算", "逆矩阵", "线性方程组", "向量组", "特征值", "二次型", "相似对角化"],
            ),
            (
                "概率",
                None,
                ["随机事件", "条件概率", "随机变量", "分布函数", "期望方差", "常见分布", "大数定律", "中心极限"],
            ),
        ],
    ),
    "politics": (
        "政治",
        [
            (
                "马原",
                None,
                ["唯物论", "辩证法", "认识论", "唯物史观", "实践观", "矛盾规律", "否定之否定", "量变质变"],
            ),
            (
                "毛中特",
                None,
                ["新民主主义", "社会主义改造", "改革开放", "市场经济", "一国两制", "三个代表", "科学发展观", "中国特色"],
            ),
            (
                "史纲",
                None,
                ["鸦片战争", "辛亥革命", "五四运动", "建党", "长征", "抗战", "解放战争", "建国初期"],
            ),
            (
                "思修",
                None,
                ["理想信念", "中国精神", "人生价值", "道德规范", "法治思维", "宪法法律", "权利义务", "社会责任"],
            ),
        ],
    ),
}
```

Update `seed_minimal_syllabus` to create L1 then each leaf with `meta_json=child_meta` (same as L1). Update module docstring to "3-level".

- [ ] **Step 4: Remap past exams + parent_name resolve**

In `seed_past_exams.py`, change leaf_name fields from L1 names to concrete leaves, e.g. `"阅读"` → `"主旨题"`, `"翻译"` → `"词义选择"`, `"高数"` → `"导数"`, `"线代"` → `"行列式"`, `"马原"` → `"实践观"`, `"史纲"` → `"五四运动"`.

In `placement_paper_context.py` `_resolve_node_for_area`:

```python
def _resolve_node_for_area(
    leaves: list[SyllabusNode],
    knowledge_area: str | None,
    *,
    fallback_index: int,
    weak_node_ids: set[uuid.UUID],
    parent_name_by_id: dict[uuid.UUID, str] | None = None,
) -> SyllabusNode:
    by_name = {n.name: n for n in leaves}
    if knowledge_area and knowledge_area in by_name:
        return by_name[knowledge_area]
    if knowledge_area and parent_name_by_id:
        for node in leaves:
            if parent_name_by_id.get(node.parent_id) == knowledge_area:
                return node
    for node in leaves:
        if node.id in weak_node_ids:
            return node
    return leaves[fallback_index % len(leaves)]
```

Update `build_placement_slots` to build `parent_name_by_id` from all year nodes (or pass parent map). Keep templates' `knowledge_area` as L1 names ("阅读", "高数") so they resolve via parent_name.

- [ ] **Step 5: Run seed + placement context tests**

Run: `cd backend && uv run pytest tests/test_syllabus_seed.py tests/test_placement_paper_context.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/seed_syllabus.py backend/app/seed_past_exams.py \
  backend/app/services/placement_paper_context.py \
  backend/tests/test_syllabus_seed.py
git commit -m "$(cat <<'EOF'
feat: deepen syllabus seed to leaf nodes

EOF
)"
```

---

### Task 2: Roadmap draft emits and validates leaf IDs

**Files:**
- Modify: `backend/app/services/roadmap_draft.py`
- Test: `backend/tests/test_roadmap.py`

**Interfaces:**
- Consumes: `leaf_nodes_for_placement`, Task 1 seed
- Produces: `syllabus_outline[code] = [{id, name, parent_name}, ...]`; rule/LLM drafts write `syllabus_node_ids: list[str]` (2–4 per subject/month); no `syllabus_nodes` key in new drafts; invalid LLM → `None` so caller falls back to rules

- [ ] **Step 1: Write failing draft tests**

Add to `backend/tests/test_roadmap.py`:

```python
def test_roadmap_draft_rule_uses_leaf_ids(db_session):
    student = _seed_student(db_session)
    draft = RoadmapDraftService().draft(db_session, student_user_id=student.id)
    months = draft.months_json.get("months") or []
    assert months
    seen: set[str] = set()
    for month in months:
        for code, block in (month.get("subjects") or {}).items():
            ids = block.get("syllabus_node_ids") or []
            assert 1 <= len(ids) <= 4
            assert "syllabus_nodes" not in block or block.get("syllabus_nodes") in (None, [])
            for nid in ids:
                assert nid not in seen
                seen.add(nid)


def test_parse_llm_rejects_invalid_leaf_id(db_session):
    student = _seed_student(db_session)
    svc = RoadmapDraftService()
    context = svc._build_context(db_session, student_user_id=student.id, subject_codes=["english"])
    month_keys = ["2026-07"]
    valid_id = context["syllabus_outline"]["english"][0]["id"]
    raw = json.dumps(
        {
            "summary": {"text": "t"},
            "months": [
                {
                    "month": "2026-07",
                    "label": "基础月",
                    "subjects": {
                        "english": {
                            "focus": "阅读",
                            "syllabus_node_ids": [valid_id, "00000000-0000-0000-0000-000000000000"],
                            "weekly_hours_hint": 12,
                            "notes": "",
                        }
                    },
                    "milestones": [],
                }
            ],
        },
        ensure_ascii=False,
    )
    parsed = svc._parse_llm_draft(
        raw,
        subject_codes=["english"],
        start_date=__import__("datetime").date(2026, 7, 1),
        end_date=__import__("datetime").date(2026, 7, 31),
        month_keys=month_keys,
        allowed_ids_by_subject={
            code: {n["id"] for n in context["syllabus_outline"].get(code, [])}
            for code in ["english"]
        },
    )
    assert parsed is None
```

(Import `json` at top of test file if missing.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_roadmap.py::test_roadmap_draft_rule_uses_leaf_ids tests/test_roadmap.py::test_parse_llm_rejects_invalid_leaf_id -q`

Expected: FAIL

- [ ] **Step 3: Update `_build_context` outline to leaves**

Replace L1 selection in `roadmap_draft.py` `_build_context` with:

```python
from app.services.placement_paper_context import leaf_nodes_for_placement

# inside loop per code:
leaves = leaf_nodes_for_placement(
    db,
    subject_code=code,
    exam_year=exam_year,
    english_track=english_track,
    math_track=math_track,
)
by_id = {n.id: n for n in syllabus_nodes_for_year(db, subject_code=code, exam_year=exam_year)}
syllabus_outline[code] = []
for n in leaves:
    parent = by_id.get(n.parent_id) if n.parent_id else None
    syllabus_outline[code].append(
        {
            "id": str(n.id),
            "name": n.name,
            "parent_name": parent.name if parent else None,
        }
    )
```

(Remove unused `filter_nodes_for_track` call in that loop if leaf helper already filters.)

- [ ] **Step 4: Update rule draft to emit IDs (2–4 per month)**

Rewrite `_draft_with_rules` node cycling:

```python
nodes_by_subject: dict[str, list[dict]] = {
    code: list(context["syllabus_outline"].get(code, []))
    for code in codes
}
# each month take 2 leaves (or remaining), advance index; cap 4
PER_MONTH = 2
...
chunk = []
for _ in range(PER_MONTH):
    if not names:
        break
    item = names[idx[code] % len(names)]
    idx[code] += 1
    chunk.append(item)
# dedupe within month by id
ids = []
seen_local = set()
for item in chunk:
    if item["id"] not in seen_local:
        seen_local.add(item["id"])
        ids.append(item["id"])
label_names = "、".join(item["name"] for item in chunk)
subjects_block[code] = {
    "focus": f"{SUBJECT_LABELS.get(code, code)} · {label_names}",
    "syllabus_node_ids": ids[:4],
    "weekly_hours_hint": weekly_hours,
    "notes": f"本月重点学习 {label_names}，按周完成系统任务。",
}
```

Prefer **no cross-month reuse**: slice a flat permutation of all leaves across months (round-robin without wrapping onto already used IDs when possible). If months × 2 < leaf count, leave remainder uncovered (audit log optional; do not fail).

Update summary text to mention 叶子知识点.

- [ ] **Step 5: Update LLM prompt + `_parse_llm_draft`**

- Prompt: ask for `syllabus_node_ids` from outline `id`s; 2–4 per subject/month; no cross-month reuse; no math if math_track=none.
- Change `_parse_llm_draft` signature to accept `allowed_ids_by_subject: dict[str, set[str]]`.
- For each subject block: read `syllabus_node_ids`, normalize to str, whitelist filter; if any ID not allowed → return `None` (whole draft invalid).
- Cap 4; require non-empty for each subject_code present in subject_codes when block exists.
- After building all months, if any leaf id appears in two months → return `None`.
- Do not write `syllabus_nodes`.
- Call site in `_draft_with_llm`: pass allowed sets from context outline; if parse returns None, outer `draft()` already falls back to rules.

- [ ] **Step 6: Run roadmap unit tests**

Run: `cd backend && uv run pytest tests/test_roadmap.py -q`

Expected: PASS (including existing confirm/enqueue tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/roadmap_draft.py backend/tests/test_roadmap.py
git commit -m "$(cat <<'EOF'
feat: draft roadmaps with syllabus leaf node IDs

EOF
)"
```

---

### Task 3: Resolve helper, API enrich, confirm whitelist

**Files:**
- Create: `backend/app/services/roadmap_resolve.py`
- Modify: `backend/app/schemas/roadmap.py`
- Modify: `backend/app/services/roadmap_activation.py`
- Modify: `backend/app/routers/student_roadmap.py`
- Modify: `backend/app/routers/org_students.py` (`_roadmap_state_out`)
- Test: `backend/tests/test_roadmap.py`

**Interfaces:**
- Consumes: Task 2 `syllabus_node_ids` in months_json
- Produces:
  - `resolve_syllabus_nodes(db, ids: list[str]) -> list[dict]` with `{id, name, parent_name}`
  - `enrich_months_json(db, months_json) -> dict` adding `syllabus_nodes_resolved` per subject block
  - Confirm raises 400 `路线图含无效考纲节点` when IDs present but invalid
  - GET `/student/roadmap` and org GET return enriched versions

- [ ] **Step 1: Write failing tests**

```python
def test_roadmap_get_includes_resolved_leaves(client, db_session):
    student = _seed_student(db_session)
    job = RoadmapGenerationJobService().enqueue(db_session, student_user_id=student.id)
    RoadmapGenerationJobService().run_job(db_session, job.job_id)
    token = client.post("/auth/login", json={"email": student.email, "password": "pw"}).json()["access_token"]
    state = client.get("/student/roadmap", headers={"Authorization": f"Bearer {token}"})
    assert state.status_code == 200
    pending = state.json()["pending_version"]
    assert pending is not None
    month0 = pending["months_json"]["months"][0]
    block = next(iter(month0["subjects"].values()))
    assert block.get("syllabus_node_ids")
    resolved = block.get("syllabus_nodes_resolved")
    assert resolved
    assert resolved[0]["name"]
    assert "parent_name" in resolved[0]


def test_confirm_rejects_invalid_leaf_ids(client, db_session):
    student = _seed_student(db_session)
    job = RoadmapGenerationJobService().enqueue(db_session, student_user_id=student.id)
    RoadmapGenerationJobService().run_job(db_session, job.job_id)
    state = RoadmapActivationService().get_state(db_session, student_user_id=student.id)
    pending = state["pending_version"]
    months = pending.months_json["months"]
    # corrupt one id
    first_code = next(iter(months[0]["subjects"]))
    months[0]["subjects"][first_code]["syllabus_node_ids"] = [
        "00000000-0000-0000-0000-000000000099"
    ]
    from sqlalchemy.orm.attributes import flag_modified
    pending.months_json = {"months": months}
    flag_modified(pending, "months_json")
    db_session.commit()
    token = client.post("/auth/login", json={"email": student.email, "password": "pw"}).json()["access_token"]
    confirm = client.post("/student/roadmap/confirm", headers={"Authorization": f"Bearer {token}"})
    assert confirm.status_code == 400
    assert "无效" in confirm.json()["detail"]
```

Note: `get_state` may return ORM or dict — match existing `test_roadmap.py` patterns (`state["pending_version"]` is ORM object in activation service). Adjust corruption to load `StudyRoadmapVersion` via `db_session.get`.

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && uv run pytest tests/test_roadmap.py::test_roadmap_get_includes_resolved_leaves tests/test_roadmap.py::test_confirm_rejects_invalid_leaf_ids -q`

Expected: FAIL

- [ ] **Step 3: Implement `roadmap_resolve.py`**

```python
# backend/app/services/roadmap_resolve.py
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SyllabusNode


def resolve_syllabus_nodes(db: Session, node_ids: list[str]) -> list[dict]:
    if not node_ids:
        return []
    uuids: list[uuid.UUID] = []
    for raw in node_ids:
        try:
            uuids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not uuids:
        return []
    nodes = list(
        db.execute(select(SyllabusNode).where(SyllabusNode.id.in_(uuids))).scalars().all()
    )
    by_id = {n.id: n for n in nodes}
    parent_ids = {n.parent_id for n in nodes if n.parent_id}
    parents = {}
    if parent_ids:
        parents = {
            p.id: p
            for p in db.execute(select(SyllabusNode).where(SyllabusNode.id.in_(parent_ids))).scalars()
        }
    out: list[dict] = []
    for raw in node_ids:
        try:
            uid = uuid.UUID(str(raw))
        except ValueError:
            continue
        node = by_id.get(uid)
        if node is None:
            continue
        parent = parents.get(node.parent_id) if node.parent_id else None
        out.append(
            {
                "id": str(node.id),
                "name": node.name,
                "parent_name": parent.name if parent else None,
            }
        )
    return out


def enrich_months_json(db: Session, months_json: dict | None) -> dict:
    if not months_json:
        return {"months": []}
    months = months_json.get("months") or []
    enriched_months = []
    for item in months:
        if not isinstance(item, dict):
            continue
        subjects = item.get("subjects") or {}
        new_subjects = {}
        if isinstance(subjects, dict):
            for code, block in subjects.items():
                if not isinstance(block, dict):
                    continue
                block_out = dict(block)
                ids = block.get("syllabus_node_ids") or []
                if ids:
                    block_out["syllabus_nodes_resolved"] = resolve_syllabus_nodes(db, list(ids))
                else:
                    # legacy name-only
                    names = block.get("syllabus_nodes") or []
                    block_out["syllabus_nodes_resolved"] = [
                        {"id": None, "name": str(n), "parent_name": None} for n in names if n
                    ]
                new_subjects[code] = block_out
        enriched_months.append({**item, "subjects": new_subjects})
    return {**months_json, "months": enriched_months}


def validate_months_leaf_ids(db: Session, months_json: dict | None) -> list[str]:
    """Return list of invalid id strings; empty if OK or legacy name-only."""
    if not months_json:
        return []
    has_ids = False
    invalid: list[str] = []
    seen: set[str] = set()
    all_ids: list[str] = []
    for item in months_json.get("months") or []:
        if not isinstance(item, dict):
            continue
        for block in (item.get("subjects") or {}).values():
            if not isinstance(block, dict):
                continue
            ids = block.get("syllabus_node_ids") or []
            if ids:
                has_ids = True
            for raw in ids:
                s = str(raw)
                if s in seen:
                    invalid.append(s)
                seen.add(s)
                all_ids.append(s)
    if not has_ids:
        return []
    resolved = resolve_syllabus_nodes(db, all_ids)
    ok = {r["id"] for r in resolved}
    for s in all_ids:
        if s not in ok:
            invalid.append(s)
    return invalid
```

- [ ] **Step 4: Schema + activation + routers**

`RoadmapMonthSubjectOut`:

```python
class SyllabusNodeResolvedOut(BaseModel):
    id: str | None = None
    name: str
    parent_name: str | None = None


class RoadmapMonthSubjectOut(BaseModel):
    focus: str = ""
    syllabus_nodes: list[str] = Field(default_factory=list)
    syllabus_node_ids: list[str] = Field(default_factory=list)
    syllabus_nodes_resolved: list[SyllabusNodeResolvedOut] = Field(default_factory=list)
    weekly_hours_hint: int | None = None
    notes: str = ""
```

In `confirm_pending`, before activating:

```python
from fastapi import HTTPException, status
from app.services.roadmap_resolve import validate_months_leaf_ids

bad = validate_months_leaf_ids(db, pending.months_json)
if bad:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "路线图含无效考纲节点")
```

Enrich in routers when building `StudyRoadmapVersionOut`: either mutate a copy of `months_json` via `enrich_months_json` before `model_validate`, or add helper `version_out(db, version)`.

Example in `student_roadmap.py`:

```python
from app.services.roadmap_resolve import enrich_months_json

def _version_out(db, version) -> StudyRoadmapVersionOut | None:
    if version is None:
        return None
    data = StudyRoadmapVersionOut.model_validate(version).model_dump()
    data["months_json"] = enrich_months_json(db, data.get("months_json"))
    return StudyRoadmapVersionOut.model_validate(data)
```

Apply same in org router.

- [ ] **Step 5: Run tests**

Run: `cd backend && uv run pytest tests/test_roadmap.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/roadmap_resolve.py backend/app/schemas/roadmap.py \
  backend/app/services/roadmap_activation.py \
  backend/app/routers/student_roadmap.py backend/app/routers/org_students.py \
  backend/tests/test_roadmap.py
git commit -m "$(cat <<'EOF'
feat: resolve and validate roadmap leaf node IDs

EOF
)"
```

---

### Task 4: Inject month leaves into tactical PlanDraft

**Files:**
- Modify: `backend/app/services/plan_draft.py`
- Test: `backend/tests/test_roadmap.py` (extend confirm assertion) and/or existing plan draft tests

**Interfaces:**
- Consumes: `MonthSlice.subjects[*].syllabus_node_ids` (or legacy `syllabus_nodes`); `resolve_syllabus_nodes`
- Produces: `_apply_month_slice` notes include `本月叶子：…`; `draft_initial_plans` LLM prompt includes `current_month_leaves`; `light_revise_draft` also applies month slice leaves when MonthSlice exists

- [ ] **Step 1: Write failing test**

```python
def test_confirm_plan_notes_include_leaf_names(client, db_session):
    student = _seed_student(db_session)
    job = RoadmapGenerationJobService().enqueue(db_session, student_user_id=student.id)
    RoadmapGenerationJobService().run_job(db_session, job.job_id)
    token = client.post("/auth/login", json={"email": student.email, "password": "pw"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/student/roadmap/confirm", headers=headers).status_code == 200
    master = client.get("/student/master-plan", headers=headers).json()
    # Find any subject plan phase notes containing 本月叶子 or a known leaf name
    # Prefer asserting via PlanDraftService unit if master-plan JSON shape is awkward:
```

Prefer a direct unit test:

```python
from datetime import date
from app.services.plan_draft import PlanDraft, PlanDraftService
from app.services.roadmap_context import MonthSlice

def test_apply_month_slice_appends_leaf_names(db_session):
    student = _seed_student(db_session)
    draft_rm = RoadmapDraftService().draft(db_session, student_user_id=student.id)
    month0 = draft_rm.months_json["months"][0]
    code, block = next(iter(month0["subjects"].items()))
    leaf_id = block["syllabus_node_ids"][0]
    from app.services.roadmap_resolve import resolve_syllabus_nodes
    name = resolve_syllabus_nodes(db_session, [leaf_id])[0]["name"]
    base = PlanDraft(
        weekly_goals_json=[],
        daily_time_budget_json=[],
        subject_phases_json={code: [{"title": "x", "days": 7, "notes": "旧"}]},
    )
    slice_ = MonthSlice(
        month=month0["month"],
        label=month0["label"],
        subjects={code: block},
        milestones=[],
    )
    out = PlanDraftService()._apply_month_slice(base, slice_, date.today(), db=db_session)
    notes = out.subject_phases_json[code][0]["notes"]
    assert name in notes or "本月叶子" in notes
```

Update `_apply_month_slice` signature to accept optional `db: Session | None = None` for resolve; callers that have db pass it. If `db` is None and only IDs present, skip name resolve and keep focus/notes.

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && uv run pytest tests/test_roadmap.py::test_apply_month_slice_appends_leaf_names -q`

Expected: FAIL

- [ ] **Step 3: Implement `_apply_month_slice` leaf injection**

```python
def _apply_month_slice(
    self, draft: PlanDraft, month_slice: MonthSlice | None, today: date, db: Session | None = None
) -> PlanDraft:
    ...
    for code, block in month_slice.subjects.items():
        ...
        focus = str(block.get("focus") or "").strip()
        notes = str(block.get("notes") or "").strip()
        leaf_names: list[str] = []
        ids = block.get("syllabus_node_ids") or []
        if ids and db is not None:
            from app.services.roadmap_resolve import resolve_syllabus_nodes
            leaf_names = [r["name"] for r in resolve_syllabus_nodes(db, list(ids))]
        if not leaf_names:
            leaf_names = [str(n) for n in (block.get("syllabus_nodes") or []) if n]
        leaf_line = f"本月叶子：{'、'.join(leaf_names)}" if leaf_names else ""
        primary = notes or (f"本月重点：{focus}" if focus else leaf_line)
        if leaf_line and leaf_line not in primary:
            primary = f"{primary}\n{leaf_line}" if primary else leaf_line
        subject_phases[code] = [
            {"title": f"{label} · {month_slice.label}", "days": 7, "notes": primary}
        ]
```

Update all call sites of `_apply_month_slice` to pass `db`.

In `_draft_with_llm` (plan_draft), if `month_slice` available before LLM, append to prompt:

```python
f"当月路线图叶子 current_month_leaves：{json.dumps(...)}"
```

Build leaves dict from resolve. Rule path already goes through `_apply_month_slice`.

Ensure `light_revise_draft` still calls `_apply_month_slice` with db when MonthSlice exists (add if missing).

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_roadmap.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plan_draft.py backend/tests/test_roadmap.py
git commit -m "$(cat <<'EOF'
feat: inject roadmap leaf nodes into weekly plan drafts

EOF
)"
```

---

### Task 5: Frontend grouped leaf display

**Files:**
- Modify: `frontend/src/api/roadmap.ts`
- Modify: `frontend/src/pages/student/MasterPlan.tsx`
- Test: add `frontend/tests/MasterPlanRoadmap.test.tsx` (follow WorkspaceTasks patterns) OR skip if no MasterPlan test harness — prefer adding a small render test

**Interfaces:**
- Consumes: `syllabus_nodes_resolved: { id, name, parent_name }[]`
- Produces: UI lines like `阅读：细节题、主旨题`; fallback to flat `syllabus_nodes` names

- [ ] **Step 1: Extend API types**

```typescript
export type SyllabusNodeResolved = {
  id?: string | null;
  name: string;
  parent_name?: string | null;
};

// inside subject block:
syllabus_node_ids?: string[];
syllabus_nodes_resolved?: SyllabusNodeResolved[];
syllabus_nodes?: string[];
```

- [ ] **Step 2: Write failing UI test**

Create `frontend/tests/MasterPlanRoadmap.test.tsx` that renders a helper-exported `groupLeavesByParent` or the timeline with mocked months:

```tsx
import { describe, it, expect } from "vitest";
import { groupLeavesByParent } from "../src/pages/student/MasterPlan";

describe("groupLeavesByParent", () => {
  it("groups by parent_name", () => {
    const lines = groupLeavesByParent([
      { name: "细节题", parent_name: "阅读" },
      { name: "主旨题", parent_name: "阅读" },
      { name: "词义选择", parent_name: "翻译" },
    ]);
    expect(lines).toEqual(["阅读：细节题、主旨题", "翻译：词义选择"]);
  });
});
```

Export `groupLeavesByParent` from `MasterPlan.tsx` (or a tiny `roadmapDisplay.ts` next to the page — prefer `frontend/src/pages/student/roadmapDisplay.ts` to avoid exporting from page).

- [ ] **Step 3: Run to verify fail**

Run: `cd frontend && npx vitest run MasterPlanRoadmap`

Expected: FAIL (module missing)

- [ ] **Step 4: Implement grouping + timeline**

`frontend/src/pages/student/roadmapDisplay.ts`:

```typescript
import type { SyllabusNodeResolved } from "../../api/roadmap";

export function groupLeavesByParent(nodes: SyllabusNodeResolved[]): string[] {
  const order: string[] = [];
  const map = new Map<string, string[]>();
  for (const n of nodes) {
    const parent = n.parent_name?.trim() || "考纲";
    if (!map.has(parent)) {
      map.set(parent, []);
      order.push(parent);
    }
    map.get(parent)!.push(n.name);
  }
  return order.map((p) => `${p}：${map.get(p)!.join("、")}`);
}
```

In `RoadmapTimeline`, replace syllabus_nodes join:

```tsx
const resolved = block.syllabus_nodes_resolved?.length
  ? block.syllabus_nodes_resolved
  : (block.syllabus_nodes ?? []).map((name) => ({ name, parent_name: null }));
const lines = groupLeavesByParent(resolved);
...
{lines.length ? (
  <div className="text-xs text-slate-500 space-y-0.5">
    {lines.map((line) => (
      <p key={line}>考纲：{line}</p>
    ))}
  </div>
) : null}
```

(Or single label「考纲」with multiple lines without repeating prefix — use `lines.map` as `阅读：…` without extra「考纲：」 if line already has chapter.)

Preferred display:

```tsx
{lines.map((line) => (
  <p key={line} className="text-xs text-slate-500">{line}</p>
))}
```

- [ ] **Step 5: Run vitest**

Run: `cd frontend && npx vitest run MasterPlanRoadmap`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/roadmap.ts frontend/src/pages/student/MasterPlan.tsx \
  frontend/src/pages/student/roadmapDisplay.ts frontend/tests/MasterPlanRoadmap.test.tsx
git commit -m "$(cat <<'EOF'
feat: show roadmap leaves grouped by chapter

EOF
)"
```

---

### Task 6: Regression sweep and mark spec implemented

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-roadmap-leaf-node-scheduling-design.md` (状态 → 已实现)
- Test: backend placement + roadmap + syllabus; frontend MasterPlanRoadmap

- [ ] **Step 1: Run backend suites**

Run: `cd backend && uv run pytest tests/test_syllabus_seed.py tests/test_placement_paper_context.py tests/test_roadmap.py tests/test_placement_flow.py -q`

Expected: PASS

- [ ] **Step 2: Run frontend suite**

Run: `cd frontend && npx vitest run MasterPlanRoadmap WorkspaceTasks`

Expected: PASS

- [ ] **Step 3: Update spec status**

Change header `**状态：** 待实现` → `**状态：** 已实现`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-22-roadmap-leaf-node-scheduling-design.md
git commit -m "$(cat <<'EOF'
docs: mark roadmap leaf-node scheduling spec implemented

EOF
)"
```

---

## Spec coverage self-check

| Spec requirement | Task |
|------------------|------|
| Seed 3-level, ≥8 leaves/L1, copy tracks | Task 1 |
| Past exams / placement still work | Task 1 |
| Outline = leaves with id/name/parent_name | Task 2 |
| `syllabus_node_ids` 2–4/month; no new `syllabus_nodes` | Task 2 |
| Invalid LLM → full rule draft | Task 2 |
| Cross-month no duplicate IDs | Task 2 |
| GET enrich `syllabus_nodes_resolved` | Task 3 |
| Confirm whitelist 400 | Task 3 |
| Legacy name-only GET + confirm | Task 3 |
| Tactical notes + LLM inject leaves | Task 4 |
| light_revise reads MonthSlice leaves | Task 4 |
| UI group by parent_name | Task 5 |
| Spec status 已实现 | Task 6 |
| Week-level / JSON edit / monthly LLM regen | OUT OF SCOPE |

---

## Self-review notes

- Types aligned: `syllabus_node_ids: list[str]`, resolved `{id, name, parent_name}`, confirm detail `路线图含无效考纲节点`
- `_apply_month_slice(..., db=)` added in Task 4 — callers updated in same task
- Past-exam + `_resolve_node_for_area` parent match keeps templates on L1 `knowledge_area` without rewriting templates
