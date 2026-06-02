import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import Base

os.environ["AITEACHER_DATABASE_URL"] = get_settings().test_database_url
test_engine = create_engine(get_settings().test_database_url, future=True)
TestSession = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    future=True,
    join_transaction_mode="create_savepoint",
)


def _sync_test_schema(connection) -> None:
    """create_all does not add columns to existing tables; patch drift for tests."""
    Base.metadata.create_all(bind=connection)
    insp = inspect(connection)
    if "master_plans" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("master_plans")}
        if "pending_version_id" not in cols:
            connection.execute(
                text(
                    "ALTER TABLE master_plans "
                    "ADD COLUMN pending_version_id UUID NULL "
                    "REFERENCES master_plan_versions(id) ON DELETE SET NULL"
                )
            )
    if "wrong_book_items" in insp.get_table_names():
        wb_cols = {c["name"] for c in insp.get_columns("wrong_book_items")}
        for col, ddl in (
            ("status", "VARCHAR(40) NOT NULL DEFAULT 'active'"),
            ("wrong_count", "INTEGER NOT NULL DEFAULT 1"),
            ("consecutive_correct_count", "INTEGER NOT NULL DEFAULT 0"),
            ("first_correct_at", "TIMESTAMP WITH TIME ZONE"),
            ("last_practice_at", "TIMESTAMP WITH TIME ZONE"),
            ("mastered_at", "TIMESTAMP WITH TIME ZONE"),
        ):
            if col not in wb_cols:
                connection.execute(text(f"ALTER TABLE wrong_book_items ADD COLUMN {col} {ddl}"))


@pytest.fixture
def db_session() -> Session:
    connection = test_engine.connect()
    transaction = connection.begin()
    _sync_test_schema(connection)
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
