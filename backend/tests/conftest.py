import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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


@pytest.fixture
def db_session() -> Session:
    connection = test_engine.connect()
    transaction = connection.begin()
    # Ensure newly-added tables exist in test DB.
    Base.metadata.create_all(bind=connection)
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
