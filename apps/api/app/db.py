from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings


def create_database_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_settings().database_url, pool_pre_ping=True)


@contextmanager
def database_connection(engine: Engine) -> Iterator[None]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        yield


def database_is_ready(engine: Engine) -> bool:
    try:
        with database_connection(engine):
            return True
    except Exception:
        # Readiness must fail closed for driver, DNS, pool, and database errors.
        # The caller returns a sanitized response and logs infrastructure detail separately.
        return False
