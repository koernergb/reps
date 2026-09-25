import pytest
from pydantic import ValidationError

from app.config import Settings


def test_rejects_empty_database_url() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="")


def test_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(api_port=70000)
