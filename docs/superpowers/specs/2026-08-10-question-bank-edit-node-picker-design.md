# 题库编辑与知识点选择器 — 产品设计规格

**日期：** 2026-08-10  
**状态：** 待实现  
**依赖：** 全局题库 P1–P3（`QuestionBankItem`、admin/staff 题库页、审核流）、大纲 `syllabus_nodes`  
**关联：** `docs/superpowers/specs/2026-08-04-global-question-bank-design.md`

---

## 1. 背景与目标

题库已支持新建、列表分页、详情查看、审核/禁用，以及公式渲染与知识点名称展示。缺口：

1. **不能编辑**已入库题目（规格 CRUD 未完成）；
2. **知识点只能看不能选**：新建确认页与详情仅展示名称/ID，人工无法改挂接节点。

目标：在管理端补齐「编辑」与「知识点选择器」，并与现有审核状态机一致。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 可编辑状态 | `pending_review` / `rejected` / `disabled`；`active` 须先禁用 |
| 编辑后状态 | `rejected` / `disabled` → `pending_review`；`pending_review` 保持不变 |
| 可改字段 | 题干、题型、选项、答案、科目、知识点、难度、解析；**不含**归属 `scope` |
| 交互形态 | 详情抽屉内「编辑」为主；列表也可放同权限的「编辑」入口 |
| 知识点 UI | 按科目过滤的可搜索叶子节点下拉（文案 `parent / name`） |
| 历史卷面 | 已生成自测快照不随题库编辑改变 |

---

## 3. 权限与状态机

### 3.1 可变范围

沿用现有 `_get_mutable_item`：

| 角色 | 可编辑范围 |
|------|------------|
| `org_staff` | 本机构 `scope=org` 题 |
| `org_admin` | 本机构题 + 平台 `global` 题 |

### 3.2 状态规则

- **允许 PATCH**：`pending_review` / `rejected` / `disabled`
- **禁止 PATCH**：`active` → 明确 4xx（文案示例：「请先禁用后再编辑」）
- **编辑后**：
  - `pending_review` → 仍为 `pending_review`
  - `rejected` / `disabled` → `pending_review`，并清空 `reviewed_by` / `reviewed_at`
- UI：`active` 不展示「编辑」，仅「查看 / 禁用」

### 3.3 快照隔离

`SelfTestQuestion` 为卷面快照；题库 `PATCH` **不得**回写已生成试卷题目。

---

## 4. API

### 4.1 更新题目

`PATCH /org/question-bank/{id}`

**请求体**（字段均可选，至少提供一项）：

| 字段 | 说明 |
|------|------|
| `stem` | 题干 |
| `q_type` | 题型 |
| `choices` | 选项列表（客观题） |
| `answer_key` | 答案 |
| `subject_code` | 科目 |
| `knowledge_node_id` | 知识点 UUID，可显式 `null` 清空 |
| `difficulty` | 1–5 |
| `analysis_text` | 解析，可 `null` |

**服务端步骤：**

1. 鉴权 + 可变范围校验  
2. 状态校验（非 `active`）  
3. 科目与知识点一致性：
   - 生效科目 = 请求中的 `subject_code`（若有）否则库中现有科目  
   - 若请求显式带 `knowledge_node_id`：节点须存在、**须为叶子**、且属于生效科目；`null` 表示清空  
   - 若只改了 `subject_code` 未带 `knowledge_node_id`，而库中旧节点不属于新科目 → **服务端自动清空** `knowledge_node_id`  
4. 客观题校验选项/答案格式（与 create 一致）  
5. 应用字段；按 §3.2 调整状态与审核字段  
6. 返回 `QuestionBankItemOut`（含 `knowledge_node_name`）

> 路由注意：`GET /knowledge-nodes` 须注册在 `/{item_id}/...` 之前，避免被路径参数吞掉。

### 4.2 知识点候选列表

`GET /org/question-bank/knowledge-nodes?subject_code={code}`

- Auth：`org_admin` / `org_staff`  
- 返回该科目**叶子**节点：`[{ id, name, parent_name }]`  
- 展示约定：有父级 → `{parent_name} / {name}`；无父级 → `{name}`

---

## 5. 前端

### 5.1 入口

- 详情抽屉：可编辑状态显示「编辑」  
- 列表操作列：同样条件显示「编辑」  
- `active`：不显示「编辑」

### 5.2 编辑弹窗

- 布局对齐新建确认页：题干/题型/选项/答案 + 科目/知识点/难度/解析  
- 题干、选项、答案保留 `MathText` 预览  
- 知识点：可搜索下拉，数据来自 §4.2；可清空为「未标注」  
- 换科目：若当前选中节点不属于新科目，自动清空并提示重选  
- 保存 → `PATCH`；成功后关弹窗、刷新列表（状态回待审时列表应立即反映）

### 5.3 新建确认页

- 将只读知识点改为同一选择器；模型建议值为默认选中，人工可改

### 5.4 错误展示

- `active` 误操作：接口/前端提示先禁用  
- 校验失败（选项格式、知识点科目不匹配等）：表单内展示错误信息

---

## 6. 组件边界（建议）

| 单元 | 职责 |
|------|------|
| `QuestionBankService.update` | 状态/权限/字段校验与落库 |
| `GET knowledge-nodes` router | 科目叶子节点查询 |
| `KnowledgeNodeSelect`（前端） | 按科目拉选项、搜索、清空；新建确认 + 编辑共用 |
| 编辑弹窗 | 表单状态、预览、调用 PATCH |

---

## 7. 测试要点

### 后端

- `pending_review` PATCH 成功且状态不变  
- `rejected` / `disabled` PATCH 后 → `pending_review`，审核字段清空  
- `active` PATCH → 4xx  
- staff 不能改 global；admin 可以  
- 知识点与科目不匹配 → 422  
- `GET knowledge-nodes` 仅返回对应科目叶子节点

### 前端

- 可编辑题显示「编辑」；`active` 不显示  
- 保存后列表刷新；下拉按科目过滤  
- 新建确认页可用选择器修改知识点

---

## 8. 非目标（本规格不做）

- 改归属 `scope`（org ↔ global）  
- `disabled` → 直接 `active` 的「重新启用」捷径（统一走待审再通过）  
- 大纲树形多级展开选择器（首期叶子下拉即可）  
- 题目删除（硬删）；向量去重、多题 OCR 切分

---

## 9. 验收标准

1. 老师/管理员可对非 `active` 题编辑题面与属性并保存。  
2. `active` 须先禁用才能编辑；编辑禁用/驳回题后进入待审。  
3. 新建确认与编辑均可按科目选择/清空知识点，展示为可读名称。  
4. 已有自测卷面内容不因题库编辑而改变。
