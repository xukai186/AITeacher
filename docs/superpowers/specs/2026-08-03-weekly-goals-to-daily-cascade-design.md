# 周目标结构化 → 日任务级联 — 产品设计规格

**日期：** 2026-08-03  
**状态：** 已实现  
**依赖：** 年度路线图当月切片（`2026-06-25-annual-study-roadmap-design.md`、叶子调度 `2026-07-22`）、`MasterPlanVersion.weekly_goals_json`、`PlanDraftService`、`SubjectAgentService` / PlanReview、`ReportService` 薄弱点

---

## 1. 背景与目标

当前链路为：

- 路线图当月叶子 → 写入 7 天战术草稿时**多半变成文案**（阶段 notes / 周目标 title），**不落结构化知识点 ID**；
- 日任务主要由 `ReportService` 错题/自测推荐生成，**不读**周目标；
- 工作台「今日计划」查**今天**，而任务默认常写**明天**，易出现「暂无今日任务」。

目标：在总计划版本上把**周任务结构化**（从总计划/当月路线图拆出知识点），日任务**优先按本周知识点推进**，有薄弱点时**再插一条复习**。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 周任务载体 | **方案 A**：扩展 `MasterPlanVersion.weekly_goals_json`，不新建 WeeklyPlan 表 |
| 周知识点来源 | **仅**年度路线图当月切片叶子 `syllabus_node_ids`；薄弱点**不**写入周清单 |
| 日任务分配 | **优先**本周知识点推进；有活跃薄弱点时**最多再插 1 条** `review_wrong` |
| 实现路径 | **方案 1**：扩展 JSON schema + 改 `PlanDraftService` 月切片写入 + 改 `SubjectAgent` 日生成 |
| 今日日期 | 日任务默认目标日改为**今天**（或「今天无 pending 任务则补生成今天」）；与级联一并修 |

---

## 3. 周目标 JSON Schema

### 3.1 新结构（每条）

```json
{
  "title": "本周：英语 — 阅读细节题",
  "description": "推进当月路线图叶子节点",
  "subject_code": "english",
  "syllabus_node_ids": ["<uuid>", "<uuid>"],
  "kind": "focus"
}
```

| 字段 | 要求 |
|------|------|
| `title` / `description` | 保留；展示用 |
| `subject_code` | focus 目标必填 |
| `syllabus_node_ids` | 叶子 UUID 列表；可为空仅当 `kind=support` |
| `kind` | `focus`：来自当月切片；`support`：可选辅助文案目标（可无 ID） |

### 3.2 兼容

- 仅有 `title`/`description` 的旧条目：视为无周知识点；日生成对该科**回退**现有 `ReportService` 推荐。
- 列表 API 仍返回 `weekly_goals_json` 原样；前端可逐步展示科目与节点名（解析 syllabus）。

### 3.3 SubjectPlan

- `phases_json` 可继续在 notes 中展示叶子名称（现状可保留）。
- **日任务权威来源**为 Master 周目标上的 `syllabus_node_ids`，不以 phases notes 解析名为准。

---

## 4. 起草与刷新（总计划拆周）

### 4.1 写入时机

与现有战术刷新一致：

- 路线图确认后刷新战术；
- 月初 `refresh_tactical_from_roadmap`；
- 档案轻改等走 `PlanDraftService` / `light_revise` 的路径。

核心改动：`PlanDraftService._apply_month_slice`（及保证初始 draft 经同一路径）。

### 4.2 算法

对当月切片中每个启用科目 `S`：

1. 取 `subjects[S].syllabus_node_ids`（已是叶子；若空则跳过该科 focus 条）。
2. 写入 **一条** `kind=focus` 周目标：`subject_code=S`，`syllabus_node_ids=该列表`，`title`/`description` 结合 `focus` 文案与解析到的节点名（截断合理长度）。
3. 可选保留少量无 ID 的 `support` 目标（如「保持节奏」），不阻塞日生成。
4. `daily_time_budget_json` 仍按 `weekly_hours_hint // 7`（或现有逻辑）。

