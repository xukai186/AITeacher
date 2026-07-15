# 摸底考试一科只考一遍 — 产品设计规格

**日期：** 2026-07-15  
**状态：** 待实现  
**依赖：** P3 摸底（`PlacementPaper` / `PlacementSubmission`）、学生工作台、档案变更作废摸底

---

## 1. 背景与目标

摸底按产品语义应为**入学一次性定级**：每科交卷后不可再考。当前后端已拒绝重复 `submit`，但：

1. `POST /student/placement/start` 对已交卷科目仍返回 200 + `paper_id`，前端会继续进入试卷页，体验像能「再考一场」；
2. 工作台始终显示「开始摸底测评」，未反映已完成状态；
3. `GET /student/placement` 的 `status` 使用试卷表字段（`ready` / `generating` / `failed`），**不会**标为 `submitted`，前端无法据此禁用按钮。

本期收紧学生侧入口与 start 语义，明确「一科一遍」。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 重考策略 | **不允许**学生主动重考（方案 1：前端闸门 + start 硬拒绝） |
| 已完成后工作台 | 灰态 **「已完成」**，不可点，**不**跳转旧卷 |
| 结果查看 | 仍走学情 / 错题（及试卷中心既有入口）；本期**不**新增工作台「查看结果」 |
| 粒度 | **按科目**独立；未交科目仍可测 |
| 例外 | 档案**结构变更**（专业 / 卷种 / 科目）沿用 `invalidate_placement_on_track_change` 作废后可再开；CET/数学轻量修订**不**作废 |

---

## 3. 后端行为

### 3.1 `POST /student/placement/start`

- 请求指定 `subject_code` 且该科已有 `PlacementSubmission` → **HTTP 400**，`detail`: `该科摸底已完成`  
  （不再返回 200 与可导航 `paper_id`）
- 未指定 `subject_code`：跳过已交科目，选下一未完成科（保持现有优先逻辑）；若全部启用科目均已交 → **400**，`detail`: `全部科目摸底已完成`

### 3.2 `POST /student/placement/{paper_id}/submit`

- 已交卷拒绝逻辑保留；`detail` 统一为中文：`该科摸底已完成`（替换 `placement already submitted`）

### 3.3 `GET /student/placement`

- `PlacementPaperSummary.status` 改为 `PlacementService._paper_status_label` 结果：  
  有 submission → `submitted`；否则沿用 `generating` / `failed` / `ready`（与 start 返回的 subject status 一致）

### 3.4 不改动

- `GET /student/placement/{paper_id}`：直链仍可打开（方案 1）；工作台不提供入口
- 档案作废 / 路线图末科 enqueue 等既有链路

---

## 4. 前端行为

### 4.1 工作台 `Workspace.tsx`

- `useQuery` 拉取 `GET /student/placement`，按 `subject_code` 索引
- 当前科目 `status === "submitted"`：按钮文案「已完成」，`disabled`，不调用 `startPlacement`
- 否则：保持「开始摸底测评」；条件仍含档案未完成、组卷中等现有禁用
- 摸底交卷成功（或从 placement 页返回）后 `invalidateQueries` placement 列表，使按钮即时变灰
- 若 `start` 返回 400：展示 `detail`，不 `navigate`

### 4.2 试卷答题页

- 本期不强制只读 UI；二次提交依赖后端 400 即可

---

## 5. 测试要点

- 已交卷科目再 `start`（带 `subject_code`）→ 400 + 中文 detail
- 全部科目已交且无 `subject_code` 再 `start` → 400
- `GET /student/placement`：已交试卷项 `status == "submitted"`
- 工作台：已交科目显示「已完成」且 disabled（组件测试）
- 回归：未交科目仍可 start；submit 成功仍写 mastery / 末科 enqueue roadmap

---

## 6. 实现要点（文件级）

| 文件 | 变更 |
|------|------|
| `backend/app/services/placement.py` | start 已交拒绝；list status 用 `_paper_status_label`；submit 中文 detail |
| `backend/tests/test_placement_flow.py`（或等价） | start/list 一科一遍用例 |
| `frontend/src/pages/student/Workspace.tsx` | 拉取 placement 列表 + 已完成按钮 |
| `frontend/tests/WorkspaceTasks.test.tsx` 或新建测 | 已完成态断言 |

---

## 7. OUT OF SCOPE

- 学生 / 老师主动「重开摸底」运营入口
- 答题页只读结果页、工作台「查看结果」
- 新建 attempt 表或状态机实体
- 改全年路线图触达条件

---

## 8. 与现有 spec 关系

| 模块 | 关系 |
|------|------|
| P3 / `2026-05-26-ai-teacher-design.md` | 摸底仍为入学定级入口；本期明确不可学生重复交 |
| `2026-06-02-student-exam-profile-master-plan-design.md` | 结构变更作废摸底例外不变 |
| `2026-06-25-annual-study-roadmap-design.md` | 末科交卷触发路线图不变；不因「再考」重复 enqueue（因禁止再考） |
