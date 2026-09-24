from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.interview import service
from app.interview.interviewer import InterviewerTurn
from app.interview.replay import replay
from app.llm.provider import LLMResult, LLMUnavailable
from app.models import InterviewEvent, InterviewSession, LLMCall, Problem, User

REFERENCE = get_corpus().problem("pair-sum-indices").definition.reference_solution


def key() -> str:
    return uuid4().hex


def start(
    client: TestClient, mode: str = "practice", problem: str = "pair-sum-indices"
) -> dict[str, Any]:
    response = client.post("/v1/interviews", json={"problem_slug": problem, "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def say(client: TestClient, view: dict[str, Any], text: str) -> dict[str, Any]:
    response = client.post(
        f"/v1/interviews/{view['id']}/messages",
        json={"content": text, "expected_version": view["version"], "idempotency_key": key()},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def advance(client: TestClient, view: dict[str, Any], target: str) -> dict[str, Any]:
    response = client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={"target": target, "expected_version": view["version"], "idempotency_key": key()},
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def interviewer_lines(view: dict[str, Any]) -> list[str]:
    return [
        item["payload"]["content"]
        for item in view["transcript"]
        if item["type"] == "interviewer_message"
    ]


def test_full_practice_interview_reaches_report(
    client: TestClient, run_jobs: Callable[[], int]
) -> None:
    view = start(client)
    assert view["state"] == "INTRO" and view["policy"]["mode"] == "practice"
    view = say(client, view, "Can the same element be used twice?")
    assert "must be different" in interviewer_lines(view)[-1]
    view = say(client, view, "I would scan once with a hash map from value to index.")
    view = advance(client, view, "IMPLEMENTATION")
    client.put(
        f"/v1/interviews/{view['id']}/code", json={"code": REFERENCE, "idempotency_key": key()}
    )
    job = client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": REFERENCE,
            "kind": "submit",
            "idempotency_key": key(),
            "session_id": view["id"],
        },
    ).json()
    run_jobs()
    view = client.get(f"/v1/interviews/{view['id']}").json()
    assert view["state"] == "COMPLEXITY"
    types = [item["type"] for item in view["transcript"]]
    assert "solution_submitted" in types and "test_success" in types
    view = say(client, view, "O(n) time and O(n) space.")
    assert view["state"] == "FOLLOW_UP"
    view = say(client, view, "Two pointers on sorted input give O(1) space.")
    assert view["state"] == "COMPLETE" and view["evaluation"]["status"] == "completed"
    report = client.get(f"/v1/interviews/{view['id']}/report").json()
    assert report["report"]["facts"]["result"] == "solved_independently"
    assert report["report"]["facts"]["passed_hidden"] is True
    assert job["status"] == "queued"


def test_stale_and_duplicate_requests(client: TestClient) -> None:
    view = start(client)
    idempotency = key()
    body = {
        "content": "What about duplicates?",
        "expected_version": view["version"],
        "idempotency_key": idempotency,
    }
    first = client.post(f"/v1/interviews/{view['id']}/messages", json=body)
    assert first.status_code == 200
    retry = client.post(f"/v1/interviews/{view['id']}/messages", json=body)
    assert retry.status_code == 200
    assert retry.json()["version"] == first.json()["version"]
    assert len(retry.json()["transcript"]) == len(first.json()["transcript"])
    stale = client.post(
        f"/v1/interviews/{view['id']}/messages",
        json={"content": "hello", "expected_version": view["version"], "idempotency_key": key()},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_version"


def test_invalid_transition_is_rejected_without_side_effects(client: TestClient) -> None:
    view = start(client)
    response = client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={"target": "FOLLOW_UP", "expected_version": view["version"], "idempotency_key": key()},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    after = client.get(f"/v1/interviews/{view['id']}").json()
    assert after["state"] == "INTRO" and after["version"] == view["version"]


def test_code_is_required_before_testing(client: TestClient) -> None:
    view = start(client)
    view = advance(client, view, "APPROACH_DISCUSSION")
    view = advance(client, view, "IMPLEMENTATION")
    response = client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={"target": "TESTING", "expected_version": view["version"], "idempotency_key": key()},
    )
    assert response.json()["error"]["code"] == "code_required"


def test_practice_hint_ladder_and_budget(client: TestClient, seeded_engine: Engine) -> None:
    view = start(client)
    hints = get_corpus().problem("pair-sum-indices").definition.hints
    for level in range(1, 6):
        view = client.post(
            f"/v1/interviews/{view['id']}/hints",
            json={"expected_version": view["version"], "idempotency_key": key()},
        ).json()
        assert view["max_hint_level"] == level
        given = [item for item in view["transcript"] if item["type"] == "hint_given"]
        assert given[-1]["payload"]["content"] == hints[level - 1]
    extra = client.post(
        f"/v1/interviews/{view['id']}/hints",
        json={"expected_version": view["version"], "idempotency_key": key()},
    )
    assert extra.status_code == 409
    with Session(seeded_engine) as session:
        logged = session.scalars(
            select(InterviewEvent).where(InterviewEvent.event_type == "hint_given")
        ).all()
        assert all("interview.independence" in event.payload["capability_tags"] for event in logged)


def test_mock_mode_allows_one_small_nudge_and_has_a_deadline(client: TestClient) -> None:
    view = start(client, mode="mock")
    assert view["deadline_at"] is not None and view["time_limit_s"] == 45 * 60
    assert "45 minutes" in interviewer_lines(view)[0]
    view = client.post(
        f"/v1/interviews/{view['id']}/hints",
        json={"expected_version": view["version"], "idempotency_key": key()},
    ).json()
    assert view["max_hint_level"] == 1
    second = client.post(
        f"/v1/interviews/{view['id']}/hints",
        json={"expected_version": view["version"], "idempotency_key": key()},
    )
    assert second.status_code == 409
    assert "mode" in second.json()["error"]["message"]


def test_mock_accommodation_extends_time(client: TestClient) -> None:
    response = client.post(
        "/v1/interviews",
        json={
            "problem_slug": "pair-sum-indices",
            "mode": "mock",
            "time_multiplier": 1.5,
            "reduce_motion": True,
        },
    ).json()
    assert response["time_limit_s"] == round(45 * 60 * 1.5)
    assert response["accommodations"]["reduce_motion"] is True


def test_mock_timer_expires_server_side(client: TestClient, seeded_engine: Engine) -> None:
    view = start(client, mode="mock")
    with Session(seeded_engine) as session:
        interview = session.get(InterviewSession, view["id"])
        assert interview is not None
        interview.deadline_at = service.utcnow() - timedelta(seconds=1)
        session.commit()
    late = client.post(
        f"/v1/interviews/{view['id']}/messages",
        json={
            "content": "Still here",
            "expected_version": view["version"],
            "idempotency_key": key(),
        },
    )
    assert late.status_code == 200
    body = late.json()
    assert body["state"] == "COMPLETE" and body["result"] == "timed_out"
    assert "timer_expired" in [item["type"] for item in body["transcript"]]
    report = client.get(f"/v1/interviews/{view['id']}/report").json()
    assert report["report"]["facts"]["result"] == "timed_out"
    assert report["report"]["scorecard"]["rubric_version"] == "scorecard/v1"


def test_abandon_is_terminal(client: TestClient) -> None:
    view = start(client)
    view = advance(client, view, "ABANDONED")
    assert view["state"] == "ABANDONED" and view["result"] == "abandoned"
    response = client.post(
        f"/v1/interviews/{view['id']}/messages",
        json={"content": "hi", "expected_version": view["version"], "idempotency_key": key()},
    )
    assert response.status_code == 409


def test_replay_reconstructs_session(
    client: TestClient, seeded_engine: Engine, run_jobs: Callable[[], int]
) -> None:
    view = start(client)
    view = say(client, view, "Is the input sorted?")
    view = advance(client, view, "APPROACH_DISCUSSION")
    view = client.post(
        f"/v1/interviews/{view['id']}/hints",
        json={"expected_version": view["version"], "idempotency_key": key()},
    ).json()
    view = advance(client, view, "IMPLEMENTATION")
    client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": REFERENCE,
            "kind": "run",
            "idempotency_key": key(),
            "session_id": view["id"],
        },
    )
    run_jobs()
    with Session(seeded_engine) as session:
        interview = session.get(InterviewSession, view["id"])
        assert interview is not None
        events = session.scalars(
            select(InterviewEvent).where(InterviewEvent.session_id == interview.id)
        ).all()
        problem = session.get(Problem, interview.problem_id)
        assert problem is not None
        replayed = replay(events, problem.starter_code)
        assert replayed.state == interview.state
        assert replayed.hints_used == interview.hints_used
        assert replayed.max_hint_level == interview.max_hint_level
        assert replayed.current_code == interview.current_code
        assert replayed.event_count == interview.event_count
        assert [event.sequence for event in sorted(events, key=lambda e: e.sequence)] == list(
            range(1, interview.event_count + 1)
        )


