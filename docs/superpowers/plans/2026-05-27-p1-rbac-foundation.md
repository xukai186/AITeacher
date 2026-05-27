# P1 — Foundation: Accounts, Org RBAC, Admin Backend Skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the AITeacher monorepo with PostgreSQL, JWT-based auth, the org/user/package/staff-student data model, and a minimal management backend + frontend so that institution admins, staff, and students can log in and see role-appropriate empty surfaces.

**Architecture:** Python FastAPI backend (SQLAlchemy 2.0 + Alembic + PostgreSQL) exposing JSON APIs guarded by JWT and a permission layer that combines role checks with `StaffStudent` scoping. React + TypeScript (Vite) frontend with TanStack Query, Tailwind, and role-aware routing. Local PostgreSQL via Docker Compose; tests run against the same engine using a per-test transaction rollback fixture.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, psycopg[binary], passlib[bcrypt], python-jose[cryptography], pytest, pytest-asyncio, httpx
- Frontend: React 18, TypeScript 5, Vite 5, React Router 6, TanStack Query 5, Tailwind CSS 3, vitest, @testing-library/react, msw
- Infra: Docker Compose (PostgreSQL 16)

**Conventions:**
- All money/time fields in DB use UTC `TIMESTAMP WITH TIME ZONE`.
- All primary keys are `uuid` (`gen_random_uuid()` via `pgcrypto`).
- Tests live next to the layer they cover (`backend/tests/...`, `frontend/tests/...`).
- Run backend tests from `backend/` with `uv run pytest` (or `pytest` inside the venv).
- Run frontend tests from `frontend/` with `npm test -- --run`.
- Commit messages use Conventional Commits (`feat:`, `test:`, `chore:`).

---

## File Structure (P1)

Top-level:

```
AITeacher/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app + router includes
│   │   ├── config.py                # Pydantic settings (DB URL, JWT secret)
│   │   ├── database.py              # Engine, SessionLocal, get_db dep
│   │   ├── models/                  # SQLAlchemy ORM
│   │   │   ├── base.py
│   │   │   ├── organization.py
│   │   │   ├── user.py              # User + UserRole enum
│   │   │   ├── student.py           # StudentProfile, StudentSubject
│   │   │   ├── package.py
│   │   │   ├── staff_student.py
│   │   │   └── audit.py
│   │   ├── schemas/                 # Pydantic request/response
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── student.py
│   │   │   ├── package.py
│   │   │   └── staff.py
│   │   ├── auth/
│   │   │   ├── security.py          # password hashing, JWT encode/decode
│   │   │   ├── deps.py              # get_current_user
│   │   │   └── permissions.py       # role + StaffStudent scoping
│   │   ├── routers/
│   │   │   ├── auth.py              # POST /auth/login
│   │   │   ├── me.py                # GET /me
│   │   │   ├── admin_students.py
│   │   │   ├── admin_staff.py
│   │   │   ├── admin_packages.py
│   │   │   ├── staff_students.py
│   │   │   └── student_profile.py
│   │   ├── services/
│   │   │   └── audit.py
│   │   └── seed.py                  # CLI: seed default org + admin
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/                # generated migration files
│   ├── tests/
│   │   ├── conftest.py              # DB + client fixtures
│   │   ├── factories.py             # builders for Org/User/etc.
│   │   ├── test_auth.py
│   │   ├── test_permissions.py
│   │   ├── test_admin_students.py
│   │   ├── test_admin_staff.py
│   │   ├── test_admin_packages.py
│   │   ├── test_staff_assignment.py
│   │   ├── test_staff_students.py
│   │   └── test_student_profile.py
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── students.ts
│   │   │   ├── staff.ts
│   │   │   └── packages.ts
│   │   ├── auth/
│   │   │   └── AuthContext.tsx
│   │   ├── components/
│   │   │   ├── ProtectedRoute.tsx
│   │   │   └── Layout.tsx
│   │   └── pages/
│   │       ├── Login.tsx
│   │       ├── admin/
│   │       │   ├── StudentsList.tsx
│   │       │   ├── StaffList.tsx
│   │       │   └── PackagesList.tsx
│   │       ├── staff/MyStudents.tsx
│   │       └── student/Workspace.tsx
│   ├── tests/
│   │   ├── setup.ts
│   │   ├── Login.test.tsx
│   │   └── ProtectedRoute.test.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── README.md
├── docker-compose.yml
└── README.md
```

---

## Task 0: Repo scaffold, Docker Compose, root README

**Files:**
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `.gitignore`

- [ ] **Step 1: Write `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.coverage

# Node
node_modules/
dist/
.vite/

# Env
.env
.env.local

# OS
.DS_Store
```

- [ ] **Step 2: Write `docker-compose.yml` for PostgreSQL**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: aiteacher
      POSTGRES_PASSWORD: aiteacher
      POSTGRES_DB: aiteacher
    ports:
      - "5433:5432"
    volumes:
      - aiteacher_pgdata:/var/lib/postgresql/data

volumes:
  aiteacher_pgdata:
```

- [ ] **Step 3: Write root `README.md`**

```markdown
# AITeacher

One-on-one AI tutors for graduate-exam students. See `docs/superpowers/specs/2026-05-26-ai-teacher-design.md`.

## Repo layout

- `backend/` — FastAPI service
- `frontend/` — React workspace UI
- `docs/superpowers/` — specs and plans

## Local dev (P1)

```bash
docker compose up -d           # PostgreSQL on localhost:5433
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install && npm run dev
```

Default admin: `admin@demo.local` / `admin123`.
```

- [ ] **Step 4: Start PostgreSQL and verify it accepts connections**

Run:
```bash
docker compose up -d
docker compose exec db pg_isready -U aiteacher
```
Expected: `accepting connections`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore docker-compose.yml README.md
git commit -m "chore: scaffold repo with docker-compose postgres and readme"
```

---

## Task 1: Backend project init (pyproject, config, db session, health route)

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[project]
name = "aiteacher-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.1",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "passlib[bcrypt]>=1.7",
    "python-jose[cryptography]>=3.3",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `backend/app/__init__.py`**

```python
```

- [ ] **Step 3: Write `backend/app/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher"
    test_database_url: str = "postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AITEACHER_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Write `backend/app/database.py`**

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Write `backend/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="AITeacher API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Write `backend/tests/__init__.py`**

```python
```

- [ ] **Step 7: Write `backend/tests/conftest.py` (minimal — DB fixtures added in Task 2)**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 8: Write the failing health test in `backend/tests/test_health.py`**

```python
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 9: Install deps and run the test**

Run:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_health.py -v
```
Expected: `1 passed`.

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(backend): init fastapi app with health route and pytest"
```

---

## Task 2: Models — Organization + User; Alembic + per-test transaction fixture

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/organization.py`
- Create: `backend/app/models/user.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (empty dir, add `.gitkeep`)
- Modify: `backend/tests/conftest.py` (add db + override get_db)
- Create: `backend/tests/factories.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write `backend/app/models/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Write `backend/app/models/organization.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Write `backend/app/models/user.py`**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRole(str, enum.Enum):
    student = "student"
    org_staff = "org_staff"
    org_admin = "org_admin"


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_users_org_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, default=UserStatus.active
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: Write `backend/app/models/__init__.py`**

```python
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User, UserRole, UserStatus

__all__ = ["Base", "Organization", "User", "UserRole", "UserStatus"]
```

- [ ] **Step 5: Write `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 6: Write `backend/alembic/script.py.mako`**

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 7: Write `backend/alembic/env.py`**

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import get_settings
from app.models import Base  # noqa: F401 ensure models registered
import app.models.organization  # noqa: F401
import app.models.user  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: Add `.gitkeep` so the empty versions dir is tracked**

```bash
touch backend/alembic/versions/.gitkeep
```

- [ ] **Step 9: Create the test database**

Run:
```bash
docker compose exec db psql -U aiteacher -c "CREATE DATABASE aiteacher_test;"
```
Expected: `CREATE DATABASE` (or `already exists` — both fine).

- [ ] **Step 10: Generate the first migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "initial org and user"
```
Expected: file created under `alembic/versions/`. Open it and confirm it creates `organizations` and `users` tables. If the autogen missed `CREATE EXTENSION IF NOT EXISTS pgcrypto`, prepend this line at the top of `upgrade()`:

```python
op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
```

- [ ] **Step 11: Apply migration to dev and test DBs**

Run:
```bash
alembic upgrade head
AITEACHER_DATABASE_URL=postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test alembic upgrade head
```
Expected: both finish without errors.

- [ ] **Step 12: Rewrite `backend/tests/conftest.py` to use a transactional fixture**

```python
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app

os.environ["AITEACHER_DATABASE_URL"] = get_settings().test_database_url
test_engine = create_engine(get_settings().test_database_url, future=True)
TestSession = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    future=True,
    join_transaction_mode="create_savepoint",
)


@pytest.fixture
def db_session() -> Session:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session) -> TestClient:
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 13: Write `backend/tests/factories.py`**

```python
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Organization, User, UserRole, UserStatus


def make_org(db: Session, name: str = "Demo Org") -> Organization:
    org = Organization(name=name)
    db.add(org)
    db.flush()
    return org


def make_user(
    db: Session,
    org: Organization,
    role: UserRole,
    email: str | None = None,
    password_hash: str = "x",
    name: str = "Test User",
) -> User:
    user = User(
        org_id=org.id,
        email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@demo.local",
        password_hash=password_hash,
        role=role,
        status=UserStatus.active,
        name=name,
    )
    db.add(user)
    db.flush()
    return user
```

- [ ] **Step 14: Write the failing model test in `backend/tests/test_models.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import UserRole
from tests.factories import make_org, make_user


