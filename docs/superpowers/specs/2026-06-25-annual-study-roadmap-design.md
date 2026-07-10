# 全年学习路线图（战略层）— 产品设计规格

**日期：** 2026-06-25  
**状态：** 已实现  
**依赖：** 学生考试档案（已实现）、摸底与掌握度（P3）、考纲树 `SyllabusNode`、7 天总/分科计划（P3/P12）、`planning` 模型策略

---

## 1. 背景与目标

当前 `PlanDraftService` 仅生成 **未来 7 天** 的可执行计划（周目标、日预算、分科单阶段），且考纲树未进入规划 prompt。学生端总计划页主要展示时间预算，分科阶段内容未展示。

机构需要：在**报考专业、考试科目、英语/数学水平、摸底结果、当年考纲**齐备后，由大模型产出**从今天到考试日**的全年整体学习路线图，作为战略层；现有 7 天计划与每日任务作为战术层，从路线图按月滚动细化。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 与现有计划关系 | **双层（A）**：全年路线图（战略）+ 7 天计划 / 每日任务（战术） |
| 首次生成时机 | **全部启用科目摸底交卷后（A）**；此前不生成路线图 |
| 时间范围 | **今天 → `StudentProfile.exam_date`（A）**；无 `exam_date` 时用 `exam_year` 推算默认考期 |
| 阶段粒度 | **按月 + 考纲一级章节（A）** |
| 生效方式 | **学生确认后（A）** 才写入 `current_version`；确认前为 `pending` |
| 实现结构 | **独立 `StudyRoadmap` 实体（方案 1）**，不与 `MasterPlanVersion` 混用 |
| 生成方式 | **异步 Job**（避免摸底交卷 HTTP 阻塞）；失败降级规则模板 |
| 确认前战术层 | 保持现有 7 天计划；路线图确认后再按当月切片刷新战术计划 |
| 月块展示 | 含 `weekly_hours_hint`（建议每周学习小时） |

---

## 3. 架构与数据流

```
档案确认 → 各科摸底（逐科更新学情）
    → 最后一科交卷？
        否：仅 mastery / 错题 / 当日任务，不触发生成路线图
        是：enqueue RoadmapGenerationJob
            → LLM / 规则降级 → StudyRoadmapVersion (pending)
            → 学生确认 → current
            → PlanDraftService 读取当月切片 → 7 天 MasterPlan + SubjectPlan
            → 每日任务生成（现有链路）
```

**改造：** `PlacementService.submit` 当前每交一科即 `create_initial_plans`，改为仅在 `PlacementService.all_subjects_completed(student)` 为真时触发路线图 Job；单科交卷仍更新掌握度、错题、PlanReviewJob。

---

## 4. 数据模型

### 4.1 `StudyRoadmap`（每学生一条）

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `student_user_id` | FK → `users.id`，UNIQUE |
| `status` | `draft` / `active` |
| `current_version_id` | FK → `study_roadmap_versions.id`，可空 |
| `pending_version_id` | FK → `study_roadmap_versions.id`，可空 |
| `created_at` | |

### 4.2 `StudyRoadmapVersion`

| 字段 | 说明 |
|------|------|
| `id` | UUID PK |
| `roadmap_id` | FK → `study_roadmaps.id` |
| `version` | 递增 |
| `source` | `ai` / `rule` / `staff` |
| `start_date` | `date`，备考起点（通常 today） |
| `end_date` | `date`，考试日或推算考期 |
| `summary_json` | 可选，`{ "text": "整体策略 2-3 句" }` |
| `months_json` | 见 §4.3 |
| `created_at` | |

### 4.3 `months_json` Schema

```json
{
  "months": [
    {
      "month": "2026-07",
      "label": "基础夯实月",
      "subjects": {
        "english": {
          "focus": "词汇语法 + 阅读入门",
          "syllabus_nodes": ["阅读"],
          "weekly_hours_hint": 12,
          "notes": "结合 CET 基础，长难句拆解"
        },
        "math": {
          "focus": "高数极限与连续",
          "syllabus_nodes": ["高数"],
          "weekly_hours_hint": 15,
          "notes": "数学基础良好，可直接中高难度"
        },
        "politics": {
          "focus": "马原唯物论",
          "syllabus_nodes": ["马原"],
          "weekly_hours_hint": 8,
          "notes": "结合摸底毛中特薄弱点加强"
        }
      },
      "milestones": ["完成英语阅读模考 1 次"]
    }
  ]
}
```

