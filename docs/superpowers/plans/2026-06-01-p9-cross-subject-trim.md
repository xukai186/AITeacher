# P9：跨科协调削减

## 行为

- 科目权重：套餐 `Package.subject_codes` 顺序（靠前权重更高）；无套餐时各启用科目权重相同。
- 当日总时长超 `MasterPlanVersion.daily_time_budget_json` 时，优先取消**低权重科目**的**低优先级**任务（`study` > `check_result` > `self_test` > `review_wrong` 保留顺序不变）。
- 单科 `PlanReviewService` 只生成任务，**不在单科复审时削减**。
- `PlanReviewJobRunner` 在一批 job 执行完后，按 `(student, date)` 做一次跨科 `trim_tasks_by_budget`，并回写 job `warnings` / `cross_subject_cancelled`。

## 验收

- `pytest tests/test_cross_subject_trim.py tests/test_plan_review.py`
