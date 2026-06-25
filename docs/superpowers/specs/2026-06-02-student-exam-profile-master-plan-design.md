# 学生报考档案与总计划个性化 — 产品设计规格

**日期：** 2026-06-02  
**状态：** 已实现  
**依赖：** P3 摸底与计划、P12 总计划待确认、现有 `StudentProfile` / `Package` / `PastExamPaperTemplate`

---

## 1. 背景与目标

当前系统仅在 `StudentProfile` 中记录 `exam_year`，科目通过 `Package` 或 `StudentSubject` 以 `english` / `math` / `politics` 粗粒度开通。总计划生成主要参考考试年份、科目列表与掌握度快照，**无法**根据学生报考专业、英一/英二、数一/数二/不考数学、四六级与数学基础水平做个性化。

机构老师在录入学生时需要补充上述报考信息；系统应据此：

1. 生成**初始总计划**（档案确认后立即）
2. 选择正确的**摸底卷种**与考纲范围
3. 在摸底完成后**自动修订**总计划

**本期不做：** 专业课（自命题）目录与计划；机构自定义专业库（使用平台种子目录）。

---

## 2. 已确认的产品决策


| 维度     | 决策                                             |
| ------ | ---------------------------------------------- |
| 专业选择   | **大类 → 具体专业 → 系统推荐科目组合**，老师可覆盖                 |
| 四六级    | **选填**：未考 / 四级 / 六级，可填分数                       |
| 数学掌握   | **选填**：零基础 / 一般 / 较好 / 很好                      |
| 卷种影响范围 | **总计划 + 摸底 + 考纲过滤 + 科目开通**；自测组卷**不**参考四六级/数学等级 |
| 总计划时机  | 档案确认后**立即**生成初始计划；摸底提交后**自动修订**                |
| 权限     | **机构管理员**与**负责员工**均可录入/修改；学生只读自己的档案            |
| 实现方案   | **独立 `StudentExamProfile` + 平台专业目录表**（方案 2）    |


---

## 3. 数据模型

### 3.1 专业目录（平台种子）

`**ExamMajorCategory`**


| 字段           | 说明                                                           |
| ------------ | ------------------------------------------------------------ |
| `code`       | 如 `academic_master`、`professional_master`、`management_joint` |
| `name`       | 学硕、专硕、管理类联考                                                  |
| `sort_order` | 展示排序                                                         |


`**ExamMajor`**


| 字段                      | 说明                                        |
| ----------------------- | ----------------------------------------- |
| `code`                  | 如 `cs_academic`                           |
| `category_code`         | FK → `ExamMajorCategory`                  |
| `name`                  | 计算机科学与技术                                  |
| `default_english_track` | `english_1`                               |
| `default_math_track`    | `math_1`                                  |
| `default_subject_codes` | JSON 数组，如 `["english","math","politics"]` |
| `notes`                 | 可选说明                                      |


首期种子：每大类 10～20 个常见专业；后续通过 migration/seed 扩展。

### 3.2 学生考试档案

`**StudentExamProfile`**（`user_id` PK，FK → `users.id`）


| 字段                          | 说明                    |
| --------------------------- | --------------------- |
| `major_category_code`       | 报考大类                  |
| `major_code`                | FK → `ExamMajor.code` |
| `english_track`             | 老师可覆盖专业默认             |
| `math_track`                | 老师可覆盖专业默认             |
| `subject_codes`             | 实际开通科目 JSON 数组        |
| `cet_status`                | `null`                |
| `cet_score`                 | 可选整数                  |
| `math_mastery_level`        | `null`                |
| `profile_completed_at`      | 档案确认时间                |
| `created_at` / `updated_at` | 审计                    |


### 3.3 有效配置解析

`**ExamProfileService.get_effective(student_user_id)`** 返回 `EffectiveExamProfile`：