**约束：**

- `syllabus_nodes` 必须为上下文给出的**考纲一级节点 name**（`SyllabusNode` 子节点，parent 为科目根）
- `math_track=none` 时禁止出现 `math` 键
- 月份序列覆盖 `start_date`–`end_date`，允许最后一个月为 partial（`label` 注明冲刺即可）
- 每月每科 1–2 个 `syllabus_nodes`；`weekly_hours_hint` 为建议值，战术层可 ±15% 调整

### 4.4 `RoadmapGenerationJob`（异步）

| 字段 | 说明 |
|------|------|
| `id` | UUID |
| `student_user_id` | |
| `status` | `pending` / `running` / `succeeded` / `failed` |
| `roadmap_version_id` | 成功后写入 pending version |
| `error_message` | |
| `created_at` / `finished_at` | |

与 `paper_gen_jobs` 模式一致：worker 轮询或 cron 执行。

---

## 5. 上下文与 LLM Prompt

### 5.1 `RoadmapDraftService._build_context`

| 来源 | 字段 |
|------|------|
| `EffectiveExamProfile` | `major_name`、`major_category_name`、`english_track`、`math_track`、`subject_codes`、`cet_status`、`cet_score`、`math_mastery_level` |
| `StudentProfile` | `exam_year`、`exam_date` |
| 摸底 | 每科 `PlacementResult.total_score`、`mastery_json` |
| 学情 | `ReportService.overview` → `weak_nodes`（Top 5）、`recommendations` |
| 考纲 | 各科一级节点列表：`syllabus_outline[subject] = [{ "name", "id" }]`，按 `exam_year` + track 过滤 |

**默认考期（无 `exam_date`）：**

- `start_date` = `date.today()`
- `end_date` = `date(exam_year, 12, 20)`；若 today 已晚于该年 7 月，则 `start_date` 仍为 today

### 5.2 Prompt 要点

- 角色：考研机构总规划老师
- 任务：在 `start_date`–`end_date` 内按月分配各科一级考纲模块
- 规则：
  - 薄弱科目（摸底低分 / weak_nodes 多）多月占比更高
  - 英语结合 `cet_status`；数学结合 `math_mastery_level`
  - `syllabus_nodes` 只能从给定列表选取
  - `math_track=none` 严禁输出 math
- 输出：STRICT JSON，结构同 §4.3 + 可选 `summary.text`
- 场景：`ModelPolicy.scene == "planning"`（与 7 天计划共用策略）；`provider=mock` 时走规则降级

### 5.3 规则降级

- 将备考月数 N 均分各科一级考纲节点
- 英语/数学月 `weekly_hours_hint` 按 CET/数学水平 ±20%
- `source=rule`

---

## 6. 战术层消费（7 天计划）

### 6.1 `RoadmapContextService`

```python
current_month_slice(db, student_user_id, today: date) -> MonthSlice | None
```

- 读取 `StudyRoadmap.current_version_id` 的 `months_json`
- 匹配 `month` 字段 == `today.strftime("%Y-%m")`
- 无 active 路线图时返回 `None`（战术层沿用现有逻辑）

### 6.2 `PlanDraftService` 扩展

生成 7 天计划（初始 / 复审 / 月初刷新）时：

- 若存在 `MonthSlice`：prompt / 规则注入当月 `label`、各科 `focus`、`syllabus_nodes`、`weekly_hours_hint`
- `daily_time_budget`：`weekly_hours_hint` 按 7 天均分（分钟），仍受 60–360 clamp
- `subject_phases_json`：`notes` 引用当月 focus + syllabus_nodes
- 若无路线图：行为与现网一致

### 6.3 刷新节奏

- 路线图 **confirm 后**：立即用当月切片生成新一版 7 天计划（可能触发 P12 pending，若预算变动 >15%）
- **每月 1 日**（机构时区，cron）：对有 active 路线图的学生 enqueue 战术层刷新 Job
- 现有 `PlanReviewJob` / 轻量修订：**不**自动重生成全年路线图

---

## 7. API 与权限

### 7.1 学生

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/student/roadmap` | `active_version`、`pending_version`、`generation_job` 状态 |
| POST | `/student/roadmap/confirm` | pending → current；触发战术层刷新 |
| POST | `/student/roadmap/reject` | 丢弃 pending |

### 7.2 机构（只读 + 重试）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/org/students/{id}/roadmap` | 同学生视图 |
| POST | `/org/students/{id}/roadmap/regenerate` | 老师手动重试生成（需负责关系） |

