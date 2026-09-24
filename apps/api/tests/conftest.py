import os
from collections.abc import Iterator

# Tests run learner-code paths through the trusted subprocess backend; the sandbox suite
# (tests/test_sandbox_docker.py) exercises the real Docker boundary.
os.environ["ENVIRONMENT"] = "test"
os.environ["EXECUTION_BACKEND"] = "trusted-subprocess"
os.environ["LLM_PROVIDER"] = "offline"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.models import Base
from app.seed import seed_database


def isolated_engine() -> Engine:
    """In-memory SQLite by default; set TEST_DATABASE_URL to run the suite on PostgreSQL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        return engine
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def unseeded_engine() -> Iterator[Engine]:
    engine = isolated_engine()
    yield engine
    engine.dispose()


@pytest.fixture
def seeded_engine() -> Iterator[Engine]:
    engine = isolated_engine()
    with Session(engine) as session:
        seed_database(session)
    yield engine
    engine.dispose()


@pytest.fixture
def client(seeded_engine: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(lambda: seeded_engine)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Iterator[None]:
    from app.config import get_settings
    from app.execution.service import rate_limiter

    get_settings.cache_clear()
    rate_limiter.reset()
    yield
    get_settings.cache_clear()


@pytest.fixture
def run_jobs(seeded_engine: Engine):  # type: ignore[no-untyped-def]
    """Process queued executions with interview hooks, like the worker does."""
    from sqlalchemy.orm import sessionmaker

    from app.execution.backends import TrustedSubprocessBackend
    from app.execution.service import process_available_jobs
    from app.worker_hooks import register_hooks

    register_hooks()
    factory = sessionmaker(bind=seeded_engine, expire_on_commit=False)

    def run() -> int:
        return process_available_jobs(factory, TrustedSubprocessBackend())

    return run