def test_can_create_org_and_user(db_session):
    org = make_org(db_session)
    user = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.local")
    assert user.org_id == org.id


def test_email_unique_per_org(db_session):
    org = make_org(db_session)
    make_user(db_session, org, role=UserRole.student, email="dup@demo.local")
    with pytest.raises(IntegrityError):
        make_user(db_session, org, role=UserRole.student, email="dup@demo.local")
        db_session.flush()
```

- [ ] **Step 15: Run the tests**

Run:
```bash
cd backend
pytest tests/test_models.py -v
```
Expected: `2 passed`.

- [ ] **Step 16: Commit**

```bash
git add backend/app/models backend/alembic.ini backend/alembic backend/tests/conftest.py backend/tests/factories.py backend/tests/test_models.py
git commit -m "feat(backend): add organization and user models with alembic + test fixtures"
```

---

## Task 3: Password hashing + JWT helpers

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write `backend/app/auth/__init__.py`**

```python
```

- [ ] **Step 2: Write the failing security tests in `backend/tests/test_security.py`**

```python
from datetime import timedelta

import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed != "hunter2"
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_jwt_roundtrip_carries_claims():
    token = create_access_token({"sub": "user-123", "role": "org_admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "org_admin"


def test_expired_token_rejected():
    token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError):
        decode_access_token(token)
```

- [ ] **Step 3: Run and confirm it fails**

Run: `pytest tests/test_security.py -v`
Expected: ImportError (module missing).

- [ ] **Step 4: Implement `backend/app/auth/security.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(
    claims: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    settings = get_settings()
    to_encode = claims.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expires_minutes)
    )
    to_encode["exp"] = int(expire.timestamp())
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("invalid or expired token") from exc
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_security.py -v`
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth backend/tests/test_security.py
git commit -m "feat(backend): add password hashing and jwt helpers"
```

---

## Task 4: Login endpoint + `/me`

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/auth/deps.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/routers/me.py`
- Modify: `backend/app/main.py` (include routers)
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write `backend/app/schemas/__init__.py`**

```python
```

- [ ] **Step 2: Write `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 3: Write `backend/app/schemas/user.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    role: UserRole
    name: str
```

- [ ] **Step 4: Write `backend/app/auth/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models.user import User, UserStatus

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing subject")

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user
```

- [ ] **Step 5: Write `backend/app/routers/__init__.py`**

```python
```

- [ ] **Step 6: Write `backend/app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, verify_password
from app.database import get_db
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return LoginResponse(access_token=token)
```

- [ ] **Step 7: Write `backend/app/routers/me.py`**

```python
from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current
```

- [ ] **Step 8: Update `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import auth as auth_router
from app.routers import me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 9: Write `backend/tests/test_auth.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin(db, email="admin@demo.local", password="admin123"):
    org = make_org(db)
    user = make_user(
        db, org, role=UserRole.org_admin, email=email, password_hash=hash_password(password)
    )
    db.commit()
    return user


def test_login_success_returns_jwt(client, db_session):
    _seed_admin(db_session)
    resp = client.post("/auth/login", json={"email": "admin@demo.local", "password": "admin123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_rejected(client, db_session):
    _seed_admin(db_session)
    resp = client.post("/auth/login", json={"email": "admin@demo.local", "password": "nope"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, db_session):
    user = _seed_admin(db_session)
    token = client.post(
        "/auth/login", json={"email": "admin@demo.local", "password": "admin123"}
    ).json()["access_token"]
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@demo.local"
    assert body["role"] == "org_admin"
    assert body["id"] == str(user.id)
```

- [ ] **Step 10: Run the tests**

Run: `pytest tests/test_auth.py -v`
Expected: `4 passed`.

> Note: tests use `db_session.commit()` for seed data because they immediately issue HTTP requests through `TestClient`, which opens its own connection. The outer transactional fixture still rolls back at teardown via the bound connection — confirm by re-running the file twice; the second run must still pass.

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas backend/app/auth/deps.py backend/app/routers backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(backend): add login endpoint and /me with jwt"
```

---

## Task 5: Role-based dependencies

**Files:**
- Create: `backend/app/auth/permissions.py`
- Create: `backend/tests/test_role_deps.py`

- [ ] **Step 1: Write the failing test in `backend/tests/test_role_deps.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _login(client, db, role: UserRole, email: str):
    org = make_org(db, name=f"Org-{role.value}")
    make_user(db, org, role=role, email=email, password_hash=hash_password("pw"))
    db.commit()
    return client.post("/auth/login", json={"email": email, "password": "pw"}).json()[
        "access_token"
    ]


def test_admin_only_route_rejects_student(client, db_session):
    token = _login(client, db_session, UserRole.student, "s@demo.local")
    resp = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_only_route_allows_admin(client, db_session):
    token = _login(client, db_session, UserRole.org_admin, "a@demo.local")
    resp = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"pong": "admin"}
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_role_deps.py -v`
Expected: routes don't exist (404).

- [ ] **Step 3: Write `backend/app/auth/permissions.py`**

```python
from collections.abc import Iterable

from fastapi import Depends, HTTPException, status

from app.auth.deps import get_current_user
from app.models.user import User, UserRole


def require_roles(*roles: UserRole):
    allowed: tuple[UserRole, ...] = tuple(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _dep


def require_admin():
    return require_roles(UserRole.org_admin)


def require_staff_or_admin():
    return require_roles(UserRole.org_admin, UserRole.org_staff)


def require_any(roles: Iterable[UserRole]):
    return require_roles(*roles)
```

- [ ] **Step 4: Add a temporary admin-only ping route to verify wiring — modify `backend/app/main.py`**

Replace the body of `main.py` with:

```python
from fastapi import Depends, FastAPI

from app.auth.permissions import require_admin
from app.models.user import User
from app.routers import auth as auth_router
from app.routers import me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/admin/ping")
def admin_ping(_: User = Depends(require_admin())) -> dict[str, str]:
    return {"pong": "admin"}
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_role_deps.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth/permissions.py backend/app/main.py backend/tests/test_role_deps.py
git commit -m "feat(backend): add role-based fastapi dependencies"
```

---

## Task 6: Models — StudentProfile, Package, StudentSubject

**Files:**
- Create: `backend/app/models/package.py`
- Create: `backend/app/models/student.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py` (import new models)
- Create: `backend/tests/test_student_models.py`

- [ ] **Step 1: Write `backend/app/models/package.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Write `backend/app/models/student.py`**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exam_year: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StudentSubject(Base):
    __tablename__ = "student_subjects"
    __table_args__ = (
        UniqueConstraint("student_user_id", "subject_code", name="uq_student_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Update `backend/app/models/__init__.py`**

```python
from app.models.base import Base
from app.models.organization import Organization
from app.models.package import Package
from app.models.student import StudentProfile, StudentSubject
from app.models.user import User, UserRole, UserStatus

__all__ = [
    "Base",
    "Organization",
    "Package",
    "StudentProfile",
    "StudentSubject",
    "User",
    "UserRole",
    "UserStatus",
]
```

- [ ] **Step 4: Update `backend/alembic/env.py` to import new modules**

Add the following imports near the existing model imports:

```python
import app.models.package  # noqa: F401
import app.models.student  # noqa: F401
```

- [ ] **Step 5: Generate and apply the migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "add packages and student profiles"
alembic upgrade head
AITEACHER_DATABASE_URL=postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test alembic upgrade head
```
Expected: both finish without errors.

- [ ] **Step 6: Write `backend/tests/test_student_models.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Package, StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def test_create_package_and_student_profile(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.local")
    pkg = Package(org_id=org.id, name="Standard", subject_codes=["politics", "english"])
    db_session.add(pkg)
    db_session.flush()
    profile = StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id)
    db_session.add(profile)
    db_session.flush()
    assert profile.package_id == pkg.id


def test_student_subject_unique_per_student(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="s2@demo.local")
    db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(StudentSubject(student_user_id=student.id, subject_code="math"))
        db_session.flush()
```

- [ ] **Step 7: Run the tests**

Run: `pytest tests/test_student_models.py -v`
Expected: `2 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models backend/alembic/versions backend/alembic/env.py backend/tests/test_student_models.py
git commit -m "feat(backend): add package, student profile, and subject models"
```

---

## Task 7: Models — StaffStudent + AuditLog

**Files:**
- Create: `backend/app/models/staff_student.py`
- Create: `backend/app/models/audit.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/tests/test_staff_student_model.py`

- [ ] **Step 1: Write `backend/app/models/staff_student.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StaffStudent(Base):
    __tablename__ = "staff_students"
    __table_args__ = (
        UniqueConstraint("staff_user_id", "student_user_id", name="uq_staff_student"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Write `backend/app/models/audit.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Update `backend/app/models/__init__.py`**

```python
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.organization import Organization
from app.models.package import Package
from app.models.staff_student import StaffStudent
from app.models.student import StudentProfile, StudentSubject
from app.models.user import User, UserRole, UserStatus

__all__ = [
    "AuditLog",
    "Base",
    "Organization",
    "Package",
    "StaffStudent",
    "StudentProfile",
    "StudentSubject",
    "User",
    "UserRole",
    "UserStatus",
]
```

- [ ] **Step 4: Update `backend/alembic/env.py` imports**

Add:

```python
import app.models.staff_student  # noqa: F401
import app.models.audit  # noqa: F401
```

- [ ] **Step 5: Generate and apply migration**

Run:
```bash
cd backend
alembic revision --autogenerate -m "add staff_students and audit_logs"
alembic upgrade head
AITEACHER_DATABASE_URL=postgresql+psycopg://aiteacher:aiteacher@localhost:5433/aiteacher_test alembic upgrade head
```
Expected: success.

- [ ] **Step 6: Write `backend/tests/test_staff_student_model.py`**

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import StaffStudent, UserRole
from tests.factories import make_org, make_user


def test_unique_staff_student_pair(db_session):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff, email="t@demo.local")
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.local")
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=student.id))
        db_session.flush()
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_staff_student_model.py -v`
Expected: `1 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models backend/alembic/versions backend/alembic/env.py backend/tests/test_staff_student_model.py
git commit -m "feat(backend): add staff_student and audit_log models"
```

---

## Task 8: Audit service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/tests/test_audit_service.py`

