# P6：学科 Agent — 建议落成每日任务

## 目标

将 P5 学情报告中的规则建议，通过**学科 Agent 服务层**落成可执行的 `DailyTask`（默认次日），并做总规划时长校验提示；学生从学情报告页一键触发，不自动改计划。

## 范围（本期 MVP）

- `SubjectAgentService.apply_report_recommendations`：读取 `ReportService.overview` 的 `recommendations`，幂等写入 `DailyTask`（`ref_id` = uuid5 去重）。
- 任务类型映射：`review_wrong` / `self_test` / `check_result`，`payload_json.source = report_recommendation`。
- 总规划：对比 `MasterPlanVersion.daily_time_budget_json` 当日预算，超预算返回 `warnings`（不自动削减）。
- API：`POST /student/agent/apply-recommendations?subject_code=&target_date=`
- 前端：学情报告「生成明日任务」按钮。

## P6+（已完成）

- `AgentToolRegistry`：`get_subject_context`、`generate_daily_tasks`
- `PlanReviewService`：内部 Pipeline（生成任务 → 总规划削减）
- `MasterPlannerService.trim_tasks_by_budget`：超预算取消低优先级 `pending` 任务（`study` 先于 `review_wrong`）
- 触发：自测 `graded`、摸底完成、手动「生成明日任务」（均走 `PlanReviewService`）
- 今日任务 API 仅返回 `status=pending`

## 非本期

- LLM / `ChatService` tool loop（对话触发工具）
- `plan_review_jobs` 表与异步队列、cron 00:05
- 跨科多科目协调削减
- 自测 `generate_paper` 与任务条目联动

## 验收

- `pytest tests/test_subject_agent_tasks.py tests/test_plan_review.py tests/test_agent_tools.py` 通过
- 自测交卷后次日存在 `review_wrong` 类任务（无需手点按钮）
- 前端 `npm test -- --run` 通过
