# 报考档案轻量修订与任务权重 — 产品设计规格

**日期：** 2026-06-25  
**状态：** 已实现  
**依赖：** [学生报考档案与总计划个性化](2026-06-02-student-exam-profile-master-plan-design.md)（已上线）、P12 总计划待确认、`PlanDraftService`、`MasterPlanActivationService`

---

## 1. 背景与目标

报考档案（`StudentExamProfile`）已支持四六级与数学掌握度录入，并在**初始总计划**起草时注入 `PlanDraftService` 上下文。但存在两个缺口：

1. **轻量修订未实现**：老师仅更新四六级/数学自评时，不会修订已有分科计划与总计划（卷种变更才会作废摸底并重走全量流程）。
2. **任务权重未接入档案**：跨科预算削减（`MasterPlannerService`）的科目权重来自 Package 顺序；次日任务生成（`SubjectAgentService`）未根据 CET/数学等级做弱项倾斜。

本期目标：

1. 档案确认后，**仅**四六级/数学字段变更时触发**轻量修订**（不动卷种、科目、摸底卷）。
2. 按档案弱项信号调整**跨科削减权重**与**次日任务生成**（弱项多保护、多排任务）。

**本期不做：** 机构自定义专业、专业课、独立考纲树；自测组卷仍不读取 CET/数学自评（保持上期决策）。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 轻量修订生效 | **混合（C）**：分科阶段/周目标/小预算调整直接生效；`daily_time_budget` 总变动 **>15%** 走 P12 `pending_version` 待学生确认 |
| 任务权重范围 | **两层（C）**：跨科 `trim` 保护弱项 + 次日 `generate_daily_tasks` 弱项多排 |
| 触发入口 | 管理员/员工 `PUT .../exam-profile`（档案已确认后） |
| 卷种/专业/科目变更 | **不**走轻量修订，沿用现有全量逻辑（作废摸底 + `create_initial_plans`） |

---

## 3. 触发与分流

### 3.1 变更检测

在 `admin_exam_profile` / `staff_exam_profile` 的 `PUT` 处理中，`db.flush()` 后比较 **变更前** 与 **变更后** 的 `EffectiveExamProfile`：

| 变更类型 | 字段 | 行为 |
|----------|------|------|
| 结构变更 | `major_*`、`english_track`、`math_track`、`subject_codes` | 现有：`invalidate_placement_on_track_change` + 同步科目；**不**在本期新增全量 replan（若尚未做可保持现状） |
| 基础水平变更 | `cet_status`、`cet_score`、`math_mastery_level` | **轻量修订**（见 §4） |
| 档案未完成 | `profile_completed_at is null` | 仅保存档案，不修订计划 |

**轻量修订前置条件：** `profile_completed_at is not None` 且存在 `MasterPlan.current_version_id`。

若无总计划/分科计划 → fallback `PlanningService.create_initial_plans`（与 confirm 后行为一致）。

### 3.2 审计

轻量修订成功后记录 `AuditLog`：

- `action`: `student.exam_profile.light_revise`
- `before` / `after`: `cet_status`、`cet_score`、`math_mastery_level`

---

## 4. 轻量修订逻辑

### 4.1 服务边界

新增 `PlanningService.light_revise_from_profile(db, student_user_id)`（或同级方法），内部：

1. `PlanDraftService` — 复用 `_build_context` + 规则层 `_draft_with_rules` 中 **仅 english/math** 的 phases 生成逻辑（抽取为可复用方法，避免复制 if/else）。
2. `MasterPlanActivationService.propose_version` — 提交新的 `MasterPlanVersion`（周目标 + 日预算），由 P12 阈值决定直接激活或 pending。
3. 分科计划 — 仅为 `english` / `math`（且在 `subject_codes` 内）创建新 `SubjectPlanVersion`；`politics` 与其他科目 **版本号不变**。

### 4.2 分科计划修订

对每个受影响科目（`english`、`math`）：