- [ ] **Step 1: Write `backend/app/services/__init__.py`**

```python
```

- [ ] **Step 2: Write the failing test in `backend/tests/test_audit_service.py`**

```python
from sqlalchemy import select

from app.models import AuditLog, UserRole
from app.services.audit import record_audit
from tests.factories import make_org, make_user


def test_record_audit_persists_actor_and_payload(db_session):
    org = make_org(db_session)
    actor = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.local")
    record_audit(
        db_session,
        actor=actor,
        action="student.assign_staff",
        target_type="student",
        target_id="abc-123",
        before=None,
        after={"staff_id": "staff-1"},
    )
    db_session.flush()
    row = db_session.execute(select(AuditLog)).scalar_one()
    assert row.action == "student.assign_staff"
    assert row.actor_user_id == actor.id
    assert row.actor_role == "org_admin"
    assert row.after == {"staff_id": "staff-1"}
    assert row.org_id == org.id
```

- [ ] **Step 3: Run and confirm failure**

Run: `pytest tests/test_audit_service.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `backend/app/services/audit.py`**

```python
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    db: Session,
    *,
    actor: User,
    action: str,
    target_type: str,
    target_id: str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=actor.org_id,
        actor_user_id=actor.id,
        actor_role=actor.role.value,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
    )
    db.add(entry)
    return entry
```

- [ ] **Step 5: Run the test**

Run: `pytest tests/test_audit_service.py -v`
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services backend/tests/test_audit_service.py
git commit -m "feat(backend): add audit service helper"
```

---

## Task 9: Student-scope permission helper

**Files:**
- Modify: `backend/app/auth/permissions.py`
- Create: `backend/tests/test_student_scope.py`

- [ ] **Step 1: Write the failing test in `backend/tests/test_student_scope.py`**

```python
import uuid

import pytest
from fastapi import HTTPException

from app.auth.permissions import assert_can_access_student
from app.models import StaffStudent, UserRole
from tests.factories import make_org, make_user


def test_admin_can_access_any_student_in_same_org(db_session):
    org = make_org(db_session)
    admin = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.local")
    student = make_user(db_session, org, role=UserRole.student, email="s@demo.local")
    assert_can_access_student(db_session, admin, student.id)


def test_admin_cannot_access_student_in_other_org(db_session):
    org_a = make_org(db_session, name="A")
    org_b = make_org(db_session, name="B")
    admin = make_user(db_session, org_a, role=UserRole.org_admin, email="a@demo.local")
    student = make_user(db_session, org_b, role=UserRole.student, email="s@demo.local")
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, admin, student.id)
    assert exc.value.status_code == 403


def test_staff_can_access_assigned_student_only(db_session):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff, email="t@demo.local")
    own = make_user(db_session, org, role=UserRole.student, email="o@demo.local")
    other = make_user(db_session, org, role=UserRole.student, email="x@demo.local")
    db_session.add(StaffStudent(staff_user_id=staff.id, student_user_id=own.id))
    db_session.flush()
    assert_can_access_student(db_session, staff, own.id)
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, staff, other.id)
    assert exc.value.status_code == 403


def test_student_can_access_only_self(db_session):
    org = make_org(db_session)
    student = make_user(db_session, org, role=UserRole.student, email="self@demo.local")
    other = make_user(db_session, org, role=UserRole.student, email="other@demo.local")
    assert_can_access_student(db_session, student, student.id)
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, student, other.id)
    assert exc.value.status_code == 403


def test_missing_student_raises_404(db_session):
    org = make_org(db_session)
    admin = make_user(db_session, org, role=UserRole.org_admin, email="a@demo.local")
    with pytest.raises(HTTPException) as exc:
        assert_can_access_student(db_session, admin, uuid.uuid4())
    assert exc.value.status_code == 404
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_student_scope.py -v`
Expected: ImportError (`assert_can_access_student` missing).

- [ ] **Step 3: Extend `backend/app/auth/permissions.py`**

Append:

```python
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StaffStudent
from app.models.user import User, UserRole


def assert_can_access_student(db: Session, actor: User, student_id: uuid.UUID) -> User:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

    if student.org_id != actor.org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-org access denied")

    if actor.role == UserRole.org_admin:
        return student

    if actor.role == UserRole.student:
        if actor.id == student.id:
            return student
        raise HTTPException(status.HTTP_403_FORBIDDEN, "students may only access themselves")

    if actor.role == UserRole.org_staff:
        linked = db.execute(
            select(StaffStudent).where(
                StaffStudent.staff_user_id == actor.id,
                StaffStudent.student_user_id == student.id,
            )
        ).scalar_one_or_none()
        if linked is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "student not assigned to staff")
        return student

    raise HTTPException(status.HTTP_403_FORBIDDEN, "role cannot access students")
```

> Make sure the new imports do not duplicate existing imports — merge `from fastapi import ...` lines and add `from sqlalchemy import select` once.

- [ ] **Step 4: Run the test**

Run: `pytest tests/test_student_scope.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/permissions.py backend/tests/test_student_scope.py
git commit -m "feat(backend): add student-scope permission helper"
```

---

## Task 10: Admin — create + list students

**Files:**
- Create: `backend/app/schemas/student.py`
- Create: `backend/app/routers/admin_students.py`
- Modify: `backend/app/main.py` (drop ping route, include router)
- Create: `backend/tests/test_admin_students.py`

- [ ] **Step 1: Write `backend/app/schemas/student.py`**

```python
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StudentCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=200)
    exam_year: int = Field(ge=2025, le=2100)
    exam_date: date | None = None


class StudentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    exam_year: int
    exam_date: date | None
    package_id: uuid.UUID | None
```

- [ ] **Step 2: Write the failing test in `backend/tests/test_admin_students.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def _seed_admin(db, email="admin@demo.local", password="admin123"):
    org = make_org(db)
    make_user(db, org, role=UserRole.org_admin, email=email, password_hash=hash_password(password))
    db.commit()
    return org


def test_admin_creates_student(client, db_session):
    _seed_admin(db_session)
    token = _login(client, "admin@demo.local", "admin123")
    resp = client.post(
        "/admin/students",
        json={
            "email": "stu@demo.local",
            "name": "Stu One",
            "password": "stu1234",
            "exam_year": 2027,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "stu@demo.local"
    assert body["exam_year"] == 2027


def test_admin_lists_students_in_own_org(client, db_session):
    org = _seed_admin(db_session)
    other_org = make_org(db_session, name="Other")
    make_user(db_session, other_org, role=UserRole.student, email="x@demo.local")
    db_session.commit()
    token = _login(client, "admin@demo.local", "admin123")
    client.post(
        "/admin/students",
        json={"email": "a@demo.local", "name": "A", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert emails == {"a@demo.local"}


def test_student_cannot_list_students(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.student,
        email="s@demo.local",
        password_hash=hash_password("pw"),
    )
    db_session.commit()
    token = _login(client, "s@demo.local", "pw")
    resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 3: Implement `backend/app/routers/admin_students.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import StudentProfile, User, UserRole
from app.schemas.student import StudentCreate, StudentSummary
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/students", tags=["admin-students"])


