# 题库精确去重 — 并发安全 — 产品设计规格

**日期：** 2026-08-20  
**状态：** 已实现  
**依赖：** 全局题库 P1–P3、OCR 守卫与软删除（PR #53–#54）  
**关联：** `docs/superpowers/specs/2026-08-04-global-question-bank-design.md` §6.2、`docs/superpowers/specs/2026-08-13-question-bank-ocr-guard-soft-delete-design.md`

---

## 1. 背景与目标

当前精确去重仅在应用层实现：`QuestionBankService.create()` 在插入前调用 `find_exact_duplicate()`，重复则返回 **409**。并发场景下两个请求可能同时通过检查并各插入一行，产生重复的 `active` 或 `pending_review` 记录。

目标：

1. **数据库级兜底**：在 `active` / `pending_review` 状态下，同一去重键不可存在两行。
2. **语义不变**：保留 `allow_inactive_duplicate`、软删后同 stem 重建、`find_exact_duplicate` 优先级规则。
3. **迁移可落地**：历史重复数据自动合并（soft-delete 多余行），无需人工介入。

---

## 2. 已确认决策

| 维度 | 决策 |
|------|------|
| 实现方式 | 部分唯一索引 + 应用层 `find_exact_duplicate` 双保险 |
| 纳入唯一约束的状态 | 仅 `active`、`pending_review` |
| 不纳入唯一约束的状态 | `rejected`、`disabled`、`deleted` |
| 去重键 | `scope + org_id + q_type + btrim(stem)`（与现有一致） |
| `global` 题 `org_id = NULL` | 索引表达式使用 `COALESCE(org_id, sentinel UUID)` |
| 历史重复数据 | 自动合并：保留优先级最高行，其余 `status = deleted` |
| 保留优先级 | `active` > `pending_review` > `created_at DESC` > `id DESC`（同 `find_exact_duplicate`） |
| 冲突响应 | 统一 **409**，文案 `"exact question bank duplicate"` |
| 前端 | 无改动（已处理 409） |

---

## 3. 去重键与索引

### 3.1 去重键定义

与 `find_exact_duplicate` 一致：

```
(scope, org_id, q_type, btrim(stem))
```

- `stem` 入库与比较均经 `strip()` / `btrim()` 规范化。
- `scope = global` 时 `org_id` 为 `NULL`；索引中用零 UUID sentinel 代替，避免 PostgreSQL 唯一索引对 `NULL` 不互斥的问题。

### 3.2 部分唯一索引

```sql
CREATE UNIQUE INDEX uq_qbi_exact_dedupe
ON question_bank_items (
  scope,
  COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
  q_type,
  (btrim(stem))
)
WHERE status IN ('active', 'pending_review');
```

### 3.3 现有索引

保留非唯一索引 `ix_qbi_exact_lookup`（`(scope, org_id, q_type, btrim(stem))`）。`find_exact_duplicate` 仍需查询 `rejected` / `disabled` 等状态，部分唯一索引无法替代该 lookup。

在 `QuestionBankItem.__table_args__` 中同步声明 `uq_qbi_exact_dedupe`（含 `postgresql_where`）。

---

## 4. 迁移

新 Alembic revision，`down_revision = c2d3e4f5a6b7`。

### 4.1 Step 1 — 合并历史重复

仅处理 `status IN ('active', 'pending_review')` 的分组重复：

1. 按 `(scope, COALESCE(org_id, sentinel), q_type, btrim(stem))` 分组。
2. 每组保留一行：优先级 `active` > `pending_review` > `created_at DESC` > `id DESC`。
3. 其余行：`status = 'deleted'`，`updated_at = now()`。
4. 迁移日志输出 soft-delete 条数（便于审计）。

不 hard-delete；与软删除语义一致。

### 4.2 Step 2 — 创建唯一索引

执行 §3.2 的 `CREATE UNIQUE INDEX uq_qbi_exact_dedupe`。

---

## 5. Service 层行为

### 5.1 不变部分

| 组件 | 行为 |
|------|------|
| `find_exact_duplicate` | 排除 `deleted`；优先 `active` > `pending_review` > 其他；排序规则不变 |
| `create()` 前置检查 | 保留；`allow_inactive_duplicate` 逻辑不变 |
| `list` / 自测抽题 | 不变 |

### 5.2 新增：`IntegrityError` 兜底

提取 helper（如 `_flush_or_raise_duplicate(db)`），在以下路径的 `db.flush()` 处调用：

| 路径 | 触发场景 |
|------|----------|
| `create()` | 并发双写同 stem |
| `approve()` | 审核通过时与已有 `active`/`pending_review` 冲突（如 `rejected` 与 `pending` 同 stem） |
| `update()` | 修改 `stem` / `q_type` 后与已有行冲突 |

捕获条件：PostgreSQL 唯一约束违反，索引名 `uq_qbi_exact_dedupe`（或等价 constraint 名）。

响应：

```http
HTTP/1.1 409 Conflict
"exact question bank duplicate"
```

与现有应用层 409 文案一致。

### 5.3 不在本期

- `update()` / `approve()` 前置显式 `find_exact_duplicate`（仅 IntegrityError 兜底）。
- 向量 / 语义去重。
- 前端改动。

---

## 6. 行为矩阵（回归对照）

| 场景 | 预期 |
|------|------|
| 同 scope/org 下重复 `active` 题干 + 题型 | 409（create） |
| 已有 `rejected`/`disabled`，再 create 同 stem | 允许（`allow_inactive_duplicate=True` 或普通 create 无 active/pending 冲突） |
| 软删后同 stem 重建 | 允许（`deleted` 不在唯一索引内） |
| 并发两路 create 同 stem | 一路成功，一路 409 |
| `approve` 后与已有 active 冲突 | 409 |
| `update` stem 改为与另一 active/pending 相同 | 409 |
| `global` 题（`org_id = NULL`）重复 | 409（sentinel 保证互斥） |

---

## 7. 测试要点

### 7.1 迁移

- 造两条同键 `active`/`pending_review` 重复 → 迁移后保留 1 条、其余 `deleted` → 唯一索引创建成功。

### 7.2 Service / API

- `create` 重复 → 409（应用层）。
- `allow_inactive_duplicate` 仍可用。
- 两 DB session 并发 `create` 同 stem → 一成功、一 409。
- `approve` 冲突 → 409。
- `update` stem 冲突 → 409。
- 软删后 recreate 同 stem → 成功。

### 7.3 回归

- `find_exact_duplicate` 优先级测试仍通过。
- 自测 assembler `allow_inactive_duplicate` 路径不受影响。

---

## 8. 成功标准

1. 任意并发下不存在两条同为 `active` 或 `pending_review` 的精确重复（同 scope/org/q_type/stem）。
2. 现有精确去重产品语义不变：`inactive` 可重建、软删后可重建、409 文案不变。
3. 迁移可在含历史重复的数据库上一次性跑通，无需人工清理。

---

## 9. 实现文件（预期）

| 文件 | 变更 |
|------|------|
| `backend/alembic/versions/*_question_bank_exact_dedupe_unique.py` | 合并重复 + 唯一索引 |
| `backend/app/models/question_bank.py` | 声明 `uq_qbi_exact_dedupe` |
| `backend/app/services/question_bank.py` | `_flush_or_raise_duplicate`；create/approve/update 调用 |
| `backend/tests/test_question_bank_service.py` | 并发与 IntegrityError 用例 |
| `backend/tests/test_question_bank_migration.py`（或同类） | 迁移合并用例 |
