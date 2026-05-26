# 考研机构一对一 AI 老师 — 产品设计规格

**日期：** 2026-05-26  
**状态：** 已评审待实现  
**项目：** AITeacher（绿field）

---

## 1. 背景与目标

为考研培训机构每位学员提供 **一对一 AI 老师**：按机构套餐开通科目（每科一个学科 Agent），由 **总规划 Agent** 统筹跨科学习节奏。系统根据学习进度制定整体与每日计划，整理错题、分析薄弱点、动态调整计划，并按计划不定期生成自测试卷；学生完成后由 AI 批阅（含主观题），错题纳入错题集，形成闭环。

### 1.1 已确认的产品原则

| 维度 | 决策 |
|------|------|
| 教学主导 | **AI 为主**：学生主要与 AI 交互，真人老师极少介入 |
| 进度来源 | **入学摸底测评** + 之后以 **系统内行为** 为主（任务完成、自测、错题、对话） |
| 科目范围 | 机构按 **班型/套餐** 配置科目，学生仅见已开通科目 |
| 题目来源 | **AI 根据知识点与难度现场生成**（机构可抽检） |
| 批阅范围 | **客观题 + 主观题** 均由 AI 评分并给出评语 |
| 终端 | **PC 网页为主**，手机 Web 为辅（响应式） |
| 机构后台 | 学员/套餐/学情看板 + **可改计划、锁卷/换卷** |
| 学生界面 | **工作台**：左侧导航 + 右侧学科/总规划对话 |
| 跨科统筹 | **总规划 Agent** 负责周目标与每日总时长，学科 Agent 在框架内细化 |
| 机构角色 | **管理员** 可见全部学员；**普通员工** 仅可见负责学员 |
| 大模型 | **可配置**（按场景/厂商/模型路由，密钥服务端保管） |
| 架构方案 | **多 Agent 编排 + 工具服务**，分两期交付 |

---

## 2. 整体架构

### 2.1 分层

```
终端层     学生 PC 工作台（主）/ 手机 Web（辅）；机构管理后台（PC）
应用层     学员、套餐科目、计划、任务、试卷、答题、错题、学情
Agent 层   总规划 Agent、学科 Agent × N、编排器（路由/上下文/工具/版本合并）
工具层     摸底、计划 CRUD、组卷、批阅、错题结构化、学情统计、事件流
数据层     用户/套餐/考纲/计划版本/试卷/作答/错题/审计/事件
模型网关   按场景路由可配置厂商与模型
```

**原则：** 对话与推理在 Agent；落库、算分、版本控制在工具服务。机构干预修改 **版本化业务对象**，不以聊天记录为真相源。

### 2.2 Agent 角色

| 角色 | 职责 | 禁止 |
|------|------|------|
| **总规划 Agent** | 跨科周计划、每日总时长分配、负荷冲突协调 | 不讲题、不批阅 |
| **学科 Agent** | 本科阶段/每日计划、答疑、触发组卷、提议调整本科计划 | 不推翻总规划时长上限（除非已授权或总规划更新） |
| **编排器** | 会话路由、上下文组装、工具调用、人工版本合并、事件触发复审 | 不对学生说话 |

学生切换左侧 **当前学科** 时，右侧对话绑定对应学科 Agent；**总计划** 页绑定总规划 Agent。

### 2.3 大模型可配置

**模型网关 + 场景策略：**

| 配置项 | 说明 |
|--------|------|
| 厂商/接入 | OpenAI 兼容 API、国内云、后续私有化 |
| 模型 ID | 各厂商具体模型 |
| 场景路由 | `chat` / `paper_gen` / `grading` / `planning` 等可配不同模型 |
| 参数 | temperature、max_tokens、超时、重试 |
| 降级 | 主模型失败时备用模型或队列重试 |

**默认建议：** 对话与总规划用综合能力强的模型；组卷用结构化输出强的模型；主观批阅用推理与评语强的模型（可独立配置以控成本）。

**权限：** 一期 **全局策略**（平台/机构管理员）；二期 **机构级/套餐级** 覆盖。API Key 仅存服务端，变更写审计日志。