- 合并 `StudentExamProfile` 与 `ExamMajor` 默认值（老师未填 track 时用专业默认）
- 下游模块**只读**此对象，禁止各自拼字段

### 3.4 与现有模型关系


| 现有模型                    | 关系                                                        |
| ----------------------- | --------------------------------------------------------- |
| `StudentProfile`        | 保留 `exam_year`、`exam_date`、`package_id`；套餐管时长权重，不管卷种      |
| `StudentSubject`        | 由 `subject_codes` 同步 `enabled`；`math_track=none` 时关闭 math |
| `PastExamPaperTemplate` | 增加 `english_track` / `math_track`（政治暂不区分）；摸底按 track 选模板   |
| `SyllabusNode`          | 首期在节点 metadata 标注适用 track；placement 叶子节点按 track 过滤        |


### 3.5 卷种枚举


| 字段              | 取值                         |
| --------------- | -------------------------- |
| `english_track` | `english_1`, `english_2`   |
| `math_track`    | `math_1`, `math_2`, `none` |


---

## 4. 老师录入流程与界面

### 4.1 流程

1. 创建学生账号（现有：姓名、邮箱、密码、考试年份）
2. 进入「完善报考档案」向导（可跳过 → 标记未完成）
3. 确认档案 → 同步科目 → 排队**初始总计划** + **摸底卷生成**（按 `subject_codes`）

管理员从「学员管理」、员工从「我的学员」进入，表单一致。

### 4.2 向导步骤

1. **报考大类** — 下拉选择
2. **具体专业** — 按大类过滤；展示系统推荐的英/数卷种与科目
3. **覆盖推荐**（可折叠）— 老师可改英一/英二、数一/数二/不考、科目勾选；偏离默认时提示
4. **基础水平**（选填）— 四六级状态与分数；数学掌握四级
5. **确认** — 摘要展示后提交

### 4.3 API（概要）


| 方法   | 路径                                  | 权限                          |
| ---- | ----------------------------------- | --------------------------- |
| GET  | `/exam-majors/categories`           | admin, staff, student(只读目录) |
| GET  | `/exam-majors?category=`            | 同上                          |
| GET  | `/admin/students/{id}/exam-profile` | admin                       |
| PUT  | `/admin/students/{id}/exam-profile` | admin                       |
| GET  | `/staff/students/{id}/exam-profile` | staff（需负责关系）                |
| PUT  | `/staff/students/{id}/exam-profile` | staff                       |
| GET  | `/student/exam-profile`             | student（自己的）                |
| POST | `.../exam-profile/confirm`          | admin / staff               |


写入同步 `StudentSubject`，记录 `AuditLog`。

### 4.4 档案修改策略


| 变更类型        | 行为                                     |
| ----------- | -------------------------------------- |
| 专业或卷种变更     | 提示确认；作废未提交摸底卷；按新 track 重生成摸底；重新生成初始总计划 |
| 仅四六级 / 数学等级 | 更新档案；**轻量修订**总计划（不改卷种与科目）              |
| 档案未完成       | 学生不可开始摸底；列表显示 ⚠️ 未完成                   |


---

## 5. 下游消费逻辑

### 5.1 摸底卷（Placement）

- 模板匹配：`(subject_code, english_track|math_track, syllabus_exam_year)`
- `math_track=none`：不生成数学摸底、不开通 math 科目
- 卷种变更：作废未提交 paper，重新 enqueue `paper_gen_jobs`

### 5.2 考纲（Syllabus）

- 首期：`SyllabusNode` metadata 标注适用 track；`leaf_nodes_for_placement` 按 `EffectiveExamProfile` 过滤
- 二期可拆独立考纲树（本期不做了）

### 5.3 自测组卷（Paper Gen）

**不参考** `cet_status`、`cet_score`、`math_mastery_level`。

组卷依据保持不变：

- `ReportService.overview` 学情摘要
- `weak_nodes` 薄弱知识点
- 错题本相关节点