学生 **不可** 直接编辑路线图 JSON；调整通过对话 Agent 或老师干预（二期）。

---

## 8. 界面

### 8.1 学生「总计划」页

两 Tab：

1. **全年路线图** — 月时间轴；每月展示各科 `focus`、`syllabus_nodes`、`weekly_hours_hint`、`milestones`；pending 时展示新旧对比 + 确认/拒绝
2. **本周执行** — 周目标、日预算、**分科本周阶段**（修复当前仅显示时间的问题）

### 8.2 工作台横幅

路线图 pending 时：`全年学习计划已生成，请前往总计划页确认`

路线图 Job `running` 时：`正在生成全年学习计划…`

---

## 9. 触发与修订

| 场景 | 行为 |
|------|------|
| 最后一科摸底交卷 | enqueue `RoadmapGenerationJob`（若尚无 pending） |
| 学生 confirm | pending → current；`PlanDraftService` 刷新战术层 |
| 学生 reject | 清除 pending；保留旧 current（若有） |
| 档案结构变更（专业/卷种/科目） | 作废 pending/current 路线图 + 现有 invalidate 摸底逻辑 |
| CET/数学轻量修订 | **仅战术层**（已实现）；路线图本期不自动重算 |
| 老师 regenerate | 新 pending version，需学生再次 confirm |
| 重复交卷同一科 | 不重复 enqueue（dedup by student + status pending/running） |

---

## 10. 异常与边界

| 场景 | 处理 |
|------|------|
| LLM 超时/解析失败 | 规则降级；Job `failed` 可老师重试 |
| 考纲无一级节点 | 该科 `syllabus_nodes` 用科目名占位；审计日志 |
| 备考不足 1 个月 | 仍生成 1 个月块，`label` 为冲刺 |
| 备考 > 18 个月 | 合并为季度级 label，但 `month` 仍按月；或 cap 18 个月（实现取 cap 18） |
| 无 planning 策略 / mock | 规则降级 |

---

## 11. 实现要点（文件级）

| 文件 | 变更 |
|------|------|
| `backend/app/models/study_roadmap.py` | **新建** `StudyRoadmap`、`StudyRoadmapVersion` |
| `backend/app/models/roadmap_generation_job.py` | **新建** Job 模型 |
| `backend/alembic/versions/...` | migration |
| `backend/app/services/roadmap_draft.py` | **新建** context + LLM + 规则降级 |
| `backend/app/services/roadmap_context.py` | **新建** `current_month_slice` |
| `backend/app/services/roadmap_activation.py` | **新建** confirm/reject（仿 P12） |
| `backend/app/services/placement.py` | 末科交卷检测 + enqueue job；移除逐科 `create_initial_plans` |
| `backend/app/services/plan_draft.py` | 注入 `MonthSlice` |
| `backend/app/jobs/run_roadmap_generation_jobs.py` | **新建** worker |
| `backend/app/routers/student_roadmap.py` | **新建** |
| `frontend/src/pages/student/MasterPlan.tsx` | Tab + 路线图时间轴 + 分科阶段 |
| `frontend/src/api/roadmap.ts` | **新建** |
| `backend/tests/test_roadmap_*.py` | **新建** |

---

## 12. 测试要点

- 三科摸底：前两科交卷不生成路线图；第三科交卷 enqueue 一次
- LLM mock JSON 解析；`syllabus_nodes` 校验拒绝非法节点
- confirm / reject 状态机
- confirm 后 `PlanDraftService` 日预算与当月 `weekly_hours_hint` 一致
- `math_track=none` 路线图与 prompt 均无 math
- 学生页展示路线图 + 分科阶段，不再仅显示时间

---

## 13. 与现有 spec 关系

| 模块 | 关系 |
|------|------|
| `2026-06-02-student-exam-profile-master-plan-design.md` | 档案仍是路线图输入；档案 confirm 后**不再**立即生成可执行总计划，改为摸底后生成路线图 |
| `2026-06-25-exam-profile-light-revise-and-task-weights-design.md` | 轻量修订仅战术层；路线图 OUT OF SCOPE |
| P12 待确认 | 战术层预算 >15% 仍 pending；路线图有独立 pending |

---

## 14. OUT OF SCOPE（本期）

- 考纲叶子节点级排期
- 专业课（自命题）路线图
- 机构自定义考纲树
- 路线图每月自动 LLM 全量重算
- 学生直接编辑路线图
