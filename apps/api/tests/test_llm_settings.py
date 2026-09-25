import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.evaluation.schemas import SemanticEvaluation
from app.llm import provider as provider_module
from app.llm.provider import (
    GeminiProvider,
    OpenAIProvider,
    _parse_json,
    build_provider,
    gemini_json_schema,
)
from app.local_mode import LOCAL_USER_ID
from app.main import create_app
from app.models import Base, LLMCredential
from app.seed import seed_database

GEMINI_KEY = "AIzaSy-test-key-1234567890abcd"


def put(client: TestClient, body: dict[str, Any]) -> Any:
    return client.put("/v1/settings/llm", json=body)


def test_defaults_follow_env(client: TestClient) -> None:
    body = client.get("/v1/settings/llm").json()
    assert body["active"] == "env" and body["effective"] == "offline"
    assert body["providers"]["gemini"]["has_key"] is False
    assert build_provider() is None


def test_saving_keys_never_returns_them(client: TestClient) -> None:
    response = put(
        client, {"gemini": {"api_key": GEMINI_KEY, "model": "gemini-2.5-pro"}, "active": "gemini"}
    )
    assert response.status_code == 200
    body = response.json()
    assert GEMINI_KEY not in response.text
    assert body["providers"]["gemini"] == {
        "has_key": True,
        "key_hint": "…abcd",
        "model": "gemini-2.5-pro",
        "env_key_present": False,
    }
    assert body["active"] == "gemini" and body["effective"] == "gemini"
    active = build_provider()
    assert isinstance(active, GeminiProvider) and active.model == "gemini-2.5-pro"
    assert client.get("/v1/system/status").json()["llm"]["provider"] == "gemini"
    assert GEMINI_KEY not in client.get("/v1/settings/llm").text


def test_model_change_keeps_key_and_clear_removes_it(client: TestClient) -> None:
    put(client, {"openai": {"api_key": "sk-test-openai-key-9999"}, "active": "openai"})
    body = put(client, {"openai": {"model": "gpt-custom"}}).json()
    assert (
        body["providers"]["openai"]["has_key"]
        and body["providers"]["openai"]["model"] == "gpt-custom"
    )
    active = build_provider()
    assert isinstance(active, OpenAIProvider) and active.model == "gpt-custom"
    put(client, {"active": "offline"})
    assert build_provider() is None
    cleared = put(client, {"openai": {"clear_key": True}}).json()
    assert cleared["providers"]["openai"]["has_key"] is False


def test_selecting_a_provider_requires_a_key(client: TestClient) -> None:
    response = put(client, {"active": "gemini"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "api_key_required"
    assert client.get("/v1/settings/llm").json()["active"] == "env"


def test_export_excludes_keys_and_reset_keeps_them(
    client: TestClient, seeded_engine: Engine
) -> None:
    put(client, {"gemini": {"api_key": GEMINI_KEY}})
    exported = client.get("/v1/me/export")
    assert GEMINI_KEY not in exported.text
    assert exported.json()["additional"]["llm_credentials"][0]["provider"] == "gemini"
    assert client.delete("/v1/me/history").status_code == 200
    with Session(seeded_engine) as session:
        assert session.get(LLMCredential, (LOCAL_USER_ID, "gemini")) is not None


def test_saved_choice_is_loaded_at_startup(tmp_path: Path) -> None:
    # A file database survives the first app's shutdown (which disposes its engine).
    url = f"sqlite+pysqlite:///{tmp_path / 'startup.sqlite'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    with TestClient(create_app(lambda: create_engine(url))) as first:
        put(first, {"gemini": {"api_key": GEMINI_KEY}, "active": "gemini"})
    assert build_provider() is None
    with TestClient(create_app(lambda: create_engine(url))):
        assert isinstance(build_provider(), GeminiProvider)
    engine.dispose()


def mock_gemini(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        response: httpx.Response = handler(request)
        return response

    original = provider_module.make_provider

    def factory(provider: str, api_key: str, model: str | None, settings: Any = None) -> Any:
        client = original(provider, api_key, model, settings)
        client._client = httpx.Client(
            transport=httpx.MockTransport(wrapped), base_url="https://gemini.test"
        )
        return client

    import app.routes.settings as settings_routes

    monkeypatch.setattr(settings_routes, "make_provider", factory)
    return seen


def test_list_models_and_connection_test(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(client, {"gemini": {"api_key": GEMINI_KEY, "model": "gemini-2.5-flash"}})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {GEMINI_KEY}"
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "models/gemini-2.5-flash"},
                        {"id": "models/gemini-2.5-pro"},
                        {"id": "models/embedding-001"},
                    ]
                },
            )
        body = json.loads(request.content)
        schema = body["response_format"]["json_schema"]
        assert "strict" not in schema and "additionalProperties" not in json.dumps(schema)
        return httpx.Response(
            200,
            json={
                "model": "gemini-2.5-flash",
                "choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}],
            },
        )

    mock_gemini(monkeypatch, handler)
    models = client.get("/v1/settings/llm/gemini/models").json()["models"]
    assert models == ["gemini-2.5-flash", "gemini-2.5-pro"]
    result = client.post("/v1/settings/llm/test", json={"provider": "gemini"}).json()
    assert result["ok"] is True and result["model"] == "gemini-2.5-flash"


def test_connection_test_reports_provider_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(client, {"gemini": {"api_key": GEMINI_KEY}})
    mock_gemini(
        monkeypatch,
        lambda request: httpx.Response(
            400, json=[{"error": {"message": "API key not valid. Please pass a valid API key."}}]
        ),
    )
    result = client.post("/v1/settings/llm/test", json={"provider": "gemini"}).json()
    assert result["ok"] is False and result["error_code"] == "provider_rejected"
    assert "API key not valid" in result["message"]
    assert client.get("/v1/settings/llm/openai/models").status_code == 422


def test_gemini_schema_is_self_contained() -> None:
    schema = gemini_json_schema(SemanticEvaluation)
    text = json.dumps(schema)
    assert "$ref" not in text and "$defs" not in text and "additionalProperties" not in text
    assert (
        schema["properties"]["weaknesses"]["items"]["properties"]["capability"]["type"] == "string"
    )
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('{"a": 2}') == {"a": 2}