仅在 prompt 中注入 `english_track` / `math_track`（保证题型/难度符合卷种），不注入四六级/数学自评。

### 5.4 总计划（Master Plan）

**初始计划（档案 confirm 后）** — `PlanDraftService` 上下文扩展：

```json
{
  "exam_year": 2027,
  "major_name": "计算机科学与技术",
  "major_category": "学硕",
  "english_track": "english_1",
  "math_track": "math_1",
  "cet_status": "cet4",
  "cet_score": 450,
  "math_mastery_level": "basic",
  "subjects": [...]
}
```

规则层示例（mock/兜底）：

- 英二 + 四级未过 → 英语基础阶段加长  
- `math_track=none` → 总计划不含数学周目标  
- `math_mastery_level=zero` → 数学基础阶段拉长  
- 管理类联考专业 → 默认 `math_track=none`

**摸底后修订** — 在现有 placement → plan 流程上，额外传入 `EffectiveExamProfile`；根据摸底薄弱点调整分科阶段，**不因摸底结果改变卷种**（卷种以档案为准）。

**轻量修订** — 仅四六级/数学等级变更时，修订英语/数学相关阶段，不动科目组合与卷种。

### 5.5 每日任务（Daily Task）

- 仅为 `subject_codes` 内科目生成任务  
- `math_track=none` 不生成数学任务  
- 可选：按 `math_mastery_level` / `cet_status` 调整英语/数学任务权重（弱项多排）

---

## 6. 权限


| 操作         | 机构管理员 | 负责员工     | 学生      |
| ---------- | ----- | -------- | ------- |
| 查看报考档案     | 全部学员  | 仅负责学员    | 仅自己（只读） |
| 创建/修改/确认档案 | ✅     | ✅（仅负责学员） | ❌       |


所有写入记录 `AuditLog`（含卷种变更 before/after）。

---

## 7. 异常与边界


| 场景               | 处理                                       |
| ---------------- | ---------------------------------------- |
| 档案未完成            | 摸底入口不可用；总计划不生成                           |
| 改为不考数学           | 关闭 `StudentSubject.math`；取消进行中数学摸底/任务并提示 |
| 英一 ↔ 英二切换        | 作废未提交摸底；按新模板重生成                          |
| Package 与档案科目不一致 | 以档案 `subject_codes` 为准同步；Package 仅影响时长权重 |
| 种子专业无匹配模板        | 降级同 `subject_code` 通用模板 + 记 warning 日志   |


---

## 8. 测试要点

- `ExamProfileService`：默认值合并与老师覆盖  
- 员工改非负责学员 → 403  
- 档案 confirm → 初始总计划 job 入队  
- 摸底模板按 `english_track` / `math_track` 正确匹配  
- 自测组卷**不读取**四六级/数学自评字段（回归）  
- 卷种变更 → 未提交摸底作废并重生成  
- 档案未完成 → `POST /student/placement/start` 拒绝或返回明确错误

---

## 9. 分期与范围

**本期（P?）**

- 数据模型 + migration + 专业种子  
- 管理员/员工录入 UI + API  
- `ExamProfileService` 统一解析  
- 摸底模板按 track 选择；考纲 metadata 过滤  
- 总计划初始生成与摸底后修订接入档案上下文  
- 学生端只读展示报考摘要

**下期**

- 机构自定义专业目录  
- 专业课（自命题）  
- 独立考纲树按卷种拆分

---

## 10. 架构示意

```text
老师录入 StudentExamProfile
        ↓
ExamProfileService → EffectiveExamProfile
        ↓
   ┌────┴────┬──────────┬────────────┐
   ↓         ↓          ↓            ↓
初始总计划  摸底卷模板  考纲过滤   科目开通
        ↓
   摸底提交 → 修订总计划

自测组卷 ← weak_nodes + 学情（不含四六级/数学自评）
```

