# 错题本页内讲解 — 产品设计规格

**日期：** 2026-07-23  
**状态：** 已实现  
**依赖：** 学科 Agent `/chat`、`explain_wrong_book_item` / `list_wrong_book`、错题本页 `WrongBook.tsx`、`ChatRichText`

---

## 1. 背景与目标

错题讲解能力已存在于学科聊天工具链（`explain_wrong_book_item`），但学生端错题本卡片没有入口；聊天仅嵌在 Workspace，且无 deep-link / 预填。

目标：在**错题本列表每一题**上提供「错题讲解」，**留在本页**展开结果，复用现有 `/chat` + 学科 Agent，不新增专用 REST。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 展示位置 | **方案 B**：留在错题本页，题下方展开 |
| 答案泄露 | **方案 A**：讲解可含正确选项与完整解析（与「重做前隐藏参考答案」并存；点讲解即允许看到答案） |
| 实现路径 | **方案 1**：卡片直接 `POST /chat`（subject），不新增 explain API |
| 题目定位 | 话术**优先 `item_id`**；附带页面「错题 N」仅作兜底文案 |
| 持久化 | 仅当前页会话内存；刷新后需重新点讲解 |
| 流式 | 不做；沿用现有非流式 `ChatPostResponse.assistant_message` |

---

## 3. 前端行为

### 3.1 入口

- 组件：`WrongBookItemCard`（`frontend/src/pages/student/WrongBook.tsx`）
- 所有状态（`active` / `mastered` / `archived`）均显示按钮 **「错题讲解」**
- 与现有「提交重做 / 再练一次 / 归档」并列，不替换重做流程

### 3.2 交互状态（按 `item.id`）

| 状态 | UI |
|------|-----|
| idle | 仅按钮 |
| loading | 按钮「讲解中…」禁用；可显示占位行 |
| ready | 展开区渲染助手文案；按钮可再点 → **重新请求**并覆盖 |
| error | 错误文案 +「重试」 |

- 可选「收起」：只折叠展开区，保留已缓存文案，再展开无需重请求
- 同一 `item.id` 在 `loading` 时禁止并发第二次请求
- 多题可同时各自处于 ready（互不关闭）

### 3.3 请求

```ts
postChat({
  agent_type: "subject",
  subject_code: item.subject_code, // 始终用该题科目，不受「全部科目」筛选影响
  message: `请讲解错题本条目 item_id=${item.id}（页面错题 ${index}）。结合我的当时作答说明错因与正确思路。`,
})
```

- 使用现有 `frontend/src/api/chat.ts` 的 `postChat`
- 助手回复用 `ChatRichText` 渲染（与聊天面板一致的换行 / 轻量 markdown / KaTeX）

### 3.4 与「重做隐藏答案」的关系

- **不**因讲解而自动改写 `showAnswers` / `reveal` 状态
- 参考答案区仍可在未重做前保持隐藏；讲解面板独立展示模型回复（其中可含答案）
- 文案无需额外警告；产品已接受「点讲解即可看答案」

### 3.5 不做

- 不改 Workspace `ChatPanel`、无 URL prompt deep-link
- 不在错题本页嵌入完整多轮会话（本期单次请求 → 单段回复）
- 不把讲解结果写入错题本后端字段

---

## 4. 后端行为

### 4.1 既有能力（保持）

- `explain_wrong_book_item` 已支持 `item_id` 或 `list_index`
- 学科 Agent tool 定义与 executor 已接线

### 4.2 Mock 路由补强（本期必做）

文件：`backend/app/services/model_gateway.py`

当前 mock 仅从「第 N 题」解析 `list_index`，本地/测试环境下卡片带 `item_id=` 的话术会对错题。

- 若用户消息匹配 `错题本` 且含讲解意图，且能解析 `item_id=<uuid>`（或等价清晰模式）→ tool args 使用该 `item_id`
- 否则回退现有「第 N 题」→ `list_index`（默认 1）逻辑

真实模型路径仍依赖 tool schema 中的 `item_id`，无需改定义（已有）。

### 4.3 不改动

- 不新增 `POST /student/wrong-book/{id}/explain`
- 不改 `WrongBookService` 列表/练习/归档语义

---

## 5. 测试

### 5.1 前端

- `WrongBook.test.tsx`（或同文件扩写）：
  - 点击「错题讲解」后 `fetch`/`postChat` 收到含 `item_id=` 与对应 `subject_code` 的 body
  - loading → 成功文案出现在卡片下
  - 失败时出现错误与可重试

### 5.2 后端

- mock：含 `item_id=<uuid>` 的讲解话术 → `explain_wrong_book_item` arguments 含该 id
- 既有 `list_index` mock 路径回归不破坏

---

## 6. 验收标准

1. 错题本任意一条可见「错题讲解」，点击后本页展开讲解，无需跳转 Workspace  
2. 请求使用该题 `subject_code` + `item_id`，筛选「全部科目」或分页时仍讲对本题  
3. 讲解可含正确答案；未点讲解时，重做前参考答案仍可隐藏  
4. 加载中、失败重试、再次点击覆盖刷新行为符合 §3.2  
5. 本地 mock 下用 `item_id` 话术能稳定讲评（§4.2）
)
