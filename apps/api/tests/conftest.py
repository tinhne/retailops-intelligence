"""Shared test fixtures.

Unit tests need nothing external. Integration tests (marked ``integration``) run against a real
PostgreSQL database given by TEST_DATABASE_URL (default: the docker compose ``retailops_test`` DB).
The schema is built with Alembic, so migrations are exercised on every run.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://retailops:retailops@localhost:54329/retailops_test",
)
API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "test",
        "database_url": TEST_DATABASE_URL,
        "log_level": "WARNING",
        "demo_mode_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"PostgreSQL not reachable at TEST_DATABASE_URL: {exc}")
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(API_ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(API_ROOT, "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    yield factory
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(session_factory: sessionmaker[Session], settings: Settings) -> FastAPI:
    application = create_app(settings)

    def _get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _get_db
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
