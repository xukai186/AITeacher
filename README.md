# AITeacher

One-on-one AI tutors for graduate-exam students. See `docs/superpowers/specs/2026-05-26-ai-teacher-design.md`.

## Repo layout

- `backend/` — FastAPI service
- `frontend/` — React workspace UI
- `docs/superpowers/` — specs and plans
- `docs/deployment/` — production ops (e.g. [worker](docs/deployment/worker.md))

## Local dev (P1)

```bash
docker compose up -d           # PostgreSQL on localhost:5433
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install && npm run dev
```

Default admin: `admin@demo.example` / `admin123`.

## P1 verification

After `python -m app.seed`:

- admin@demo.example / admin123 → `/admin/students`
- teacher@demo.example / teach123 → `/staff/students`
- student@demo.example / stud123 → `/student/workspace`
