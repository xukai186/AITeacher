# 错题讲解落库缓存 — 产品设计规格

**日期：** 2026-07-27  
**状态：** 已实现  
**依赖：** 错题本页内讲解（`2026-07-23-wrong-book-inline-explain-design.md`）、学科 Agent `ChatToolLoop` / `explain_wrong_book_item`、`WrongBookItem`

---

## 1. 背景与目标

当前「错题讲解」每次点击都走 `POST /chat`（`ChatService.post_message`）：

1. **重复消耗 token**：同一题多次打开/刷新会反复调模型；
2. **污染 Workspace 会话**：讲解话术与 tool 中间消息写入学科 `ChatSession`，与日常答疑混在一起。

目标：同一道错题的讲解**默认只生成一次并落库**；之后读库返回，**不调模型、不写聊天会话**。仅当学生显式「重新生成讲解」时才再次调模型并覆盖。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 失效策略 | **方案 A**：仅学生点「重新生成讲解」才再调模型；不因重做/又错/模型变更/过期自动作废 |
| 存储形态 | **方案 1**：`wrong_book_items` 上增加讲解字段 + 专用 `POST .../explain` |
| 生成通道 | 复用 `ChatToolLoop` + `explain_wrong_book_item`，**不**经 `ChatService.post_message` |
| 列表载荷 | 列表返回 `has_explanation`；**不**在列表中返回全文（避免大 payload） |
| Workspace | 讲解结果**不**写入学科聊天历史 |

---

## 3. 数据模型

### 3.1 `wrong_book_items` 新增列（Alembic）

| 列 | 类型 | 说明 |
|----|------|------|
| `explanation_text` | `Text`，可空 | 最近一次生成的讲解正文 |
| `explanation_created_at` | `DateTime(timezone=True)`，可空 | 最近一次写入时间 |

- 无讲解时两字段均为 `NULL`
- 重新生成时**覆盖**全文与时间戳（不保留历史版本）

### 3.2 不做

- 独立 `wrong_book_explanations` 历史表
- 讲解版本号 / 模型名落库（YAGNI；若日后排查成本再加）

---

## 4. 后端行为

### 4.1 `POST /student/wrong-book/{item_id}/explain`

**鉴权：** `require_roles(student)`；条目必须属于当前学生（与 practice / archive 相同）。

**请求 body：**

```json
{ "regenerate": false }
```

- `regenerate` 缺省为 `false`

**逻辑：**

1. 加载条目；不存在或不属于本人 → 404（与 `get_item` 一致）
2. 若 `item.explanation_text` 非空且 `regenerate` 为 `false`：
   - **不**调用模型
   - 返回已存文案，`from_cache: true`
3. 否则：
   - 用该题 `subject_code`、固定内部话术（含 `item_id`）跑与学科聊天相同的 tool loop（provider/model 取 org `ModelPolicy` scene=`chat`，与 `ChatService` 一致）
   - 将最终助手文案写入 `explanation_text`，`explanation_created_at = now()`
   - `commit`
   - 返回文案，`from_cache: false`
4. **全程不**创建/追加 `ChatSession` / `ChatMessage`

**响应 schema（示例）：**

```json
{
  "explanation_text": "...",
  "from_cache": true,
  "explanation_created_at": "2026-07-27T12:00:00+00:00"
}
```

- 生成失败：与现有 chat 错误语义对齐（HTTP 错误 + `detail`）；**不**清空已有缓存（失败的 regenerate 保留旧文案）

### 4.2 `GET /student/wrong-book` 列表

`WrongBookItemOut` 增加：

- `has_explanation: bool` — `explanation_text` 是否非空

不在列表中返回 `explanation_text`。

### 4.3 生成实现要点

- 新建或扩展 service（如 `WrongBookExplainService.explain(...)`），内部调用 `ChatToolLoop.run`，`history_messages=[]`，`user_message` 与现前端固定话术对齐（含 `item_id=`），便于 mock 路由。
- 抽取「读 chat ModelPolicy」可与 `ChatService` 共用小函数，避免复制 provider/model 默认值逻辑（实现期按 DRY 处理；非必须拆公共模块若改动面过大）。

### 4.4 不改动

- `POST /chat` 与 Workspace `ChatPanel` 行为
- 练习 / 归档 / 掌握规则
- 讲解可含正确答案的产品语义（与 2026-07-23 规格一致）

---

## 5. 前端行为

### 5.1 API 客户端

`frontend/src/api/wrongBook.ts` 增加：

- `explainWrongItem(itemId, { regenerate?: boolean })` → 调用上述 POST

列表类型增加 `has_explanation: boolean`。

### 5.2 `WrongBookItemCard`

- **「错题讲解」**：`regenerate: false`；有缓存时读库，无则生成
- 首次进入页面若 `has_explanation`：可显示「已讲解」类提示；点「错题讲解」仍调 API（命中缓存，几乎无成本）或直接展开并拉一次（仍 `regenerate: false`）
- **「重新生成讲解」**：仅在已有讲解（本地或 `has_explanation`）时展示；`regenerate: true`，覆盖后刷新面板
- 收起 / 展开：仍只控 UI；**不再**用「再点一次主按钮 = 强制重算」作为默认语义（主按钮 = 获取/展示缓存；重算走「重新生成」）
- 加载 / 失败 / 重试：失败时保留旧文案（若有）；「重试」对首次失败或 regenerate 失败再发请求

### 5.3 不做

- 不在机构端本期展示讲解全文
- 不流式

---

## 6. 测试

### 6.1 后端

- 首次 explain：写入 `explanation_text`，`from_cache=false`；断言模型/tool loop 被调用（mock）
- 第二次 `regenerate=false`：`from_cache=true`；断言**不**再调 model gateway / tool loop
- `regenerate=true`：覆盖文案与时间戳，`from_cache=false`
- 他人 `item_id` → 404
- 列表项 `has_explanation` 与库一致

### 6.2 前端

- 点击讲解调用 `/wrong-book/{id}/explain` 而非 `/chat`
- 有缓存文案时展示；「重新生成」body 含 `regenerate: true`
- 失败路径与重试

---

## 7. 验收标准

1. 同一错题第二次及以后点「错题讲解」（非重新生成）不调模型，返回相同已存文案  
2. 「重新生成讲解」会调模型并覆盖落库  
3. 讲解过程不在 Workspace 学科会话中新增用户/助手消息  
4. 列表可区分是否已有讲解（`has_explanation`）  
5. 练习隐藏参考答案、讲解可含答案等既有产品语义不变  

---

## 8. 与既有规格关系

- 取代 `2026-07-23-wrong-book-inline-explain-design.md` §3.5 / §2「仅会话内存、走 `/chat`」中关于**持久化与通道**的描述；页内展开、答案可泄露、优先 `item_id` 等其余决策仍有效。  
- 实现后将本 spec 标为「已实现」，并在旧 spec 顶部加一句「讲解持久化见 2026-07-27」。