@router.post("", response_model=StudentSummary, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StudentSummary:
    existing = db.execute(
        select(User).where(User.org_id == admin.org_id, User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already used in this org")

    user = User(
        org_id=admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.student,
        name=payload.name,
    )
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id, exam_year=payload.exam_year, exam_date=payload.exam_date
    )
    db.add(profile)
    record_audit(
        db,
        actor=admin,
        action="student.create",
        target_type="student",
        target_id=str(user.id),
        after={"email": payload.email, "exam_year": payload.exam_year},
    )
    db.commit()
    db.refresh(profile)

    return StudentSummary(
        id=user.id,
        email=user.email,
        name=user.name,
        exam_year=profile.exam_year,
        exam_date=profile.exam_date,
        package_id=profile.package_id,
    )


@router.get("", response_model=list[StudentSummary])
def list_students(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[StudentSummary]:
    rows = db.execute(
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(User.org_id == admin.org_id, User.role == UserRole.student)
        .order_by(User.name)
    ).all()
    return [
        StudentSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            exam_year=profile.exam_year,
            exam_date=profile.exam_date,
            package_id=profile.package_id,
        )
        for user, profile in rows
    ]
```

- [ ] **Step 4: Remove the temporary ping route — replace `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import admin_students, auth as auth_router, me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Delete `backend/tests/test_role_deps.py`** (the `/admin/ping` route it relied on is gone). Keep the role logic — it's still exercised by the admin endpoints.

```bash
rm backend/tests/test_role_deps.py
```

- [ ] **Step 6: Run the tests**

Run: `pytest tests/test_admin_students.py -v`
Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/student.py backend/app/routers/admin_students.py backend/app/main.py backend/tests/test_admin_students.py
git add -u backend/tests
git commit -m "feat(backend): admin can create and list students in org"
```

---

## Task 11: Admin — manage staff accounts

**Files:**
- Create: `backend/app/schemas/staff.py`
- Create: `backend/app/routers/admin_staff.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_staff.py`

- [ ] **Step 1: Write `backend/app/schemas/staff.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StaffCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=200)


class StaffSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
```

- [ ] **Step 2: Write the failing test in `backend/tests/test_admin_staff.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin(db):
    org = make_org(db)
    make_user(
        db,
        org,
        role=UserRole.org_admin,
        email="a@demo.local",
        password_hash=hash_password("pw1234"),
    )
    db.commit()


def _login(client, email="a@demo.local", password="pw1234"):
    return client.post("/auth/login", json={"email": email, "password": password}).json()[
        "access_token"
    ]


def test_admin_creates_staff(client, db_session):
    _seed_admin(db_session)
    token = _login(client)
    resp = client.post(
        "/admin/staff",
        json={"email": "t@demo.local", "name": "Teacher One", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "t@demo.local"


def test_admin_lists_staff(client, db_session):
    _seed_admin(db_session)
    token = _login(client)
    client.post(
        "/admin/staff",
        json={"email": "t@demo.local", "name": "Teacher One", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.get("/admin/staff", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert "t@demo.local" in emails


def test_staff_cannot_create_staff(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.org_staff,
        email="t@demo.local",
        password_hash=hash_password("pw"),
    )
    db_session.commit()
    token = _login(client, "t@demo.local", "pw")
    resp = client.post(
        "/admin/staff",
        json={"email": "x@demo.local", "name": "X", "password": "pw1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 3: Implement `backend/app/routers/admin_staff.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.auth.security import hash_password
from app.database import get_db
from app.models import User, UserRole
from app.schemas.staff import StaffCreate, StaffSummary
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/staff", tags=["admin-staff"])


@router.post("", response_model=StaffSummary, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffSummary:
    existing = db.execute(
        select(User).where(User.org_id == admin.org_id, User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already used in this org")
    user = User(
        org_id=admin.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.org_staff,
        name=payload.name,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor=admin,
        action="staff.create",
        target_type="staff",
        target_id=str(user.id),
        after={"email": payload.email},
    )
    db.commit()
    db.refresh(user)
    return StaffSummary(id=user.id, email=user.email, name=user.name)


@router.get("", response_model=list[StaffSummary])
def list_staff(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[StaffSummary]:
    rows = db.execute(
        select(User)
        .where(User.org_id == admin.org_id, User.role == UserRole.org_staff)
        .order_by(User.name)
    ).scalars().all()
    return [StaffSummary(id=r.id, email=r.email, name=r.name) for r in rows]
```

- [ ] **Step 4: Update `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import admin_staff, admin_students, auth as auth_router, me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)
app.include_router(admin_staff.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_admin_staff.py -v`
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/staff.py backend/app/routers/admin_staff.py backend/app/main.py backend/tests/test_admin_staff.py
git commit -m "feat(backend): admin can manage staff accounts"
```

---

## Task 12: Admin — packages CRUD + assign package to student

**Files:**
- Create: `backend/app/schemas/package.py`
- Create: `backend/app/routers/admin_packages.py`
- Modify: `backend/app/routers/admin_students.py` (add assign-package endpoint)
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_packages.py`

- [ ] **Step 1: Write `backend/app/schemas/package.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, Field


class PackageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject_codes: list[str] = Field(min_length=1)


class PackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    subject_codes: list[str]


class AssignPackageRequest(BaseModel):
    package_id: uuid.UUID
```

- [ ] **Step 2: Write the failing test in `backend/tests/test_admin_packages.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin(db):
    org = make_org(db)
    make_user(
        db,
        org,
        role=UserRole.org_admin,
        email="a@demo.local",
        password_hash=hash_password("pw1234"),
    )
    db.commit()


def _token(client):
    return client.post(
        "/auth/login", json={"email": "a@demo.local", "password": "pw1234"}
    ).json()["access_token"]


def _create_student(client, token, email="s@demo.local"):
    resp = client.post(
        "/admin/students",
        json={"email": email, "name": "S", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_admin_create_and_list_package(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    resp = client.post(
        "/admin/packages",
        json={"name": "Standard", "subject_codes": ["politics", "english", "math"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    pkg = resp.json()
    assert pkg["subject_codes"] == ["politics", "english", "math"]

    resp = client.get("/admin/packages", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(p["name"] == "Standard" for p in resp.json())


def test_assign_package_creates_subjects(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    pkg = client.post(
        "/admin/packages",
        json={"name": "Std", "subject_codes": ["english", "math"]},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    student_id = _create_student(client, token)
    resp = client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["subject_codes"]) == {"english", "math"}

    list_resp = client.get("/admin/students", headers={"Authorization": f"Bearer {token}"})
    matching = next(s for s in list_resp.json() if s["id"] == student_id)
    assert matching["package_id"] == pkg["id"]


def test_assign_package_idempotent_for_subjects(client, db_session):
    _seed_admin(db_session)
    token = _token(client)
    pkg = client.post(
        "/admin/packages",
        json={"name": "Std", "subject_codes": ["english"]},
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    student_id = _create_student(client, token)
    client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.post(
        f"/admin/students/{student_id}/package",
        json={"package_id": pkg["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["subject_codes"] == ["english"]
```

- [ ] **Step 3: Implement `backend/app/routers/admin_packages.py`**

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.database import get_db
from app.models import Package, User
from app.schemas.package import PackageCreate, PackageOut
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/packages", tags=["admin-packages"])


@router.post("", response_model=PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(
    payload: PackageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> PackageOut:
    pkg = Package(org_id=admin.org_id, name=payload.name, subject_codes=payload.subject_codes)
    db.add(pkg)
    db.flush()
    record_audit(
        db,
        actor=admin,
        action="package.create",
        target_type="package",
        target_id=str(pkg.id),
        after={"name": pkg.name, "subjects": pkg.subject_codes},
    )
    db.commit()
    db.refresh(pkg)
    return PackageOut(id=pkg.id, name=pkg.name, subject_codes=pkg.subject_codes)


@router.get("", response_model=list[PackageOut])
def list_packages(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[PackageOut]:
    rows = db.execute(
        select(Package).where(Package.org_id == admin.org_id).order_by(Package.name)
    ).scalars().all()
    return [PackageOut(id=p.id, name=p.name, subject_codes=p.subject_codes) for p in rows]
```

- [ ] **Step 4: Add assign-package endpoint at the bottom of `backend/app/routers/admin_students.py`**

```python
import uuid

from app.models import Package, StudentSubject
from app.schemas.package import AssignPackageRequest


class StudentDetail(StudentSummary):
    subject_codes: list[str]


@router.post("/{student_id}/package", response_model=StudentDetail)
def assign_package(
    student_id: uuid.UUID,
    payload: AssignPackageRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StudentDetail:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")
    pkg = db.get(Package, payload.package_id)
    if pkg is None or pkg.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "package not found")

    profile = db.get(StudentProfile, student.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile missing")
    profile.package_id = pkg.id

    existing = {
        row.subject_code
        for row in db.execute(
            select(StudentSubject).where(StudentSubject.student_user_id == student.id)
        ).scalars()
    }
    for code in pkg.subject_codes:
        if code not in existing:
            db.add(StudentSubject(student_user_id=student.id, subject_code=code))

    record_audit(
        db,
        actor=admin,
        action="student.assign_package",
        target_type="student",
        target_id=str(student.id),
        after={"package_id": str(pkg.id), "subjects": pkg.subject_codes},
    )
    db.commit()
    db.refresh(profile)

    return StudentDetail(
        id=student.id,
        email=student.email,
        name=student.name,
        exam_year=profile.exam_year,
        exam_date=profile.exam_date,
        package_id=profile.package_id,
        subject_codes=pkg.subject_codes,
    )
```

> Add the imports for `StudentSubject` and `Package` at the top of `admin_students.py` instead of inline, and move `class StudentDetail(...)` to a position after `StudentSummary` import (or define it in `app/schemas/student.py` and import). Final module structure: imports → router → `create_student` → `list_students` → `assign_package`.

- [ ] **Step 5: Update `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import (
    admin_packages,
    admin_staff,
    admin_students,
    auth as auth_router,
    me as me_router,
)

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)
app.include_router(admin_staff.router)
app.include_router(admin_packages.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_admin_packages.py -v`
Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/package.py backend/app/routers/admin_packages.py backend/app/routers/admin_students.py backend/app/main.py backend/tests/test_admin_packages.py
git commit -m "feat(backend): packages crud and assign package to student"
```

---

## Task 13: Admin — assign / unassign staff to a student

**Files:**
- Modify: `backend/app/schemas/staff.py` (add `StaffAssignmentRequest`)
- Modify: `backend/app/routers/admin_students.py` (add assign/unassign endpoints)
- Create: `backend/tests/test_staff_assignment.py`

- [ ] **Step 1: Append to `backend/app/schemas/staff.py`**

```python
class StaffAssignmentRequest(BaseModel):
    staff_user_id: uuid.UUID


class StaffAssignmentOut(BaseModel):
    student_id: uuid.UUID
    staff_user_ids: list[uuid.UUID]
```

Add `import uuid` at the top if not present.

- [ ] **Step 2: Write the failing test in `backend/tests/test_staff_assignment.py`**

```python
from app.auth.security import hash_password
from app.models import UserRole
from tests.factories import make_org, make_user


def _seed_admin_and_staff(db):
    org = make_org(db)
    make_user(
        db,
        org,
        role=UserRole.org_admin,
        email="a@demo.local",
        password_hash=hash_password("pw1234"),
    )
    staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t@demo.local",
        password_hash=hash_password("pw1234"),
        name="Teacher One",
    )
    db.commit()
    return staff


def _token(client, email="a@demo.local"):
    return client.post(
        "/auth/login", json={"email": email, "password": "pw1234"}
    ).json()["access_token"]


def _create_student(client, token, email="s@demo.local"):
    return client.post(
        "/admin/students",
        json={"email": email, "name": "S", "password": "pw1234", "exam_year": 2027},
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]


def test_admin_assigns_staff_to_student(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    resp = client.post(
        f"/admin/students/{student_id}/staff",
        json={"staff_user_id": str(staff.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert str(staff.id) in body["staff_user_ids"]


def test_admin_unassigns_staff(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    client.post(
        f"/admin/students/{student_id}/staff",
        json={"staff_user_id": str(staff.id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = client.delete(
        f"/admin/students/{student_id}/staff/{staff.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["staff_user_ids"] == []


def test_assign_duplicate_is_idempotent(client, db_session):
    staff = _seed_admin_and_staff(db_session)
    token = _token(client)
    student_id = _create_student(client, token)
    for _ in range(2):
        resp = client.post(
            f"/admin/students/{student_id}/staff",
            json={"staff_user_id": str(staff.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
    assert resp.json()["staff_user_ids"].count(str(staff.id)) == 1
```

- [ ] **Step 3: Add endpoints to `backend/app/routers/admin_students.py`**

Append:

```python
from app.models import StaffStudent
from app.schemas.staff import StaffAssignmentOut, StaffAssignmentRequest


@router.post("/{student_id}/staff", response_model=StaffAssignmentOut)
def assign_staff(
    student_id: uuid.UUID,
    payload: StaffAssignmentRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffAssignmentOut:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")
    staff = db.get(User, payload.staff_user_id)
    if staff is None or staff.role != UserRole.org_staff or staff.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "staff not found")

    existing = db.execute(
        select(StaffStudent).where(
            StaffStudent.staff_user_id == staff.id, StaffStudent.student_user_id == student.id
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            StaffStudent(
                staff_user_id=staff.id,
                student_user_id=student.id,
                assigned_by_user_id=admin.id,
            )
        )
        record_audit(
            db,
            actor=admin,
            action="student.assign_staff",
            target_type="student",
            target_id=str(student.id),
            after={"staff_user_id": str(staff.id)},
        )
        db.commit()

    rows = db.execute(
        select(StaffStudent.staff_user_id).where(StaffStudent.student_user_id == student.id)
    ).scalars().all()
    return StaffAssignmentOut(student_id=student.id, staff_user_ids=list(rows))


@router.delete("/{student_id}/staff/{staff_user_id}", response_model=StaffAssignmentOut)
def unassign_staff(
    student_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> StaffAssignmentOut:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student or student.org_id != admin.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "student not found")

    link = db.execute(
        select(StaffStudent).where(
            StaffStudent.staff_user_id == staff_user_id,
            StaffStudent.student_user_id == student.id,
        )
    ).scalar_one_or_none()
    if link is not None:
        db.delete(link)
        record_audit(
            db,
            actor=admin,
            action="student.unassign_staff",
            target_type="student",
            target_id=str(student.id),
            before={"staff_user_id": str(staff_user_id)},
        )
        db.commit()

    rows = db.execute(
        select(StaffStudent.staff_user_id).where(StaffStudent.student_user_id == student.id)
    ).scalars().all()
    return StaffAssignmentOut(student_id=student.id, staff_user_ids=list(rows))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_staff_assignment.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/staff.py backend/app/routers/admin_students.py backend/tests/test_staff_assignment.py
git commit -m "feat(backend): admin assigns and unassigns staff to students"
```

---

## Task 14: Staff — list assigned students

**Files:**
- Create: `backend/app/routers/staff_students.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_staff_students.py`

- [ ] **Step 1: Write the failing test in `backend/tests/test_staff_students.py`**

```python
from app.auth.security import hash_password
from app.models import StaffStudent, StudentProfile, UserRole
from tests.factories import make_org, make_user


def _seed(db):
    org = make_org(db)
    staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t@demo.local",
        password_hash=hash_password("pw1234"),
        name="Teacher",
    )
    other_staff = make_user(
        db,
        org,
        role=UserRole.org_staff,
        email="t2@demo.local",
        password_hash=hash_password("pw1234"),
    )
    mine = make_user(db, org, role=UserRole.student, email="mine@demo.local", name="Mine")
    theirs = make_user(db, org, role=UserRole.student, email="theirs@demo.local", name="Theirs")
    for s in (mine, theirs):
        db.add(StudentProfile(user_id=s.id, exam_year=2027))
    db.add(StaffStudent(staff_user_id=staff.id, student_user_id=mine.id))
    db.add(StaffStudent(staff_user_id=other_staff.id, student_user_id=theirs.id))
    db.commit()


def _token(client, email="t@demo.local"):
    return client.post(
        "/auth/login", json={"email": email, "password": "pw1234"}
    ).json()["access_token"]


def test_staff_sees_only_assigned_students(client, db_session):
    _seed(db_session)
    token = _token(client)
    resp = client.get("/staff/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()}
    assert emails == {"mine@demo.local"}


def test_admin_cannot_use_staff_route(client, db_session):
    _seed(db_session)
    org = make_org(db_session, name="X")  # ensure session has activity
    make_user(
        db_session,
        org,
        role=UserRole.org_admin,
        email="a@demo.local",
        password_hash=hash_password("pw1234"),
    )
    db_session.commit()
    token = _token(client, email="a@demo.local")
    resp = client.get("/staff/students", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Implement `backend/app/routers/staff_students.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import StaffStudent, StudentProfile, User, UserRole
from app.schemas.student import StudentSummary

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/students", response_model=list[StudentSummary])
def my_students(
    db: Session = Depends(get_db),
    staff: User = Depends(require_roles(UserRole.org_staff)),
) -> list[StudentSummary]:
    rows = db.execute(
        select(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .join(StaffStudent, StaffStudent.student_user_id == User.id)
        .where(StaffStudent.staff_user_id == staff.id)
        .order_by(User.name)
    ).all()
    return [
        StudentSummary(
            id=user.id,
            email=user.email,
            name=user.name,
            exam_year=profile.exam_year,
            exam_date=profile.exam_date,
            package_id=profile.package_id,
        )
        for user, profile in rows
    ]
```

- [ ] **Step 3: Update `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import (
    admin_packages,
    admin_staff,
    admin_students,
    auth as auth_router,
    me as me_router,
    staff_students,
)

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)
app.include_router(admin_staff.router)
app.include_router(admin_packages.router)
app.include_router(staff_students.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_staff_students.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/staff_students.py backend/app/main.py backend/tests/test_staff_students.py
git commit -m "feat(backend): staff sees only assigned students"
```

---

## Task 15: Student — `/student/me`

**Files:**
- Create: `backend/app/routers/student_profile.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_student_profile.py`

- [ ] **Step 1: Write the failing test in `backend/tests/test_student_profile.py`**

```python
from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="s@demo.local",
        password_hash=hash_password("pw1234"),
        name="Stu",
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.add(StudentSubject(student_user_id=student.id, subject_code="math"))
    db.commit()
    return student


def test_student_sees_own_profile_and_subjects(client, db_session):
    _seed(db_session)
    token = client.post(
        "/auth/login", json={"email": "s@demo.local", "password": "pw1234"}
    ).json()["access_token"]
    resp = client.get("/student/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "s@demo.local"
    assert body["exam_year"] == 2027
    assert set(body["subject_codes"]) == {"english", "math"}


def test_non_student_role_rejected(client, db_session):
    org = make_org(db_session)
    make_user(
        db_session,
        org,
        role=UserRole.org_admin,
        email="a@demo.local",
        password_hash=hash_password("pw1234"),
    )
    db_session.commit()
    token = client.post(
        "/auth/login", json={"email": "a@demo.local", "password": "pw1234"}
    ).json()["access_token"]
    resp = client.get("/student/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Implement `backend/app/routers/student_profile.py`**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import StudentProfile, StudentSubject, User, UserRole

router = APIRouter(prefix="/student", tags=["student"])


class StudentMeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    exam_year: int
    subject_codes: list[str]


@router.get("/me", response_model=StudentMeOut)
def get_me(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> StudentMeOut:
    profile = db.get(StudentProfile, student.id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "profile missing")
    subjects = db.execute(
        select(StudentSubject.subject_code).where(
            StudentSubject.student_user_id == student.id, StudentSubject.enabled.is_(True)
        )
    ).scalars().all()
    return StudentMeOut(
        id=student.id,
        email=student.email,
        name=student.name,
        exam_year=profile.exam_year,
        subject_codes=list(subjects),
    )
```

- [ ] **Step 3: Update `backend/app/main.py`**

```python
from fastapi import FastAPI

from app.routers import (
    admin_packages,
    admin_staff,
    admin_students,
    auth as auth_router,
    me as me_router,
    staff_students,
    student_profile,
)

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)
app.include_router(admin_staff.router)
app.include_router(admin_packages.router)
app.include_router(staff_students.router)
app.include_router(student_profile.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_student_profile.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Run the whole backend suite**

Run: `pytest -v`
Expected: every test passes (~25 tests across all `test_*.py`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/student_profile.py backend/app/main.py backend/tests/test_student_profile.py
git commit -m "feat(backend): student /me endpoint with subjects"
```

---

## Task 16: Seed script + CORS

**Files:**
- Modify: `backend/app/main.py` (CORS middleware)
- Create: `backend/app/seed.py`
- Modify: `backend/README.md`

- [ ] **Step 1: Add CORS middleware in `backend/app/main.py`**

Insert after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Write `backend/app/seed.py`**

```python
"""Seed the dev database with a demo org, admin, staff, package and student."""
from __future__ import annotations

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models import (
    Organization,
    Package,
    StaffStudent,
    StudentProfile,
    StudentSubject,
    User,
    UserRole,
)


def main() -> None:
    db = SessionLocal()
    try:
        org = db.execute(select(Organization).where(Organization.name == "Demo Org")).scalar_one_or_none()
        if org is None:
            org = Organization(name="Demo Org")
            db.add(org)
            db.flush()

        def ensure_user(email: str, role: UserRole, name: str, password: str) -> User:
            existing = db.execute(
                select(User).where(User.org_id == org.id, User.email == email)
            ).scalar_one_or_none()
            if existing:
                return existing
            user = User(
                org_id=org.id,
                email=email,
                password_hash=hash_password(password),
                role=role,
                name=name,
            )
            db.add(user)
            db.flush()
            return user

        admin = ensure_user("admin@demo.local", UserRole.org_admin, "Admin", "admin123")
        staff = ensure_user("teacher@demo.local", UserRole.org_staff, "Teacher", "teach123")
        student = ensure_user("student@demo.local", UserRole.student, "Student", "stud123")

        pkg = db.execute(select(Package).where(Package.org_id == org.id, Package.name == "Standard")).scalar_one_or_none()
        if pkg is None:
            pkg = Package(
                org_id=org.id, name="Standard", subject_codes=["politics", "english", "math"]
            )
            db.add(pkg)
            db.flush()

        if db.get(StudentProfile, student.id) is None:
            db.add(StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id))

        for code in pkg.subject_codes:
            exists = db.execute(
                select(StudentSubject).where(
                    StudentSubject.student_user_id == student.id,
                    StudentSubject.subject_code == code,
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(StudentSubject(student_user_id=student.id, subject_code=code))

        link = db.execute(
            select(StaffStudent).where(
                StaffStudent.staff_user_id == staff.id,
                StaffStudent.student_user_id == student.id,
            )
        ).scalar_one_or_none()
        if link is None:
            db.add(
                StaffStudent(
                    staff_user_id=staff.id,
                    student_user_id=student.id,
                    assigned_by_user_id=admin.id,
                )
            )

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Update `backend/README.md`**

```markdown
# backend

FastAPI service for AITeacher.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## DB

```bash
docker compose -f ../docker-compose.yml up -d
alembic upgrade head
python -m app.seed
```

Seed creates:

- `admin@demo.local` / `admin123` (org_admin)
- `teacher@demo.local` / `teach123` (org_staff, owns the student)
- `student@demo.local` / `stud123` (student in "Standard" package)

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## Test

```bash
pytest -v
```
```

- [ ] **Step 4: Run the seed against the dev database**

Run:
```bash
cd backend
alembic upgrade head
python -m app.seed
```
Expected: `Seed complete.`

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/seed.py backend/README.md
git commit -m "feat(backend): cors + seed script for demo accounts"
```

---

## Task 17: Frontend scaffold (Vite + React + Tailwind + Router + TanStack Query)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/README.md`

- [ ] **Step 1: Write `frontend/package.json`**

```json
{
  "name": "aiteacher-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.32.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.3"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.2",
    "@testing-library/react": "^15.0.0",
    "@types/react": "^18.2.66",
    "@types/react-dom": "^18.2.22",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.18",
    "jsdom": "^24.0.0",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.4.5",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

- [ ] **Step 2: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Write `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Write `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
```

- [ ] **Step 5: Write `frontend/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 6: Write `frontend/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 7: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AITeacher</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Write `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root {
  height: 100%;
}
```

- [ ] **Step 9: Write `frontend/src/App.tsx`**

```tsx
export default function App() {
  return (
    <div className="p-6 text-slate-700">
      <h1 className="text-2xl font-semibold">AITeacher</h1>
      <p>Scaffold ready.</p>
    </div>
  );
}
```

- [ ] **Step 10: Write `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 11: Write `frontend/tests/setup.ts`**

```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 12: Write `frontend/README.md`**

```markdown
# frontend

React + Vite UI for AITeacher.

```bash
npm install
npm run dev   # http://localhost:5173 (proxies /api -> http://localhost:8000)
npm test      # vitest
```
```

- [ ] **Step 13: Install and verify dev server boots**

Run:
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173 &
sleep 4
curl -s http://127.0.0.1:5173 | head -n 5
kill %1
```
Expected: HTML containing `<div id="root">`.

- [ ] **Step 14: Commit**

```bash
git add frontend
git commit -m "chore(frontend): scaffold vite react tailwind tanstack-query"
```

---

## Task 18: Frontend — API client + AuthContext + Login page

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/tests/Login.test.tsx`

- [ ] **Step 1: Write `frontend/src/api/client.ts`**

```ts
const API_BASE = "/api";

let currentToken: string | null = null;

export function setToken(token: string | null) {
  currentToken = token;
  if (token) localStorage.setItem("aiteacher_token", token);
  else localStorage.removeItem("aiteacher_token");
}

export function loadToken(): string | null {
  if (currentToken) return currentToken;
  currentToken = localStorage.getItem("aiteacher_token");
  return currentToken;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = loadToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
```

- [ ] **Step 2: Write `frontend/src/api/auth.ts`**

```ts
import { api } from "./client";

export type LoginRequest = { email: string; password: string };
export type LoginResponse = { access_token: string; token_type: string };

export type Me = {
  id: string;
  org_id: string;
  email: string;
  role: "student" | "org_staff" | "org_admin";
  name: string;
};

export function login(body: LoginRequest) {
  return api<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchMe() {
  return api<Me>("/me");
}
```

- [ ] **Step 3: Write `frontend/src/auth/AuthContext.tsx`**

```tsx
import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { fetchMe, login as apiLogin, Me } from "@/api/auth";
import { loadToken, setToken } from "@/api/client";

type AuthState =
  | { status: "loading" }
  | { status: "anon" }
  | { status: "authed"; me: Me };

type Ctx = {
  state: AuthState;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
};

const AuthCtx = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    const token = loadToken();
    if (!token) {
      setState({ status: "anon" });
      return;
    }
    fetchMe()
      .then((me) => setState({ status: "authed", me }))
      .catch(() => {
        setToken(null);
        setState({ status: "anon" });
      });
  }, []);

  const login = async (email: string, password: string) => {
    const { access_token } = await apiLogin({ email, password });
    setToken(access_token);
    const me = await fetchMe();
    setState({ status: "authed", me });
    return me;
  };

  const logout = () => {
    setToken(null);
    setState({ status: "anon" });
  };

  return <AuthCtx.Provider value={{ state, login, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth(): Ctx {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Write `frontend/src/pages/Login.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

const ROLE_HOME: Record<string, string> = {
  org_admin: "/admin/students",
  org_staff: "/staff/students",
  student: "/student/workspace",
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(email, password);
      navigate(ROLE_HOME[me.role] ?? "/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-8 w-full max-w-sm">
        <h1 className="text-2xl font-semibold mb-6">AITeacher 登录</h1>
        <label className="block mb-3">
          <span className="text-sm text-slate-600">邮箱</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        <label className="block mb-4">
          <span className="text-sm text-slate-600">密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        {error && <p role="alert" className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-slate-900 text-white py-2 rounded disabled:opacity-50"
        >
          {busy ? "登录中…" : "登录"}
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 5: Replace `frontend/src/App.tsx`**

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 6: Update `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 7: Write `frontend/tests/Login.test.tsx`**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Login from "../src/pages/Login";
import { AuthProvider } from "../src/auth/AuthContext";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function mockFetch(responses: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.url;
      const match = Object.entries(responses).find(([key]) => url.endsWith(key));
      if (!match) throw new Error(`no mock for ${url}`);
      const [, { status, body }] = match;
      return new Response(JSON.stringify(body), { status });
    }),
  );
}

function renderLogin(initial = "/login") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/admin/students" element={<div>admin home</div>} />
          <Route path="/staff/students" element={<div>staff home</div>} />
          <Route path="/student/workspace" element={<div>student home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Login", () => {
  it("redirects admin to /admin/students after login", async () => {
    mockFetch({
      "/auth/login": { status: 200, body: { access_token: "t", token_type: "bearer" } },
      "/me": { status: 200, body: { id: "1", org_id: "o", email: "a@d", role: "org_admin", name: "A" } },
    });
    renderLogin();
    fireEvent.change(screen.getByLabelText(/邮箱/), { target: { value: "a@d" } });
    fireEvent.change(screen.getByLabelText(/密码/), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => screen.getByText("admin home"));
  });

  it("shows error on 401", async () => {
    mockFetch({
      "/auth/login": { status: 401, body: { detail: "invalid credentials" } },
    });
    renderLogin();
    fireEvent.change(screen.getByLabelText(/邮箱/), { target: { value: "a@d" } });
    fireEvent.change(screen.getByLabelText(/密码/), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/invalid credentials/));
  });
});
```

- [ ] **Step 8: Run tests**

Run: `npm test -- --run`
Expected: `2 passed`.

- [ ] **Step 9: Commit**

```bash
git add frontend/src frontend/tests
git commit -m "feat(frontend): api client, auth context, and login page"
```

---

## Task 19: Frontend — ProtectedRoute + role-based redirects + Layout

**Files:**
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Create: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/tests/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write `frontend/src/components/ProtectedRoute.tsx`**

```tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Me } from "@/api/auth";

type Props = {
  allow: Me["role"][];
  children: ReactNode;
};

export default function ProtectedRoute({ allow, children }: Props) {
  const { state } = useAuth();
  if (state.status === "loading") {
    return <div className="p-6 text-slate-500">加载中…</div>;
  }
  if (state.status === "anon") {
    return <Navigate to="/login" replace />;
  }
  if (!allow.includes(state.me.role)) {
    return <Navigate to="/forbidden" replace />;
  }
  return <>{children}</>;
}
```

- [ ] **Step 2: Write `frontend/src/components/Layout.tsx`**

```tsx
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

type NavItem = { to: string; label: string };

const NAV_BY_ROLE: Record<string, NavItem[]> = {
  org_admin: [
    { to: "/admin/students", label: "学员" },
    { to: "/admin/staff", label: "员工" },
    { to: "/admin/packages", label: "套餐" },
  ],
  org_staff: [{ to: "/staff/students", label: "我的学员" }],
  student: [
    { to: "/student/workspace", label: "今日计划" },
    { to: "/student/workspace/plan", label: "总计划" },
    { to: "/student/workspace/wrong", label: "错题集" },
    { to: "/student/workspace/papers", label: "试卷中心" },
    { to: "/student/workspace/report", label: "学情报告" },
  ],
};

export default function Layout() {
  const { state, logout } = useAuth();
  if (state.status !== "authed") return null;
  const items = NAV_BY_ROLE[state.me.role] ?? [];

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-slate-900 text-slate-100 p-4 flex flex-col">
        <div className="text-lg font-semibold mb-6">AITeacher</div>
        <nav className="flex-1 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `block px-3 py-2 rounded ${
                  isActive ? "bg-slate-700" : "hover:bg-slate-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="text-sm text-slate-400">
          <div>{state.me.name}</div>
          <button onClick={logout} className="mt-2 underline">
            退出
          </button>
        </div>
      </aside>
      <main className="flex-1 bg-slate-50 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/App.tsx`**

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forbidden" element={<div className="p-6">无权访问</div>} />

      <Route
        element={
          <ProtectedRoute allow={["org_admin"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/admin/students" element={<div>admin students placeholder</div>} />
        <Route path="/admin/staff" element={<div>admin staff placeholder</div>} />
        <Route path="/admin/packages" element={<div>admin packages placeholder</div>} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["org_staff"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/staff/students" element={<div>staff students placeholder</div>} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["student"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/student/workspace/*" element={<div>student workspace placeholder</div>} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 4: Write `frontend/tests/ProtectedRoute.test.tsx`**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "../src/components/ProtectedRoute";
import { AuthProvider } from "../src/auth/AuthContext";

function mockFetchMe(role: string) {
  localStorage.setItem("aiteacher_token", "tok");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(
        JSON.stringify({ id: "1", org_id: "o", email: "x", role, name: "x" }),
        { status: 200 },
      ),
    ),
  );
}

function renderWith(allow: string[]) {
  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/secret"
            element={
              <ProtectedRoute allow={allow as any}>
                <div>secret content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>login page</div>} />
          <Route path="/forbidden" element={<div>forbidden page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("ProtectedRoute", () => {
  it("renders content when role is allowed", async () => {
    mockFetchMe("org_admin");
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("secret content"));
  });

  it("redirects to /forbidden when role mismatched", async () => {
    mockFetchMe("student");
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("forbidden page"));
  });

  it("redirects anonymous to /login", async () => {
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("login page"));
  });
});
```

- [ ] **Step 5: Run tests**

Run: `npm test -- --run`
Expected: `5 passed` (Login 2 + ProtectedRoute 3).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components frontend/src/App.tsx frontend/tests/ProtectedRoute.test.tsx
git commit -m "feat(frontend): protected route and role-based layout shell"
```

---

## Task 20: Frontend — Admin students list page

**Files:**
- Create: `frontend/src/api/students.ts`
- Create: `frontend/src/pages/admin/StudentsList.tsx`
- Modify: `frontend/src/App.tsx` (mount real page)

- [ ] **Step 1: Write `frontend/src/api/students.ts`**

```ts
import { api } from "./client";

export type Student = {
  id: string;
  email: string;
  name: string;
  exam_year: number;
  exam_date: string | null;
  package_id: string | null;
};

export type CreateStudentBody = {
  email: string;
  name: string;
  password: string;
  exam_year: number;
};

export function listStudents() {
  return api<Student[]>("/admin/students");
}

export function createStudent(body: CreateStudentBody) {
  return api<Student>("/admin/students", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 2: Write `frontend/src/pages/admin/StudentsList.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createStudent, listStudents, Student } from "@/api/students";

export default function StudentsList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<Student[]>({
    queryKey: ["admin", "students"],
    queryFn: listStudents,
  });

  const createMut = useMutation({
    mutationFn: createStudent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "students"] }),
  });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [examYear, setExamYear] = useState(new Date().getFullYear() + 1);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMut.mutate(
      { email, name, password, exam_year: examYear },
      {
        onSuccess: () => {
          setEmail("");
          setName("");
          setPassword("");
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-xl font-semibold">学员</h1>

      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 grid grid-cols-2 gap-3">
        <input
          className="border rounded px-3 py-2"
          placeholder="姓名"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="email"
          placeholder="邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="password"
          placeholder="初始密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="number"
          placeholder="考试年份"
          value={examYear}
          onChange={(e) => setExamYear(Number(e.target.value))}
          required
        />
        <button
          type="submit"
          disabled={createMut.isPending}
          className="col-span-2 bg-slate-900 text-white rounded py-2 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增学员"}
        </button>
        {createMut.error && (
          <p role="alert" className="col-span-2 text-red-600 text-sm">
            {(createMut.error as Error).message}
          </p>
        )}
      </form>

      <section className="bg-white shadow rounded">
        {isLoading && <p className="p-4 text-slate-500">加载中…</p>}
        {error && <p className="p-4 text-red-600">{(error as Error).message}</p>}
        {data && (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">姓名</th>
                <th className="px-4 py-2">邮箱</th>
                <th className="px-4 py-2">考试年份</th>
                <th className="px-4 py-2">套餐</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2">{s.email}</td>
                  <td className="px-4 py-2">{s.exam_year}</td>
                  <td className="px-4 py-2 text-slate-500">{s.package_id ?? "—"}</td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                    暂无学员
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/App.tsx`**

Replace the admin students placeholder:

```tsx
<Route path="/admin/students" element={<StudentsList />} />
```

And add the import at the top:

```tsx
import StudentsList from "@/pages/admin/StudentsList";
```

- [ ] **Step 4: Smoke-build to confirm types**

Run:
```bash
cd frontend
npm run build
```
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/students.ts frontend/src/pages/admin/StudentsList.tsx frontend/src/App.tsx
git commit -m "feat(frontend): admin students list and create form"
```

---

## Task 21: Frontend — Admin staff management page

**Files:**
- Create: `frontend/src/api/staff.ts`
- Create: `frontend/src/pages/admin/StaffList.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/api/staff.ts`**

```ts
import { api } from "./client";

export type Staff = { id: string; email: string; name: string };

export type CreateStaffBody = { email: string; name: string; password: string };

export function listStaff() {
  return api<Staff[]>("/admin/staff");
}

export function createStaff(body: CreateStaffBody) {
  return api<Staff>("/admin/staff", { method: "POST", body: JSON.stringify(body) });
}

export function assignStaff(studentId: string, staffUserId: string) {
  return api<{ student_id: string; staff_user_ids: string[] }>(
    `/admin/students/${studentId}/staff`,
    { method: "POST", body: JSON.stringify({ staff_user_id: staffUserId }) },
  );
}

export function unassignStaff(studentId: string, staffUserId: string) {
  return api<{ student_id: string; staff_user_ids: string[] }>(
    `/admin/students/${studentId}/staff/${staffUserId}`,
    { method: "DELETE" },
  );
}
```

- [ ] **Step 2: Write `frontend/src/pages/admin/StaffList.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createStaff, listStaff } from "@/api/staff";

export default function StaffList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "staff"],
    queryFn: listStaff,
  });
  const createMut = useMutation({
    mutationFn: createStaff,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "staff"] }),
  });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMut.mutate(
      { email, name, password },
      {
        onSuccess: () => {
          setEmail("");
          setName("");
          setPassword("");
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">员工</h1>
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 grid grid-cols-2 gap-3">
        <input
          className="border rounded px-3 py-2"
          placeholder="姓名"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="email"
          placeholder="邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2 col-span-2"
          type="password"
          placeholder="初始密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button
          type="submit"
          disabled={createMut.isPending}
          className="col-span-2 bg-slate-900 text-white rounded py-2 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增员工"}
        </button>
        {createMut.error && (
          <p role="alert" className="col-span-2 text-red-600 text-sm">
            {(createMut.error as Error).message}
          </p>
        )}
      </form>

      <section className="bg-white shadow rounded">
        {isLoading && <p className="p-4 text-slate-500">加载中…</p>}
        {error && <p className="p-4 text-red-600">{(error as Error).message}</p>}
        {data && (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">姓名</th>
                <th className="px-4 py-2">邮箱</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2">{s.email}</td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-6 text-center text-slate-500">
                    暂无员工
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/App.tsx`**

```tsx
import StaffList from "@/pages/admin/StaffList";
```

Replace placeholder:

```tsx
<Route path="/admin/staff" element={<StaffList />} />
```

- [ ] **Step 4: Build to verify**

Run: `npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/staff.ts frontend/src/pages/admin/StaffList.tsx frontend/src/App.tsx
git commit -m "feat(frontend): admin staff list and create form"
```

---

## Task 22: Frontend — Admin packages page (+ assign to student)

**Files:**
- Create: `frontend/src/api/packages.ts`
- Create: `frontend/src/pages/admin/PackagesList.tsx`
- Modify: `frontend/src/pages/admin/StudentsList.tsx` (add assign-package action)
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/api/packages.ts`**

```ts
import { api } from "./client";

export type Package = { id: string; name: string; subject_codes: string[] };

export function listPackages() {
  return api<Package[]>("/admin/packages");
}

export function createPackage(body: { name: string; subject_codes: string[] }) {
  return api<Package>("/admin/packages", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function assignPackage(studentId: string, packageId: string) {
  return api<{ subject_codes: string[] }>(`/admin/students/${studentId}/package`, {
    method: "POST",
    body: JSON.stringify({ package_id: packageId }),
  });
}
```

- [ ] **Step 2: Write `frontend/src/pages/admin/PackagesList.tsx`**

```tsx
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPackage, listPackages } from "@/api/packages";

const SUBJECT_OPTIONS = [
  { code: "politics", label: "政治" },
  { code: "english", label: "英语" },
  { code: "math", label: "数学" },
];

export default function PackagesList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "packages"],
    queryFn: listPackages,
  });
  const createMut = useMutation({
    mutationFn: createPackage,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "packages"] }),
  });

  const [name, setName] = useState("");
  const [subjects, setSubjects] = useState<string[]>([]);

  const toggle = (code: string) =>
    setSubjects((curr) =>
      curr.includes(code) ? curr.filter((c) => c !== code) : [...curr, code],
    );

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (subjects.length === 0) return;
    createMut.mutate(
      { name, subject_codes: subjects },
      {
        onSuccess: () => {
          setName("");
          setSubjects([]);
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">套餐</h1>
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 space-y-3">
        <input
          className="border rounded px-3 py-2 w-full"
          placeholder="套餐名"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <div className="flex gap-3 flex-wrap">
          {SUBJECT_OPTIONS.map((opt) => (
            <label key={opt.code} className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={subjects.includes(opt.code)}
                onChange={() => toggle(opt.code)}
              />
              {opt.label}
            </label>
          ))}
        </div>
        <button
          type="submit"
          disabled={createMut.isPending || subjects.length === 0}
          className="bg-slate-900 text-white rounded py-2 px-4 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增套餐"}
        </button>
        {createMut.error && (
          <p role="alert" className="text-red-600 text-sm">
            {(createMut.error as Error).message}
          </p>
        )}
      </form>

      <section className="bg-white shadow rounded">
        {isLoading && <p className="p-4 text-slate-500">加载中…</p>}
        {error && <p className="p-4 text-red-600">{(error as Error).message}</p>}
        {data && (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">名称</th>
                <th className="px-4 py-2">科目</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2">{p.subject_codes.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Extend `StudentsList.tsx` with an assign-package row action**

At the top of the file:

```tsx
import { assignPackage, listPackages } from "@/api/packages";
```

Inside the component (after the existing queries), add:

```tsx
const { data: packages } = useQuery({
  queryKey: ["admin", "packages"],
  queryFn: listPackages,
});

const assignMut = useMutation({
  mutationFn: ({ studentId, packageId }: { studentId: string; packageId: string }) =>
    assignPackage(studentId, packageId),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "students"] }),
});
```

Replace the package cell rendering in the table row with:

```tsx
<td className="px-4 py-2">
  <select
    className="border rounded px-2 py-1 text-sm"
    value={s.package_id ?? ""}
    onChange={(e) => assignMut.mutate({ studentId: s.id, packageId: e.target.value })}
    disabled={!packages || packages.length === 0}
  >
    <option value="" disabled>
      未分配
    </option>
    {packages?.map((p) => (
      <option key={p.id} value={p.id}>
        {p.name}
      </option>
    ))}
  </select>
</td>
```

- [ ] **Step 4: Update `frontend/src/App.tsx`**

```tsx
import PackagesList from "@/pages/admin/PackagesList";
```

Replace placeholder:

```tsx
<Route path="/admin/packages" element={<PackagesList />} />
```

- [ ] **Step 5: Build to verify**

Run: `npm run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/packages.ts frontend/src/pages/admin/PackagesList.tsx frontend/src/pages/admin/StudentsList.tsx frontend/src/App.tsx
git commit -m "feat(frontend): admin packages page and assign to student"
```

---

## Task 23: Frontend — Staff "My Students" page

**Files:**
- Modify: `frontend/src/api/students.ts` (add `listMyStudents`)
- Create: `frontend/src/pages/staff/MyStudents.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add to `frontend/src/api/students.ts`**

```ts
export function listMyStudents() {
  return api<Student[]>("/staff/students");
}
```

- [ ] **Step 2: Write `frontend/src/pages/staff/MyStudents.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { listMyStudents, Student } from "@/api/students";

export default function MyStudents() {
  const { data, isLoading, error } = useQuery<Student[]>({
    queryKey: ["staff", "students"],
    queryFn: listMyStudents,
  });

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-xl font-semibold">我的学员</h1>
      {isLoading && <p className="text-slate-500">加载中…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {data && (
        <table className="w-full text-sm bg-white shadow rounded">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="px-4 py-2">姓名</th>
              <th className="px-4 py-2">邮箱</th>
              <th className="px-4 py-2">考试年份</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id} className="border-t">
                <td className="px-4 py-2">{s.name}</td>
                <td className="px-4 py-2">{s.email}</td>
                <td className="px-4 py-2">{s.exam_year}</td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-slate-500">
                  暂无分配学员
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/App.tsx`**

```tsx
import MyStudents from "@/pages/staff/MyStudents";
```

Replace placeholder:

```tsx
<Route path="/staff/students" element={<MyStudents />} />
```

- [ ] **Step 4: Build**

Run: `npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/students.ts frontend/src/pages/staff/MyStudents.tsx frontend/src/App.tsx
git commit -m "feat(frontend): staff my-students page"
```

---

## Task 24: Frontend — Student workspace shell

**Files:**
- Create: `frontend/src/api/me.ts`
- Create: `frontend/src/pages/student/Workspace.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write `frontend/src/api/me.ts`**

```ts
import { api } from "./client";

export type StudentMe = {
  id: string;
  email: string;
  name: string;
  exam_year: number;
  subject_codes: string[];
};

export function fetchStudentMe() {
  return api<StudentMe>("/student/me");
}
```

- [ ] **Step 2: Write `frontend/src/pages/student/Workspace.tsx`**

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStudentMe } from "@/api/me";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function Workspace() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["student", "me"],
    queryFn: fetchStudentMe,
  });

  const [activeSubject, setActiveSubject] = useState<string | null>(null);

  if (isLoading) return <p className="text-slate-500">加载中…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  const current = activeSubject ?? data.subject_codes[0] ?? null;

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-7 bg-white shadow rounded p-6 space-y-4">
        <header className="flex justify-between items-baseline">
          <h1 className="text-xl font-semibold">今日计划</h1>
          <div className="text-sm text-slate-500">考试年份：{data.exam_year}</div>
        </header>
        <div className="flex gap-2 flex-wrap">
          {data.subject_codes.map((code) => (
            <button
              key={code}
              onClick={() => setActiveSubject(code)}
              className={`px-3 py-1 rounded border text-sm ${
                current === code
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-300"
              }`}
            >
              {SUBJECT_LABELS[code] ?? code}
            </button>
          ))}
          {data.subject_codes.length === 0 && (
            <p className="text-slate-500 text-sm">尚未开通科目，请联系管理员</p>
          )}
        </div>
        <p className="text-slate-500 text-sm">
          {current
            ? `${SUBJECT_LABELS[current] ?? current} 暂无今日任务（P3 将启用）。`
            : "暂无今日任务。"}
        </p>
      </div>
      <aside className="col-span-5 bg-white shadow rounded p-6">
        <h2 className="font-semibold mb-3">
          {current ? `${SUBJECT_LABELS[current] ?? current} AI 老师` : "AI 老师"}
        </h2>
        <p className="text-slate-500 text-sm">对话功能将在 P2 接入。</p>
      </aside>
    </div>
  );
}
```

- [ ] **Step 3: Update `frontend/src/App.tsx`**

```tsx
import Workspace from "@/pages/student/Workspace";
```

Replace placeholder:

```tsx
<Route path="/student/workspace/*" element={<Workspace />} />
```

- [ ] **Step 4: Build**

Run: `npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/me.ts frontend/src/pages/student/Workspace.tsx frontend/src/App.tsx
git commit -m "feat(frontend): student workspace shell with subject switcher"
```

---

## Task 25: End-to-end smoke verification

**Files:**
- Modify: `README.md` (record verification steps)

- [ ] **Step 1: Start backend and frontend in separate shells**

Backend:
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm run dev
```

- [ ] **Step 2: Run backend test suite once more**

Run: `cd backend && pytest -v`
Expected: all tests pass.

- [ ] **Step 3: Run frontend test suite once more**

Run: `cd frontend && npm test -- --run`
Expected: all tests pass.

- [ ] **Step 4: Manual smoke flow**

In a browser, hit http://localhost:5173 and verify:

1. Login as `admin@demo.local` / `admin123` → lands on `/admin/students`, sees seeded student. Can create a new student. Can navigate to `/admin/staff` and `/admin/packages`.
2. Logout. Login as `teacher@demo.local` / `teach123` → lands on `/staff/students`, sees the seeded student only (no admin nav items).
3. Logout. Login as `student@demo.local` / `stud123` → lands on `/student/workspace`, sees subject chips for `politics / english / math`.

- [ ] **Step 5: Append a verification note to root `README.md`**

Add at the end:

```markdown
## P1 verification

After `python -m app.seed`:

- admin@demo.local / admin123 → `/admin/students`
- teacher@demo.local / teach123 → `/staff/students`
- student@demo.local / stud123 → `/student/workspace`
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: record p1 smoke verification flow"
```

---

## Done with P1

The repo now has:

- Postgres-backed FastAPI with versioned schema, transactional tests, and role-aware endpoints for admin / staff / student.
- JWT auth, password hashing, audit logging, and a `StaffStudent` permission helper used in every cross-student check.
- React workspace with role-based routing: admin manages students/staff/packages, staff sees only their students, students see a workspace shell with their subjects.
- Seed script and verification flow that produce three demo accounts.

The next plan (P2) layers the model gateway, agent orchestration skeleton, and the right-pane chat experience on top of these foundations.
