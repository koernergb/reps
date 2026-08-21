from pathlib import Path

from alembic import command
from alembic.config import Config
from pytest import MonkeyPatch

from app.config import get_settings


def test_migrations_upgrade_and_downgrade(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    database_path = tmp_path / "migration.sqlite"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "20260820_0001")
    command.upgrade(config, "head")

    get_settings.cache_clear()