### 2.4 机构后台角色

| 角色 | 可见范围 | 权限 |
|------|----------|------|
| **机构管理员** | 本机构全部学员 | 套餐与科目、员工账号、分配负责关系、全部学情、任意学员改计划/锁卷换卷、模型策略（若开放） |
| **普通员工** | 仅 `StaffStudent` 分配的学员 | 负责学员的学情、改计划、锁卷/换卷；不可改机构级配置、不可见未分配学员 |

负责关系：**多对多**（一名学员可多名员工）。所有列表与干预 API 经数据权限过滤；操作写入 `AuditLog`。

### 2.5 分期范围

| 一期 | 二期 |
|------|------|
| 2～3 门公共课试点、1 种套餐模板 | 任意科目组合、专业课策略 |
| 全局模型场景策略 | 机构/套餐级模型策略 |
| 摸底、总/分科计划、每日任务、AI 组卷与批阅、错题与薄弱点 | 模考卷、班际对比、更强移动端 |
| 管理员/员工权限与干预 | 坏题抽检队列、答卷导出合规、SSO |

---

## 3. 核心数据模型

### 3.1 主体与权限

- `Organization` — 租户
- `User` — `role`: `student` | `org_admin` | `org_staff`
- `StudentProfile` — `exam_year`, `exam_date`, `package_id`
- `StaffStudent` — `staff_user_id`, `student_user_id`（多对多）
- `Package` — `subject_codes[]`, 默认时长权重等
- `StudentSubject` — 学员开通科目

### 3.2 进度与考纲

- `SyllabusNode` — 按科目的知识点树
- `PlacementPaper` / `PlacementResult` — 入学摸底与掌握度映射
- `LearningEvent` — `task_done` | `paper_submitted` | `wrong_added` | …
- `MasterySnapshot` — 由工具服务根据事件与错题/自测汇总，**非 Agent 直接写入**

### 3.3 计划（版本化）

- `MasterPlan` + `MasterPlanVersion` — 跨科周目标、`daily_time_budget[]`；`source`: `ai` | `admin` | `merged`
- `SubjectPlan` + `SubjectPlanVersion` — 单科阶段计划
- `DailyTask` — 当日任务：`type`, `subject_code`, `status`, `est_minutes`, `ref_id`

**计划状态：** `draft` → `active` → [`paused`] → `archived`  
**任务状态：** `pending` → `in_progress` → `completed` | `skipped` | `cancelled`

机构修改产生新 version 并 `active`；AI 提议可能为 `draft` 或带 `auto_activate`（见 §4.4）。

### 3.4 试卷与作答

- `Paper` — `type`: `placement` | `self_test` | `mock`；`status` 见状态机
- `PaperQuestion` — `stem`, `answer_key`, `rubric`（主观评分要点）
- `Submission` / `Answer` — `graded_by`: `ai`

**Paper 状态：**  
`generating` → `ready` → `in_progress` → `submitted` → `grading` → `graded`  
分支：`locked`（机构锁定）、`replaced`（被新卷替代）、`failed`（组卷失败）

### 3.5 错题

- `WrongItem` — `wrong_count`, `question_ref`（指向题目或快照）
- `WrongAnalysis` — `weak_points[]`, `summary`（结构化，供看板与 Agent）
- `WrongItem` 状态：`active` → `mastered`（连续做对 2 次且间隔 ≥1 天）→ `archived`

### 3.6 会话

- `ChatSession` — `agent_type`: `planner` | `subject`；按科目隔离
- `ChatMessage` — 含 `tool_calls`；上下文由编排器注入计划/掌握度/错题摘要，**不扫全库**

---

## 4. 学生工作台

### 4.1 布局

- **顶栏：** 考试倒计时、开通科目、通知
- **左侧：** 今日计划、总计划、错题集、试卷中心、学情报告、科目切换
- **右侧：** 内容区 + 学科/总规划对话（约 40%，可折叠）；做题时可全屏内容区

### 4.2 导航职责

