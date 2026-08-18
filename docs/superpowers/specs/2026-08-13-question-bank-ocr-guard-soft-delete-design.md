# 题库 OCR 提交守卫与软删除 — 产品设计规格

**日期：** 2026-08-13  
**状态：** 已实现  
**依赖：** 全局题库 P1–P3、题库编辑与知识点选择器（PR #49–#52）  
**关联：** `docs/superpowers/specs/2026-08-04-global-question-bank-design.md`、`docs/superpowers/specs/2026-08-10-question-bank-edit-node-picker-design.md`

---

## 1. 背景与目标

当前「图片识别添加」模式下，用户可不经成功 OCR 就走智能补全并入库，且可提交 `ocr_import` 而缺少 `source_image_asset_id`。题库仅有 `active → disabled`，无法从列表清掉待审/驳回/已禁用条目。

目标：

1. **OCR 严格守卫**：图片识别模式下必须先识别成功，才允许智能补全与入库；后端对 `ocr_import` 强制本机构图片资产。
2. **软删除**：非 `active` 题可标记为 `deleted`，默认列表与抽题/去重均排除；本期不提供恢复。

---

## 2. 已确认决策

| 维度 | 决策 |
|------|------|
| 删除语义 | 软删：`status = deleted`（不硬删、不加 `deleted_at`） |
| 可删状态 | 仅 `pending_review` / `rejected` / `disabled`；`active` 须先禁用 |
| 恢复 | 本期不做（无回收站、无恢复 API/UI） |
| OCR 失败/未识别 | 严格守卫：禁用智能补全；可改图重试或切回手工添加 |
| OCR 后端校验 | `ocr_import` 必须带本机构有效 `source_image_asset_id` |
| 权限 | 与现有 mutate 一致（staff：本机构；admin：org + global） |

---

## 3. 软删除

### 3.1 状态机

```
pending_review ──delete──► deleted
rejected       ──delete──► deleted
disabled       ──delete──► deleted
active         ──delete──► 409（须先禁用）
deleted        ──任意 mutate（含 edit/approve/reject/disable/delete）──► 409
```

编辑规则不变：可编辑仍为非 `active` 且非 `deleted`；`deleted` 不可再编辑。

### 3.2 API

- `POST /org/question-bank/{item_id}/delete` → `QuestionBankItemOut`
- 权限：复用 `_get_mutable_item`
- 成功：`status = deleted`；不清除 `reviewed_by` / `reviewed_at`（审计保留）

### 3.3 查询与副作用

| 场景 | 行为 |
|------|------|
| 默认列表 / 分页 | 始终排除 `status = deleted`（含显式 `status=deleted`：返回空列表，不做回收站） |
| 精确去重 | 忽略 `deleted` 行（允许同 stem 重新入库） |
| 自测抽题 | 仅 `active`（已满足；确认不会抽到 deleted） |
| 历史自测快照 | 不改动；`bank_item_id` 可仍指向已删题 |

### 3.4 UI

- 列表与详情：在可 mutate 且状态为 `pending_review` / `rejected` / `disabled` 时显示「删除」
- 二次确认：「删除后列表不再显示，确认删除？」
- 成功后刷新列表（同审核/禁用）
- 状态筛选器本期不加「已删除」

---

## 4. OCR 严格守卫

### 4.1 前端（图片识别模式）

- **识别成功**定义：OCR mutation 成功，且已写入 `sourceImageAssetId`
- 未成功时：禁用「智能补全」（无法进入确认页，故无法确认入库）
- 可选提示：「请先完成图片识别」
- 「开始识别」仍要求已选文件；失败显示错误；可换图重试
- 切回「手工添加」：清空 OCR 资产与识别态；提交走 `staff_manual` / `admin_manual`
- 识别成功后：题面仍可编辑，再智能补全 → 确认入库（`source_type = ocr_import` + 该 asset）

### 4.2 后端

创建时若 `source_type == "ocr_import"`：

1. `source_image_asset_id` 必填，否则 422
2. 资产须存在且 `org_id == actor.org_id`，否则 422
3. 不要求服务端再次执行 OCR（以合法本机构资产为准）

手工来源不强制图片资产。

---

## 5. 错误码

| 场景 | HTTP |
|------|------|
| 删除 `active` 或已 `deleted` | 409 |
| 无权限 / 跨机构 | 403 / 404（沿用现有） |
| `ocr_import` 缺或非法 asset | 422 |

---

## 6. 组件边界

| 单元 | 职责 |
|------|------|
| `QuestionBankService.delete` | 状态校验与软删落库 |
| `QuestionBankService.list` / `find_exact_duplicate` | 默认排除 `deleted` |
| `QuestionBankService.create` | `ocr_import` 资产校验 |
| `POST .../delete` router | HTTP 入口 |
| `QuestionBankPage` | OCR 按钮守卫、删除入口与确认 |

---

## 7. 测试要点

### 后端

- 非 `active` DELETE/软删成功 → `deleted`
- `active` / 已 `deleted` → 409
- 默认列表不含 `deleted`
- 精确去重忽略 `deleted`，允许同 stem 新建
- `ocr_import` 无 asset / 跨机构 asset → 422；合法 asset → 201 `pending_review`

### 前端

- OCR 模式未识别成功时「智能补全」不可用
- 识别成功后可走完入库，且 create body 含 `source_image_asset_id`
- 非 active 可删；确认后调用 delete 并刷新

---

## 8. 非目标

- 恢复 / 回收站 UI 或 API
- 硬删除行、`deleted_at` 列
- OCR 失败自动改为手工来源
- 多图 OCR / 一图多题
- 改归属 `scope`

---

## 9. 验收标准

1. 图片识别模式在未成功识别前无法智能补全或入库；`ocr_import` 入库必带本机构图片资产。
2. 老师/管理员可对非 `active` 题软删除；列表不再显示；`active` 须先禁用。
3. 已删除题不参与去重与抽题；历史自测卷面内容不变。