- 读取当前 `SubjectPlan` / `SubjectPlanVersion`
- 用规则层生成新 `phases_json`（与初始计划相同的 CET/数学 notes 规则）
- `version = current.version + 1`，`source = "ai"`，`plan.current_version_id` 指向新版本

**不修改：** 政治分科计划、已锁定的其他字段。

### 4.3 总计划修订

从 `PlanDraftService` 规则层获取：

- `weekly_goals_json` — 可随 CET/数学调整描述（如「强化英语词汇语法」）
- `daily_time_budget_json` — 可选规则调整，示例：

| 条件 | 建议调整 |
|------|----------|
| `cet_status = not_taken` | 未来 7 日预算 +10 分钟/天（总量计入 change_ratio） |
| `math_mastery_level = zero` | 未来 7 日预算 +10 分钟/天 |
| `cet6` + `math strong` | 预算不变或 -5 分钟/天（可选，规则层实现时取保守默认：不变） |

调用 `MasterPlanActivationService.propose_version`：

- `change_ratio = budget_change_ratio(old, new)`
- `change_ratio <= 0.15`（`AUTO_ACTIVATE_THRESHOLD`）→ `current_version_id` 更新，无 pending
- `change_ratio > 0.15` → `pending_version_id` 设置，学生端 `requires_confirmation=true`（现有 P12 UI）

**周目标-only 变更**（预算不变）：直接 `propose_version`，`change_ratio=0`，始终直接激活。

### 4.4 与摸底/自测的关系

- **不**作废摸底卷、**不** enqueue 新 `paper_gen_jobs`
- **不**改变 `english_track` / `math_track`
- 自测组卷 prompt **仍不**注入 CET/数学自评

---

## 5. 任务权重（`ExamProfileWeightService`）

### 5.1 职责

`ExamProfileWeightService.subject_weights(db, student_user_id) -> dict[str, int]`

返回各开通科目的整数权重：**数值越大，跨科削减时越晚被取消**。

### 5.2 权重表（规则层，可配置常量）

**英语**（科目 `english` 开通时）：

| `cet_status` | 权重 |
|--------------|------|
| `not_taken` | 4 |
| `null` / 未填 | 3 |
| `cet4` | 3 |
| `cet6` | 2 |

**数学**（科目 `math` 开通且 `math_track != none`）：

| `math_mastery_level` | 权重 |
|----------------------|------|
| `zero` | 4 |
| `basic` | 3 |
| `null` / 未填 | 3 |
| `good` | 2 |
| `strong` | 1 |

**政治**（`politics`）：基准权重 **2**（无档案信号时不变）。

### 5.3 与 Package 顺序合并

`MasterPlannerService.subject_weights_for_student` 改为：

1. 读取 `ExamProfileWeightService.subject_weights` 作为基础
2. 若学生有 Package，可用 Package 内科目顺序作 **同权重内的 tie-break**（或：`final_weight = exam_weight * 10 + package_rank`，保证档案信号优先于套餐顺序）

**消费者：** `trim_tasks_by_budget` 的 `_cancel_sort_key`（权重低先砍）。

### 5.4 次日任务生成倾斜

在 `SubjectAgentService.apply_report_recommendations` 末尾（report 建议落地后）：

| 条件 | 动作 |
|------|------|
| `english` + `cet_status in (not_taken, null)` | 幂等追加 1 条 `study` 任务，标题如「英语基础巩固」，`est_minutes=30`，`payload_json.source=exam_profile_boost` |
| `math` + `math_mastery_level in (zero, basic, null)` | 同上，「数学基础巩固」 |
| `cet6` / `math strong` | 不追加 |

幂等键：`_task_ref_id(..., rec_type="study", knowledge_node_id="exam_profile_boost")` 或专用 ref 命名空间，避免重复创建。

**不修改** `ReportService` 与自测组卷逻辑。

---

## 6. 权限与界面