| 导航 | 内容 | 对话绑定 |
|------|------|----------|
| 今日计划 | 当日 `DailyTask` | 当前科或总规划 |
| 总计划 | 周目标、时长、日历 | 总规划 Agent |
| 错题集 | 筛选、重做、掌握标记 | 当前科 Agent |
| 试卷中心 | 进行中/已完成 | 出卷学科 Agent |
| 学情报告 | 掌握度、薄弱点、趋势（只读） | 可选解读 |

---

## 5. Agent 工具与 Pipeline

### 5.1 总规划 Agent 工具

`get_student_overview`, `get_master_plan`, `list_plan_versions`, `propose_master_plan`, `activate_plan_version`, `get_weekly_calendar`, `trigger_plan_review`

### 5.2 学科 Agent 工具

`get_subject_context`, `propose_subject_plan`, `generate_daily_tasks`, `generate_paper`, `get_paper`, `list_papers`, `explain_question`, `add_wrong_item`, `request_plan_adjustment`

学生 **不可** 直接调用工具；仅 Agent 推理后调用。

### 5.3 内部 Pipeline（非对话）

`submit_paper` → `grade_submission`（场景=批阅模型）→ `sync_wrong_from_submission` → `update_mastery` → 可选 `PlanReviewJob`

**组卷：** 模型（场景=组卷）→ JSON schema 校验 → 写入 `PaperQuestion` → `ready`；失败重试后 `failed`。

**批阅：** 客观规则匹配；主观按 `rubric` + 批阅模型；单题失败标记 `grading_failed`，其余照常。

### 5.4 计划生效规则

| 变更类型 | 默认行为 |
|----------|----------|
| 单科每日任务微调 | `auto_activate=true` |
| 跨科总计划时长变化 >15% | `auto_activate=false`，学生总计划页 **待确认** 后生效（机构可配置默认开/关） |
| 机构 admin/staff 修改 | 立即 `active`，标注操作人 |
| 机构锁定字段 | 工具拒绝 AI 覆盖，Agent 向学生说明 |

---

## 6. 计划调整与自测策略

### 6.1 分工

- **总规划：** 各科每周小时、每日总时长上限、跨科冲突削减
- **学科 Agent：** 知识点、题型、错题复习、自测命题范围

### 6.2 计划复审触发（`PlanReviewJob`）

一期实现：

1. 摸底 `PlacementResult` 完成  
2. 自测 `graded`（分数低于阈值或错题数 > N）  
3. 每日定时（生成次日任务前）  
4. 连续 3 天本科完成率 < 60%  

执行顺序：汇总证据 → 学科 Agent（若适用）→ 总规划 Agent 合并负荷。

二期：掌握度骤降、错题积压 80%、距考试 90/60/30 天模板。

### 6.3 每日任务

- 生成：每日 00:05（机构时区）；昨日晚补录可 00:30 增量
- 同学科优先级：未完成自测 > 错题复习 > 新学/刷题 > 预习
- 时长之和 ≤ 总规划当日本科预算

### 6.4 自测（不定期 — 可执行规则）

**硬规则（全部满足才 `generate_paper`）：**

- 距上次本科 `self_test` graded ≥ 5 天（套餐可配 3～14）
- 当日无其他 `in_progress` 试卷
- 无机构 locked 阻止
- 本周本科自测 ≤ 2 次

**软规则（任一满足则建议，由学科 Agent 在复审或每日任务中组卷）：**

- 学完一章/知识点簇（`LearningEvent`）
- 薄弱簇掌握度 < 60% 且已复习 ≥1 次
- 学生对话明确要求自测
- 总规划标记的周检测日

**参数：** 题量 15～30；时长 ≤ 本科当日预算 70%；知识点从薄弱点与近期已学按比例抽取。

### 6.5 错题闭环

批阅 → `WrongItem` + `WrongAnalysis` → `update_mastery` → `PlanReviewJob` → 未来 3 天插入 `review_wrong` → 合适窗口 `generate_paper` 侧重薄弱点 → 多科同时薄弱时总规划协调周时长。