def test_other_users_cannot_access_sessions(client: TestClient, seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        other = User(display_name="Other", mode="authenticated", email="o@example.com")
        session.add(other)
        session.commit()
        interview = service.start_session(session, other, "pair-sum-indices", "practice")
        other_id = interview.id
    assert client.get(f"/v1/interviews/{other_id}").status_code == 404
    assert (
        client.post(
            f"/v1/interviews/{other_id}/messages",
            json={"content": "x", "expected_version": 1, "idempotency_key": key()},
        ).status_code
        == 404
    )
    assert client.get(f"/v1/interviews/{other_id}/report").status_code == 404
    assert all(item["id"] != other_id for item in client.get("/v1/interviews").json())
    execution = client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": "x",
            "kind": "run",
            "idempotency_key": key(),
            "session_id": other_id,
        },
    )
    assert execution.status_code == 404


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, behavior: Callable[[str], InterviewerTurn]) -> None:
        self.behavior = behavior
        self.calls = 0

    def generate(self, *, system: str, user: str, schema: type[Any]) -> LLMResult[Any]:
        self.calls += 1
        assert "reference_solution" not in system and "hidden_tests" not in system
        if schema is not InterviewerTurn:
            raise LLMUnavailable("timeout", "no evaluator in this fake")
        return LLMResult(self.behavior(user), "fake", "fake-model", 5, 10, 5, 1)


