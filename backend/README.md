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
uvicorn app.main:app --reload --port 8000
```

## Test

```bash
pytest -v
```
