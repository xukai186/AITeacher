# 后台 Worker 部署说明

从 **P8** 起，计划复审（`plan_review_jobs`）采用 **API 入队 + 独立 Worker 消费** 模式。只启动 FastAPI 而不跑 Worker 时，学情报告「生成明日任务」、摸底/自测提交后的任务生成、每日定时入队等会一直处于 `pending`。

## 架构

```text
┌─────────────┐     写入 pending      ┌──────────────────┐
│  FastAPI    │ ────────────────────► │ plan_review_jobs │
│  (uvicorn)  │                       └────────┬─────────┘
└─────────────┘                                │
       ▲                                       │ 消费
       │ 轮询 job 状态                          ▼
┌─────────────┐                       ┌──────────────────┐
│  前端       │                       │ run_plan_review  │
└─────────────┘                       │ _jobs (Worker)   │
                                      └──────────────────┘

每日 00:05（可选）:
  daily_task_generation → 为全员入队次日 plan_review_jobs
  （仍需 Worker 执行）
```

## 前置条件

Worker 与 API **共用同一 PostgreSQL**，且 schema 版本一致：

```bash
cd backend
source .venv/bin/activate   # 或 uv venv
alembic upgrade head
```

环境变量（与 API 相同，前缀 `AITEACHER_`）：

| 变量 | 说明 |
|------|------|
| `AITEACHER_DATABASE_URL` | 生产库连接串，例如 `postgresql+psycopg://user:pass@host:5432/aiteacher` |
| `AITEACHER_JWT_SECRET` | Worker 不校验 JWT，但保持 `.env` 一致便于运维 |

在 `backend/` 目录放置 `.env`，或 systemd `EnvironmentFile` 指向该文件。

## 两个后台命令

### 1. 计划复审 Worker（必须）

消费 `plan_review_jobs`：单科生成任务 → 跨科削减 → 必要时写入总计划待确认等。

```bash
cd /path/to/AITeacher/backend
source .venv/bin/activate
python -m app.jobs.run_plan_review_jobs --once
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--once` | 否 | 处理一批后退出（适合 cron）；省略则常驻循环 |
| `--limit` | 50 | 每批最多处理 job 数 |
| `--sleep` | 1.0 | 常驻模式下无任务时的休眠秒数 |

**建议频率：** 每分钟执行一次 `--once`（生产常见做法）。

### 2. 每日入队（推荐）

为所有启用科目的学员创建**次日**的 `plan_review_jobs`（`trigger=daily_schedule`），并检查连续低完成率触发。

```bash
cd /path/to/AITeacher/backend
source .venv/bin/activate
python -m app.jobs.daily_task_generation
```

- 退出码 `0` 成功，`1` 表示有条目入队失败（见 stdout JSON）。
- **建议 cron：** 每天 **00:05**（按机构时区调整 crontab 的 `TZ` 或系统时区）。

## Cron 示例

将 `/path/to/AITeacher` 换成实际部署路径，并确保使用项目虚拟环境中的 Python。

```cron
# /etc/cron.d/aiteacher  (示例)
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# 每分钟消费计划复审队列
* * * * * deploy cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.run_plan_review_jobs --once >> /var/log/aiteacher/plan-review-worker.log 2>&1

# 每天 00:05 为次日入队（Asia/Shanghai 示例：在 crontab 顶部设 TZ=Asia/Shanghai）
5 0 * * * deploy cd /path/to/AITeacher/backend && .venv/bin/python -m app.jobs.daily_task_generation >> /var/log/aiteacher/daily-enqueue.log 2>&1
```

`deploy` 为运行用户，需对代码目录有读权限、对日志目录有写权限。

## systemd 示例

### 常驻 Worker（替代每分钟 cron）

`/etc/systemd/system/aiteacher-plan-review.service`：

```ini
[Unit]
Description=AITeacher plan review job worker
After=network.target postgresql.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/path/to/AITeacher/backend
EnvironmentFile=/path/to/AITeacher/backend/.env
ExecStart=/path/to/AITeacher/backend/.venv/bin/python -m app.jobs.run_plan_review_jobs --limit 50 --sleep 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aiteacher-plan-review.service
sudo journalctl -u aiteacher-plan-review.service -f
```

### 每日入队（oneshot + timer）

`/etc/systemd/system/aiteacher-daily-enqueue.service`：

```ini
[Unit]
Description=AITeacher daily plan review enqueue

[Service]
Type=oneshot
User=deploy
WorkingDirectory=/path/to/AITeacher/backend
EnvironmentFile=/path/to/AITeacher/backend/.env
ExecStart=/path/to/AITeacher/backend/.venv/bin/python -m app.jobs.daily_task_generation
```

`/etc/systemd/system/aiteacher-daily-enqueue.timer`：

```ini
[Unit]
Description=Run AITeacher daily enqueue at 00:05

[Timer]
OnCalendar=*-*-* 00:05:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now aiteacher-daily-enqueue.timer
```

## 运维检查

### 队列是否积压

```sql
SELECT status, COUNT(*) FROM plan_review_jobs GROUP BY status;
```

长期大量 `pending` 且 `run_after <= now()` → Worker 未跑或失败。

### 最近失败任务

```sql
SELECT id, student_user_id, subject_code, trigger, last_error, attempts, updated_at
FROM plan_review_jobs
WHERE status IN ('failed', 'retry')
ORDER BY updated_at DESC
LIMIT 20;
```

失败 job 在达到 `max_attempts` 后为 `failed`；可结合日志排查后手动改回 `pending` 重试（一期无管理 UI）。

### 本地手动跑一批

```bash
cd backend && source .venv/bin/activate
python -m app.jobs.run_plan_review_jobs --once --limit 10
```

## 与 API 行为对照

| 路径 | 是否同步执行 PlanReview |
|------|-------------------------|
| 对话内 `generate_daily_tasks` | 是（即时） |
| `POST /student/agent/apply-recommendations` | 否，仅入队 |
| 摸底 / 自测提交 | 否，仅入队 |
| `daily_task_generation` cron | 否，仅入队 |

## 相关文档

- [P8 异步入队计划](../superpowers/plans/2026-06-01-p8-async-enqueue-only.md)
- [P7 每日定时入队](../superpowers/plans/2026-05-29-p7-scheduler-planner-ui.md)
- 实现：`backend/app/jobs/run_plan_review_jobs.py`、`backend/app/jobs/daily_task_generation.py`
