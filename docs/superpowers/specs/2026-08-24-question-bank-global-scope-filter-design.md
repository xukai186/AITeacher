# 题库 Global 范围筛选 — 产品设计规格

**日期：** 2026-08-24  
**状态：** 已实现  
**依赖：** 全局题库 P1–P3、OCR 守卫与软删除、并发精确去重、多图 OCR（PR #53–#55）  
**关联：** `docs/superpowers/specs/2026-08-04-global-question-bank-design.md` §5.1

---

## 1. 背景与目标

后端已支持 `scope=global`（仅 `org_admin` 可创建与 mutate）。Admin 题库列表把本机构题与平台公共题混在一起，**无范围筛选、无范围列**，难以专门管理平台公共题。Staff 仅见本机构题（保持不变）。

目标：

1. Admin 可在现有题库页按范围筛选：全部 / 本机构 / 平台公共。
2. 列表展示「范围」列，便于区分题归属。
3. 默认「全部」，与当前混排可见性一致。
4. 本期不做独立平台题库页、不做 org ↔ global 改归属、不开放 Staff 只读 global。

---

## 2. 已确认决策

| 维度 | 决策 |
|------|------|
| 产品形态 | 现有题库页加筛选 + 范围列（非独立页） |
| 默认筛选 | **全部**（本机构 + 平台公共混排） |
| 改归属 org ↔ global | **本期不做** |
| Staff 可见 global | **本期不做**（Staff 仍仅本机构） |
| 后端 | 列表 API 增加可选 `scope` 查询参数（服务端过滤，保证分页正确） |

---

## 3. 权限（不变）

| 角色 | 列表可见性 | 创建 global | Mutate global |
|------|------------|-------------|---------------|
| `org_admin` | 本机构 + global | 是 | 是 |
| `org_staff` | 仅本机构 | 否 | 否 |

新建时 Admin 仍可通过「平台公共」下拉创建 global 题；OCR 工作台沿用现有 `scope` 选择。

---

## 4. API

### 4.1 列表查询

扩展：

```http
GET /org/question-bank?scope=org|global
```

| 参数 | 行为 |
|------|------|
| 不传 `scope` | 与现有一致：admin = 本机构 ∪ global；staff = 本机构 |
| `scope=org` | 仅 `scope=org` 且 `org_id = viewer.org_id` |
| `scope=global` | 仅 `scope=global`；**staff 调用时返回空列表**（不新增 403 文案） |

其他现有参数不变：`status`、`subject_code`、`pending`、`limit`、`offset`。始终排除 `deleted`。

### 4.2 不改动的接口

- 创建 / 更新 / 审核 / 禁用 / 删除：权限与语义不变
- 无「改归属」API

---

## 5. 前端

### 5.1 Admin 题库页

筛选区新增「范围」：

- 选项：全部 / 本机构 / 平台公共
- 默认：**全部**（请求不带 `scope`，或显式不传）
- 切换范围时重置分页（`offset = 0`），与现有科目/状态筛选一致

列表表格新增「范围」列：

- `org` →「本机构」
- `global` →「平台公共」

详情抽屉已展示范围时保持一致文案。

### 5.2 Staff 题库页

- **不展示**范围筛选项
- 范围列：可省略，或固定显示「本机构」（推荐省略，避免无信息噪音）
- 请求行为不变（不传 `scope`）

### 5.3 API client

`QuestionFilters` / `listQuestions` 增加可选 `scope?: "org" | "global"`。

---

## 6. 明确不在本期范围

- 独立「平台题库」页面或路由
- org ↔ global 改归属
- Staff 只读浏览 / 组卷侧以外的 global 列表
- 向量语义去重、跨机构私有题共享

---

## 7. 测试要点

### 7.1 后端

- Admin 不传 `scope`：本机构 + global 均可见
- Admin `scope=org`：仅本机构
- Admin `scope=global`：仅 global
- Staff `scope=global`：空列表
- Staff 不传 / `scope=org`：仅本机构
- 与 `pending` / `status` / `subject_code` / 分页组合正确；`deleted` 仍排除

### 7.2 前端

- Admin：范围筛选切换会重置列表并带上对应 query
- Admin：列表显示范围列文案
- Staff：无范围筛选项；手工/OCR 创建仍不可选 global（现有行为）

---

## 8. 成功标准

1. Admin 可一键只看平台公共题，且分页正确。
2. 默认「全部」时体验与改前混排一致。
3. Staff 权限与可见性不扩大。
4. 无改归属、无新页面。

---

## 9. 实现文件（预期）

| 文件 | 变更 |
|------|------|
| `backend/app/services/question_bank.py` | `list(..., scope=)` |
| `backend/app/routers/org_question_bank.py` | Query `scope` |
| `backend/tests/test_question_bank_service.py` / `test_question_bank_api.py` | scope 过滤用例 |
| `frontend/src/api/questionBank.ts` | `scope` filter |
| `frontend/src/components/questionBank/QuestionBankPage.tsx` | 筛选 + 列 |
| `frontend/tests/QuestionBank.test.tsx` | Admin 筛选行为 |