### 6.6 冲突处理

| 冲突 | 处理 |
|------|------|
| 各科任务总和 > 可用时间 | 按套餐科目权重削减低优先级任务 |
| 总规划减预算但已有 ready 自测 | 保留自测，砍刷题/预习 |
| 学科提议超总时长 | 工具拒绝，建议走总计划待确认 |
| `MasterPlan.paused` | 停止自动复审与组卷 |

---

## 7. 机构后台页面

| 页面 | 管理员 | 员工 |
|------|--------|------|
| 学员列表/详情 | 全部 | 仅负责学员 |
| 分配套餐/科目、分配员工 | ✓ | ✗ |
| 学情/计划/试卷/错题 | ✓ | 负责学员 only |
| 改计划、锁卷、换卷 | ✓ | 负责学员 only |
| 员工账号、模型策略 | ✓ | ✗ |

干预：`lock` 阻止 Agent 替换；`replace` 新建 Paper 并更新 `DailyTask`；计划写新 version `source=admin`。

---

## 8. 非功能需求

### 8.1 安全

- 租户 `org_id` 隔离；JWT 认证（一期账号密码）
- 模型密钥仅服务端；对话/答卷/错题访问校验
- 组卷与对话输出内容安全过滤

### 8.2 审计

记录：计划 activate、试卷 lock/replace/generate、学员分配、模型策略变更。学生可见 AI/老师版本来源与时间、老师操作人姓名。

### 8.3 错误与降级

- 模型超时：备用模型 + 队列重试（最多 3 次）
- 组卷 schema 失败：`Paper.failed`，不阻塞其他任务
- 批阅单题失败：`grading_failed`，可单题重批
- `PlanReviewJob` 失败：保留上一 active 计划，死信告警

长任务（组卷、批阅、复审）**异步**；前端轮询或 WebSocket。

### 8.4 性能（一期）

- 单机构百级并发学员；批阅/组卷走队列
- 交卷后 1 分钟内学情近实时更新

### 8.5 可观测性

Trace：`student_id`, `org_id`, `agent_type`, `tool_name`；模型 tokens/latency/scene；业务指标：组卷成功率、计划完成率、错题积压。

### 8.6 测试验收要点

- 员工不可见未分配学员；管理员见全部
- 摸底 → 计划 → 首周任务
- 自测：组卷 → 主客观批阅 → 错题 → 掌握度
- 低分自测触发复审；跨科超时长总规划削减
- 锁卷后 Agent 无法 replace；admin 字段不被 AI 覆盖
- 切换批阅模型对新卷生效

---

## 9. 技术栈建议（非绑定）

| 层 | 建议 |
|----|------|
| 后端 | API 服务 + 任务队列（Redis/Bull 等）+ PostgreSQL |
| 前端 | React 或 Vue，响应式布局 |
| Agent | LangGraph 或自研状态机 + 工具注册表 |
| 模型网关 | OpenAI-compatible 多厂商适配 |

---

## 10. 开放项（二期或实现时细化）

- 机构 SSO、答卷数据导出与删除合规
- 坏题抽检工作流
- 距考试天数冲刺模板自动化
- 机构级/套餐级模型策略 UI
- 员工在后台改分（一期以换卷与对话纠错为主）

---

## 附录：需求决策记录

| # | 问题 | 答案 |
|---|------|------|
| 1 | 真人老师角色 | A — AI 为主 |
| 2 | 进度来源 | D — 摸底 + 系统内行为 |
| 3 | 科目 | C — 套餐配置 |
| 4 | 题库 | B — AI 生成 |
| 5 | 批阅 | B — 含主观题 |
| 6 | 终端 | D — PC 为主 |
| 7 | 机构后台 | C — 看板 + 干预 |
| 8 | 界面 | B — 工作台 + 对话 |
| 9 | 跨科 | B — 总规划 Agent |
| — | 模型 | 可配置 |
| — | 机构角色 | 管理员全员 / 员工负责学员 |
| — | 架构 | 方案一，分两期 |
