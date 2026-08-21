from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.local_mode import LOCAL_USER_ID
from app.main import create_app
from app.models import (
    Capability,
    Exercise,
    HintLog,
    InterviewEvent,
    InterviewSession,
    LearnerCapabilityState,
    Problem,
    ReviewAttempt,
)


def add_learning_history(engine: Engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        problem = session.scalar(select(Problem).limit(1))
        capability = session.scalar(select(Capability).limit(1))
        assert problem is not None
        assert capability is not None
        exercise = Exercise(
            capability_id=capability.id,
            problem_id=problem.id,
            exercise_type="recall",
            prompt="Explain the idea.",
            expected_answer="Use an invariant.",
            source_type="curated",
            provenance={"reviewed": False},
        )
        interview = InterviewSession(
            user_id=LOCAL_USER_ID,
            problem_id=problem.id,
            mode="practice",
            state="COMPLETE",
            started_at=now,
            completed_at=now,
            result="completed",
            evaluation={"summary": "fixture"},
        )
        session.add_all([exercise, interview])
        session.flush()
        session.add_all(
            [
                ReviewAttempt(
                    user_id=LOCAL_USER_ID,
                    exercise_id=exercise.id,
                    started_at=now,
                    completed_at=now,
                    answer="fixture answer",
                    correctness=0.5,
                    confidence=3,
                    hints_used=1,
                    evaluation={"fixture": True},
                ),
                LearnerCapabilityState(
                    user_id=LOCAL_USER_ID,
                    capability_id=capability.id,
                    mastery=0.5,
                    stability=1,
                    difficulty=0.5,
                    last_reviewed_at=now,
                    next_review_at=now,
                    evidence_count=1,
                ),
                InterviewEvent(
                    session_id=interview.id,
                    sequence=1,
                    event_type="interview_started",
                    occurred_at=now,
                    schema_version=1,
                    payload={"fixture": True},
                ),
                HintLog(
                    user_id=LOCAL_USER_ID,
                    session_id=interview.id,
                    hint_level=1,
                    hint_text="Consider the invariant.",
                    occurred_at=now,
                ),
            ]
        )
        session.commit()


def test_local_profile_warns_about_missing_auth(client: TestClient) -> None:
    response = client.get("/v1/me")
    assert response.status_code == 200
    assert response.json()["mode"] == "local"
    assert "no authentication" in response.json()["warning"].lower()


def test_export_contains_owned_history_but_not_corpus_secrets(
    client: TestClient, seeded_engine: Engine
) -> None:
    add_learning_history(seeded_engine)
    response = client.get("/v1/me/export")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1
    assert len(body["review_attempts"]) == 1
    assert len(body["interview_sessions"]) == 1
    assert len(body["interview_events"]) == 1
    assert len(body["hint_logs"]) == 1
    assert "reference_solution" not in response.text
    assert "hidden_tests" not in response.text


def test_reset_deletes_history_and_preserves_profile_and_corpus(
    client: TestClient, seeded_engine: Engine
) -> None:
    add_learning_history(seeded_engine)
    response = client.delete("/v1/me/history")

    assert response.status_code == 200
    assert response.json()["deleted"] == {
        "interview_events": 1,
        "hint_logs": 1,
        "review_attempts": 1,
        "capability_states": 1,
        "interview_sessions": 1,
    }
    with Session(seeded_engine) as session:
        assert session.scalar(select(func.count()).select_from(InterviewSession)) == 0
        assert session.scalar(select(func.count()).select_from(Problem)) == 3
    assert client.get("/v1/me").status_code == 200


def test_reset_is_idempotent(client: TestClient) -> None:
    response = client.delete("/v1/me/history")
    assert response.status_code == 200
    assert sum(response.json()["deleted"].values()) == 0


def test_local_profile_fails_closed_before_seed(unseeded_engine: Engine) -> None:
    with TestClient(create_app(lambda: unseeded_engine)) as unseeded_client:
        response = unseeded_client.get("/v1/me")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "local_data_not_initialized"