**不做：** 把错题薄弱节点并入 `syllabus_node_ids`。

---

## 5. 日任务生成

### 5.1 入口

仍经 PlanReview → `generate_daily_tasks` → `SubjectAgentService.apply_report_recommendations`（可重命名/拆私有方法，对外工具名可不变）。

### 5.2 默认目标日

- `target_date` 缺省为 **`date.today()`**（改掉「默认明天」）。
- 每日 cron / 手动「生成任务」文案与 API 对齐为「今日/指定日」；若产品仍需「预生成明日」，用显式 `target_date` 参数，不作为默认。

### 5.3 单科算法（目标日 D，科目 S）

1. 读当前生效 `MasterPlanVersion.weekly_goals_json`，筛 `subject_code==S` 且 `syllabus_node_ids` 非空的 `focus`（及等价）目标。
2. **若存在 focus 节点：**
   - 生成 **1～2 条**推进类 `DailyTask`（建议 `type=study`，`payload.source=weekly_goal`，含 `syllabus_node_id`、可选 `weekly_goal_title`）。
   - 节点选择：对本周 ID 列表做稳定轮询（按 D 的 weekday 或已有同周已完成/已排任务避免总盯同一节点）。
   - 标题体现知识点名称（查 `SyllabusNode`）。
   - 若该科存在活跃薄弱点（`ReportService` / 错题聚合）：**最多再插入 1 条** `type=review_wrong`，`payload.source=report_weak`；优先选与本周 `syllabus_node_ids` 交集中的薄弱点，否则取 wrong_count 最高者。
   - 原无条件 `self_test` / `check_result`：可排在推进之后；总数与分钟仍受当日预算与 `trim_tasks_by_budget` 约束。若预算紧张，优先保留推进 + 至多一条薄弱复习。
3. **若不存在 focus 节点：** 回退现有 `_recommendations` → 物化逻辑（兼容旧周目标、无路线图切片）。
4. 幂等：同日同科同 `type`+`ref_id`（ref 含 node id 或 recommendation key）不重复插入。

### 5.4 明确不改（本期）

- 自测**组卷**仍可不读取日任务 payload（与既有脱钩可保留）。
- 不新建 WeeklyPlan 表；不因练习掌握自动改写周目标。

---

## 6. 前端（最小）

- 工作台今日任务：有 `payload.syllabus_node_id` / `source` 时可显示「本周推进」或「薄弱复习」轻量标记（可选但建议）。
- 总计划页：展示周目标时若有 `subject_code` / 节点，优先展示结构化信息（可选；后端先行亦可）。
- 学情「生成任务」：默认目标日与后端一致（今天）；文案避免写死「明日」若行为已变。

---

## 7. 测试

### 7.1 后端

- `_apply_month_slice`（或等价）产出含 `subject_code` + 非空 `syllabus_node_ids` 的 focus 周目标。
- 有 focus 时：`apply_report_recommendations`（或新方法）为今天生成带 `weekly_goal` 的 study；有薄弱点时同科至多一条 `review_wrong`。
- 无 focus 时：行为与旧报告推荐一致。
- 默认 `target_date` 为今天。
- 预算 trim 后不违反「优先推进」的相对优先级（断言推进类尽量保留）。

### 7.2 前端（若有 UI 标记）

- 今日列表渲染推进/复习标记（有则测）。

---

## 8. 验收标准

1. 当月切片含叶子时，生效总计划周目标含每科 focus + `syllabus_node_ids`。  
2. 触发日任务生成后，今日计划出现基于本周节点的推进任务。  
3. 同科有活跃薄弱点时，至多一条薄弱复习任务。  
4. 旧周目标无 ID 时不报错，仍能生成报告型任务。  
5. 默认不再把新任务写到「明天」而导致今日长期为空（在生成链路已跑的前提下）。

---

## 9. 与既有规格关系

- 补充而非替代 `2026-06-25-annual-study-roadmap-design.md`：战略层仍是路线图；本规格打通 **战术周目标结构化 → 日任务**。  
- 实现后本文件标「已实现」；路线图规格可加一句交叉引用。
