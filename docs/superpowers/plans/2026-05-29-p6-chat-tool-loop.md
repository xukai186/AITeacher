# P6 Chat：ChatService + LLM Tool Loop

## 目标

学科 / 总规划对话中，模型可调用内部工具（学生不可直接调 HTTP），根据工具结果生成回复。

## 实现

- `ModelGateway.complete()`：支持 `messages` + OpenAI `tools`；`mock` 用关键词触发工具，`openai_compat` 走原生 function calling。
- `ChatToolLoop`：最多 5 轮 tool loop；持久化 `__TOOL_CALLS__` 与 `tool` 角色消息供多轮上下文。
- `ChatToolExecutor`：`get_subject_context`、`generate_daily_tasks`（走 `PlanReviewService`）。
- `ChatService.post_message`：加载会话历史 → loop → 返回 `tools_used`。
- API：`ChatPostResponse.tools_used`。

## 触发示例（mock）

| 用户意图（示例） | 工具 |
|------------------|------|
| 学情 / 薄弱点 | `get_subject_context` |
| 生成 / 明日 / 任务 | `generate_daily_tasks` |

## 验收

- `pytest tests/test_chat_tool_loop.py tests/test_chat_api_mock.py`
- 全量 `pytest` 通过

## 后续

- 总规划专属工具（`get_master_plan` 等）
- 前端展示 `tools_used`、流式输出
- 更可靠的意图识别（替换 mock 关键词）
