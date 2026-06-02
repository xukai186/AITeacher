# backend

FastAPI service for AITeacher.

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## DB

```bash
docker compose -f ../docker-compose.yml up -d
alembic upgrade head
python -m app.seed
```

Seed creates:

- `admin@demo.example` / `admin123` (org_admin)
- `teacher@demo.example` / `teach123` (org_staff, owns the student)
- `student@demo.example` / `stud123` (student in "Standard" package)

## Run

```bash
uvicorn app.main:app --reload --host :: --port 8000
```

## Background workers (production)

Plan review jobs are enqueued by the API and processed asynchronously. See [docs/deployment/worker.md](../docs/deployment/worker.md) for cron/systemd setup.

```bash
# process queued jobs once (also used in cron every minute)
python -m app.jobs.run_plan_review_jobs --once

# enqueue next-day jobs (typically 00:05 daily)
python -m app.jobs.daily_task_generation
```

## Test

```bash
pytest -v
```
