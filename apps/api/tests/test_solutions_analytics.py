from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.analytics import AnalyticsContractError, validate
from app.config import Settings
from app.llm.provider import LLMUnavailable, OpenAIProvider, strict_json_schema
from app.models import CapabilityEvidence, ReviewTask, SolutionView


def test_solution_requires_confirmation_and_schedules_remediation(
    client: TestClient, seeded_engine: Engine
) -> None:
    assert "reference_solution" not in client.get("/v1/problems/pair-sum-indices").text
    refused = client.post("/v1/problems/pair-sum-indices/solution", json={"confirm": False})
    assert refused.status_code == 428
    body = client.post("/v1/problems/pair-sum-indices/solution", json={"confirm": True}).json()
    assert "def pair_sum_indices" in body["reference_solution"]
    assert [item["task_type"] for item in body["scheduled"]] == [
        "key_insight",
        "pseudocode",
        "implementation",
        "transfer",
        "reinterview",
    ]
    again = client.post("/v1/problems/pair-sum-indices/solution", json={"confirm": True}).json()
    assert again["scheduled"] == []
    progress = client.get("/v1/problems/pair-sum-indices/progress").json()
    assert progress["solution_viewed"] and {stage["status"] for stage in progress["stages"]} == {
        "scheduled"
    }
    with Session(seeded_engine) as session:
        assert len(session.scalars(select(SolutionView)).all()) == 2


def test_solution_view_makes_later_same_problem_success_assisted(
    client: TestClient, run_jobs: Any, seeded_engine: Engine
) -> None:
    from app.corpus.loader import get_corpus

    client.post("/v1/problems/pair-sum-indices/solution", json={"confirm": True})
    view = client.post("/v1/interviews", json={"problem_slug": "pair-sum-indices"}).json()
    for target in ("APPROACH_DISCUSSION", "IMPLEMENTATION"):
        view = client.post(
            f"/v1/interviews/{view['id']}/advance",
            json={
                "target": target,
                "expected_version": view["version"],
                "idempotency_key": uuid4().hex,
            },
        ).json()
    reference = get_corpus().problem("pair-sum-indices").definition.reference_solution
    client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": reference,
            "kind": "submit",
            "idempotency_key": uuid4().hex,
            "session_id": view["id"],
        },
    )
    run_jobs()
    view = client.get(f"/v1/interviews/{view['id']}").json()
    client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={
            "target": "COMPLETE",
            "expected_version": view["version"],
            "idempotency_key": uuid4().hex,
        },
    )
    with Session(seeded_engine) as session:
        evidence = session.scalars(
            select(CapabilityEvidence).where(CapabilityEvidence.source_id == view["id"])
        ).all()
        assert evidence and all(row.repeat_exposure for row in evidence)
        assert not any(row.transfer for row in evidence)
    capabilities = {item["slug"]: item for item in client.get("/v1/learner/capabilities").json()}
    assert capabilities["arrays-hashing.implementation"]["band"] != "Strong"


def test_in_interview_solution_view_is_recorded(client: TestClient, seeded_engine: Engine) -> None:
    view = client.post("/v1/interviews", json={"problem_slug": "pair-sum-indices"}).json()
    client.post(
        "/v1/problems/pair-sum-indices/solution", json={"confirm": True, "session_id": view["id"]}
    )
    after = client.get(f"/v1/interviews/{view['id']}").json()
    assert after["solution_viewed"] is True
    assert "solution_viewed" in [item["type"] for item in after["transcript"]]
    wrong = client.post(
        "/v1/problems/max-depth/solution", json={"confirm": True, "session_id": view["id"]}
    )
    assert wrong.status_code == 404
    with Session(seeded_engine) as session:
        assert (
            session.scalar(select(ReviewTask).where(ReviewTask.task_type == "key_insight"))
            is not None
        )


@pytest.mark.parametrize(
    ("name", "properties"),
    [
        ("interview_started", {"code": "print(1)"}),
        ("interview_started", {"mode": "practice", "transcript": "..."}),
        ("review_completed", {"task_type": "explain", "answer": "secret"}),
        ("not_an_event", {}),
        ("interview_started", {"mode": "a very long free text value that is not a token"}),
        ("interview_started", {"mode": ["list"]}),
    ],
)
def test_analytics_contract_rejects_content(name: str, properties: dict[str, Any]) -> None:
    with pytest.raises(AnalyticsContractError):
        validate(name, properties)


def test_analytics_contract_accepts_tokens() -> None:
    assert validate("interview_started", {"mode": "mock", "from_task": True}) == {
        "mode": "mock",
        "from_task": True,
    }


class Answer(BaseModel):
    value: int


def openai_provider(handler: Any, retries: int = 1) -> OpenAIProvider:
    settings = Settings(
        llm_provider="openai",
        openai_api_key="test-key",
        llm_max_retries=retries,
        environment="test",
        execution_backend="trusted-subprocess",
    )
    return OpenAIProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://x")
    )


def completion(content: str) -> dict[str, Any]:
    return {
        "model": "m",
        "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        "choices": [{"message": {"content": content}}],
    }


def test_openai_structured_output_and_retry_on_malformed() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)
        calls.append(body)
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200, json=completion("not json" if len(calls) == 1 else '{"value": 4}')
        )

    result = openai_provider(handler).generate(system="s", user="u", schema=Answer)
    assert result.value.value == 4 and result.attempts == 2
    assert result.input_tokens == 6
    assert calls[1]["messages"][-1]["content"].startswith("That response did not match")


@pytest.mark.parametrize(("status", "code"), [(429, "rate_limited"), (503, "provider_error")])
def test_openai_retries_then_fails_closed(status: int, code: str) -> None:
    provider = openai_provider(lambda request: httpx.Response(status, json={}), retries=1)
    with pytest.raises(LLMUnavailable) as error:
        provider.generate(system="s", user="u", schema=Answer)
    assert error.value.code == code


def test_openai_timeout_and_rejection() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(LLMUnavailable) as error:
        openai_provider(timeout, retries=0).generate(system="s", user="u", schema=Answer)
    assert error.value.code == "timeout"
    with pytest.raises(LLMUnavailable) as error:
        openai_provider(lambda r: httpx.Response(400, json={}), retries=0).generate(
            system="s", user="u", schema=Answer
        )
    assert error.value.code == "provider_rejected"


def test_strict_schema_requires_every_property() -> None:
    schema = strict_json_schema(Answer)
    assert schema["additionalProperties"] is False and schema["required"] == ["value"]
    with pytest.raises(ValueError):
        Settings(
            llm_provider="openai",
            openai_api_key=None,
            environment="test",
            execution_backend="trusted-subprocess",
        )
