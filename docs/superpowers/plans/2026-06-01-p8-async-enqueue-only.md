# P8+：PlanReview 仅入队 + 轮询

## 行为

- `POST /student/agent/apply-recommendations`：只创建 `plan_review_jobs`，返回 `job_id` + `status=pending`
- `GET /student/agent/plan-review-jobs/{job_id}`：查询状态；`succeeded` 时带 `created_count` / `warnings` 等
- 摸底/自测提交：只入队，不再 inline 执行
- 每日生成 CLI：只入队；由 `python -m app.jobs.run_plan_review_jobs` 消费
- 对话内 `generate_daily_tasks` / 手动同步 `SubjectAgentService` 仍可直接执行（即时反馈）

## 部署

生产环境需单独跑 Worker，详见 [docs/deployment/worker.md](../../deployment/worker.md)。

```bash
# API + worker 分离（cron 每分钟）
* * * * * cd backend && .venv/bin/python -m app.jobs.run_plan_review_jobs --once
```

## 前端

学情报告「生成明日任务」：入队 → 轮询 job 直至 `succeeded` / `failed`
