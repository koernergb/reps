from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.main import create_app


def sqlite_engine() -> Engine:
    return create_engine("sqlite+pysqlite:///:memory:")


def test_health_includes_request_id() -> None:
    with TestClient(create_app(sqlite_engine)) as client:
        response = client.get("/health", headers={"x-request-id": "test-request"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request"
    assert response.json() == {
        "status": "ok",
        "service": "reps-api",
        "version": "0.1.0",
        "request_id": "test-request",
    }


def test_health_generates_request_id() -> None:
    with TestClient(create_app(sqlite_engine)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["request_id"] != "unknown"
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_ready_succeeds_when_database_is_available() -> None:
    with TestClient(create_app(sqlite_engine)) as client:
        response = client.get("/ready", headers={"x-request-id": "ready-request"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "ready-request"


def broken_engine() -> Engine:
    return create_engine("sqlite+pysqlite:////private/tmp/reps-missing-directory/db.sqlite")


def test_ready_fails_cleanly_when_database_is_unavailable() -> None:
    with TestClient(create_app(broken_engine)) as client:
        response = client.get("/ready", headers={"x-request-id": "failed-ready"})

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "The API is waiting for its database.",
            "request_id": "failed-ready",
        }
    }