| 操作 | 管理员 | 员工 | 学生 |
|------|--------|------|------|
| 修改 CET/数学触发轻量修订 | ✅ | ✅（负责学员） | ❌ |
| 查看修订后总计划 | ✅ | ✅ | ✅（含 pending 确认） |

**前端：** 本期无新页面。学生总计划页已有 P12 待确认流程；档案 PUT 成功后老师端可无感（可选 toast「计划已根据基础水平更新」— 非必须）。

---

## 7. 异常与边界

| 场景 | 处理 |
|------|------|
| 档案未完成 | 不轻量修订 |
| 无 MasterPlan | fallback `create_initial_plans` |
| 仅改 `cet_score` 数值、status 不变 | 仍触发轻量修订（分数可能影响规则文案） |
| 同时改 track + CET | 走结构变更路径，**不**轻量修订 |
| `math_track=none` | 数学权重与数学 boost 任务均跳过 |
| LLM planning policy 非 mock | 轻量修订 **仅用规则层**（与初始计划 mock 兜底一致），避免异步 LLM 阻塞 PUT |

---

## 8. 测试要点

### 8.1 轻量修订

- PUT 仅 `cet_status`: `cet4` → `not_taken` → `english` `SubjectPlanVersion` version+1，`politics` version 不变
- `daily_time_budget` 总变动 10% → `current_version` 更新，`pending_version_id` 为空
- 总变动 25% → `pending_version_id` 非空，`requires_confirmation=true`
- 档案未完成 PUT → 无新 `SubjectPlanVersion`
- PUT 改 `english_track` → 不调用 `light_revise_from_profile`（走现有 invalidate）

### 8.2 任务权重

- `cet_status=not_taken` → `subject_weights["english"]` > `subject_weights["politics"]`
- `math_mastery_level=zero` → math 权重高于 strong
- `trim_tasks_by_budget` 超预算时，低权重科目任务先被取消
- `apply_report_recommendations` 对 CET 未过学生次日多 1 条 study；重复调用不重复创建

### 8.3 回归

- 自测 `paper_gen` prompt 仍不含 CET/数学字段
- 档案 confirm 全量流程不受影响

---

## 9. 实现要点（文件级）

| 文件 | 变更 |
|------|------|
| `backend/app/services/exam_profile_weights.py` | **新建** `ExamProfileWeightService` |
| `backend/app/services/planning.py` | `light_revise_from_profile` |
| `backend/app/services/plan_draft.py` | 抽取 `phases_for_subject(code, context)` 供初始/轻量共用 |
| `backend/app/services/master_planner.py` | `subject_weights_for_student` 合并档案权重 |
| `backend/app/services/subject_agent.py` | 弱项 boost 任务 |
| `backend/app/routers/admin_exam_profile.py` | PUT 后分流调用轻量修订 |
| `backend/app/routers/staff_exam_profile.py` | 同上 |
| `backend/tests/test_exam_profile_light_revise.py` | **新建** |
| `backend/tests/test_exam_profile_task_weights.py` | **新建** |

---

## 10. 架构示意

```text
PUT exam-profile (仅 CET/数学变)
        ↓
ExamProfileService 保存
        ↓
PlanningService.light_revise_from_profile
   ├─ PlanDraftService → english/math SubjectPlanVersion+1
   └─ MasterPlanActivationService.propose_version
          ├─ Δbudget ≤15% → 直接激活
          └─ Δbudget >15% → pending_version (P12)

每日 PlanReview / trim
        ↓
ExamProfileWeightService.subject_weights
   ├─ trim：弱项科目后砍
   └─ generate_daily_tasks：弱项 +1 study（幂等）
```

---

## 11. 与上期 spec 关系

| 上期 §5.4 / §5.5 | 本期 |
|------------------|------|
| 轻量修订 | §4 实现 |
| 每日任务按 CET/数学调权重 | §5 实现 |
| 下期：机构专业/专业课/考纲树 | 仍 OUT OF SCOPE |
