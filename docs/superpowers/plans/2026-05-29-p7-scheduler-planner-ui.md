# P7：定时生成 + 总规划工具 + 前端 tools_used

## 1. 每日 00:05 定时生成

- `DailyTaskGenerationService.run()`：为所有 `StudentSubject.enabled` 跑 `PlanReviewService`（`trigger=daily_schedule`，默认次日）。
- CLI：`python -m app.jobs.daily_task_generation`（供 cron 调用，退出码 1 表示有科目失败）。

```cron
5 0 * * * cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.daily_task_generation
```

## 2. 总规划 Agent 工具（对话）

| 工具 | 说明 |
|------|------|
| `get_student_overview` | 各科目学情摘要 |
| `get_master_plan` | 总规划版本与每日预算 |
| `trigger_plan_review` | 复审并生成任务（可选单科） |
| `get_subject_context` | 单科详情（需 subject_code） |

## 3. 前端

- 助手消息下方展示 `已调用：tool1、tool2`（来自 `tools_used`）。

## 验收

- `pytest tests/test_daily_task_generation.py tests/test_planner_chat_tools.py`
- 全量 pytest / vitest 通过