@pytest.fixture
def fake_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[Callable[[str], InterviewerTurn]], FakeProvider]]:
    import app.evaluation.service as evaluation_service

    def install(behavior: Callable[[str], InterviewerTurn]) -> FakeProvider:
        provider = FakeProvider(behavior)
        monkeypatch.setattr(service, "provider_factory", lambda: provider)
        monkeypatch.setattr(evaluation_service, "provider_factory", lambda: None)
        return provider

    yield install


def test_llm_turns_are_recorded_and_invalid_transitions_ignored(
    client: TestClient, seeded_engine: Engine, fake_llm: Any
) -> None:
    fake_llm(
        lambda _: InterviewerTurn(
            message="Tell me more about your approach.",
            recommended_transition="COMPLETE",
            learner_event_type="approach_proposed",
            capability_tags=["arrays-hashing.recognition", "bogus.tag"],
        )
    )
    view = start(client)
    view = say(client, view, "Use a hash map for complements.")
    assert view["state"] == "INTRO"
    assert interviewer_lines(view)[-1] == "Tell me more about your approach."
    utterance = [item for item in view["transcript"] if item["actor"] == "learner"][-1]
    assert utterance["type"] == "approach_proposed"
    assert utterance["payload"]["capability_tags"] == ["arrays-hashing.recognition"]
    with Session(seeded_engine) as session:
        calls = session.scalars(select(LLMCall)).all()
        assert calls and all(call.status == "ok" and call.task == "interviewer" for call in calls)
        assert all(call.prompt_version.startswith("interviewer/v1+") for call in calls)


def test_llm_leak_is_blocked(client: TestClient, fake_llm: Any) -> None:
    fake_llm(
        lambda _: InterviewerTurn(
            message="Sure:\n```python\ncomplement = target - value\n```",
            recommended_transition=None,
            learner_event_type=None,
            capability_tags=[],
        )
    )
    view = start(client)
    view = say(client, view, "Just give me the code.")
    assert "complement" not in interviewer_lines(view)[-1]
    assert "leak_blocked" in [item["type"] for item in view["transcript"]]


@pytest.mark.parametrize("code", ["timeout", "malformed_output", "rate_limited"])
def test_llm_failures_fall_back_to_policy(
    client: TestClient, seeded_engine: Engine, fake_llm: Any, code: str
) -> None:
    def fail(_: str) -> InterviewerTurn:
        raise LLMUnavailable(code, "down", attempts=3)

    fake_llm(fail)
    view = start(client)
    view = say(client, view, "Can the same element be used twice?")
    assert "must be different" in interviewer_lines(view)[-1]
    with Session(seeded_engine) as session:
        fallback = session.scalars(
            select(InterviewEvent).where(InterviewEvent.event_type == "llm_fallback")
        ).all()
        assert fallback and fallback[-1].payload["error_code"] == code
        failed = session.scalars(select(LLMCall).where(LLMCall.status == "error")).all()
        assert failed and failed[-1].error_code == code


def test_idle_checkin_respects_policy(client: TestClient, seeded_engine: Engine) -> None:
    view = start(client)
    with Session(seeded_engine) as session:
        interview = session.get(InterviewSession, view["id"])
        assert interview is not None
        interview.last_activity_at = service.utcnow() - timedelta(minutes=10)
        session.commit()
    after = client.post(
        f"/v1/interviews/{view['id']}/idle",
        json={"expected_version": view["version"], "idle_seconds": 600},
    ).json()
    assert "Take your time" in interviewer_lines(after)[-1]
    mock = start(client, mode="mock")
    quiet = client.post(
        f"/v1/interviews/{mock['id']}/idle",
        json={"expected_version": mock["version"], "idle_seconds": 200},
    ).json()
    assert len(interviewer_lines(quiet)) == len(interviewer_lines(mock))


def test_personas_pass_with_offline_interviewer() -> None:
    from app.interview.personas import run_all

    results = run_all()
    failures = {item.persona: item.failures for item in results if not item.passed}
    assert not failures
    assert len(results) >= 9
