from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.drills.composer import CODE_TYPES, Candidate, compose
from app.local_mode import LOCAL_USER_ID
from app.models import (
    AnalyticsEvent,
    Capability,
    CapabilityEvidence,
    Exercise,
    ReviewTask,
    User,
)
from app.reviews.grading import Rubric, rubric_grade
from app.scheduling.scheduler import create_task


def make_task(
    session: Session, exercise_source: str, *, due_offset_h: float = -1, problem: Any = None
) -> str:
    user = session.get(User, LOCAL_USER_ID)
    exercise = session.scalar(select(Exercise).where(Exercise.source_id == exercise_source))
    assert user is not None and exercise is not None
    capability = session.get(Capability, exercise.capability_id)
    assert capability is not None
    task = create_task(
        session,
        user,
        capability=capability,
        task_type=exercise.exercise_type,
        due=datetime.now(UTC) + timedelta(hours=due_offset_h),
        reason="Test reason",
        source_type="test",
        source_id=str(uuid4()),
        chain_id=str(uuid4()),
        step=1,
        exercise=exercise,
        problem=problem,
    )
    session.commit()
    assert task is not None
    return task.id


def test_rubric_grading() -> None:
    rubric = Rubric(
        prompt="p",
        key_points=[["half", "halves"], ["log"]],
        accepted_answers=[],
        reference="r",
        misconception="m",
    )
    assert rubric_grade(rubric, "each step halves the range so it's log n").correctness == 1.0
    partial = rubric_grade(rubric, "each comparison halves what remains")
    assert partial.correctness == 0.5 and partial.missing_points == ["log"]
    assert rubric_grade(rubric, "no idea").recommended_action == "rebuild"
    exact = Rubric(
        prompt="p", key_points=[], accepted_answers=["0 0 2 2"], reference="r", misconception=None
    )
    assert rubric_grade(exact, " 0  0 2 2 ").correctness == 1.0
    assert rubric_grade(exact, "0 0 1 2").correctness == 0.0


def test_text_review_retrieve_coach_and_rebuild(client: TestClient, seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        task_id = make_task(session, "sw-explain-window-invariant")
    queue = client.get("/v1/reviews/queue").json()
    item = next(task for task in queue["due"] if task["id"] == task_id)
    assert item["reason"] == "Test reason" and item["estimated_minutes"] > 0
    started = client.post(f"/v1/reviews/tasks/{task_id}/start", json={}).json()
    resumed = client.post(f"/v1/reviews/tasks/{task_id}/start", json={}).json()
    assert started["attempt_id"] == resumed["attempt_id"] and started["kind"] == "text"
    hinted = client.post(f"/v1/reviews/attempts/{started['attempt_id']}/hint").json()
    assert hinted["hints_used"] == 1 and hinted["mode"] == "coach" and hinted["hints"]
    result = client.post(
        f"/v1/reviews/attempts/{started['attempt_id']}/answer",
        json={"answer": "I am not sure", "confidence": 1},
    ).json()
    feedback = result["result"]
    assert feedback["band"] == "missed" and feedback["recommended_action"] == "rebuild"
    assert feedback["rebuild"]["confirmation_question"]
    confirmed = client.post(
        f"/v1/reviews/attempts/{started['attempt_id']}/confirm",
        json={"answer": "The window stays distinct; any earlier start still has the repeat."},
    ).json()
    assert confirmed["result"]["confirmation"]["correctness"] > 0
    with Session(seeded_engine) as session:
        task = session.get(ReviewTask, task_id)
        assert task is not None and task.status == "completed"
        retry = session.scalar(select(ReviewTask).where(ReviewTask.source_type == "review_retry"))
        assert retry is not None and retry.status == "pending"
        evidence = session.scalars(
            select(CapabilityEvidence).where(CapabilityEvidence.source_type.like("review%"))
        ).all()
        assert {row.exercise_type for row in evidence} == {"explain", "confirmation"}
        assert any(row.hint_level == 1 for row in evidence)


def test_code_review_uses_sandbox_verdict(
    client: TestClient, seeded_engine: Engine, run_jobs: Any
) -> None:
    with Session(seeded_engine) as session:
        task_id = make_task(session, "sw-debug-stale-index")
    item = client.post(f"/v1/reviews/tasks/{task_id}/start", json={}).json()
    assert item["kind"] == "code" and item["problem_slug"] == "longest-unique-substring"
    assert "last[char] + 1" in item["starter_code"]
    missing = client.post(f"/v1/reviews/attempts/{item['attempt_id']}/answer", json={})
    assert missing.status_code == 422
    reference = get_corpus().problem("longest-unique-substring").definition.reference_solution
    job = client.post(
        "/v1/executions",
        json={
            "problem_slug": "longest-unique-substring",
            "code": reference,
            "kind": "submit",
            "idempotency_key": uuid4().hex,
        },
    ).json()
    run_jobs()
    done = client.post(
        f"/v1/reviews/attempts/{item['attempt_id']}/answer", json={"job_id": job["id"]}
    ).json()
    assert done["result"]["correctness"] == 1.0 and done["result"]["grader"] == "sandbox"


def test_snooze_skip_and_report(client: TestClient, seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        first = make_task(session, "ah-recall-when-hash")
        second = make_task(session, "tp-recall-when")
        third = make_task(session, "st-recall-when")
    snoozed = client.post(f"/v1/reviews/tasks/{first}/snooze", json={"days": 2}).json()
    assert snoozed["status"] == "snoozed"
    assert first not in {task["id"] for task in client.get("/v1/reviews/queue").json()["due"]}
    assert client.post(f"/v1/reviews/tasks/{second}/skip").json()["status"] == "skipped"
    reported = client.post(
        f"/v1/reviews/tasks/{third}/report", json={"reason": "Ambiguous wording"}
    ).json()
    assert reported["status"] == "invalidated" and "Ambiguous" in reported["reason"]
    assert client.post(f"/v1/reviews/tasks/{third}/skip").status_code == 409
    with Session(seeded_engine) as session:
        names = set(session.scalars(select(AnalyticsEvent.name)))
        assert {"review_snoozed", "review_skipped", "exercise_reported"} <= names


def test_reviews_are_user_scoped(client: TestClient, seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        other = User(display_name="Other", mode="authenticated", email="x@example.com")
        session.add(other)
        session.commit()
        exercise = session.scalar(
            select(Exercise).where(Exercise.source_id == "ah-recall-when-hash")
        )
        assert exercise is not None
        capability = session.get(Capability, exercise.capability_id)
        assert capability is not None
        task = create_task(
            session,
            other,
            capability=capability,
            task_type="recall",
            due=datetime.now(UTC),
            reason="x",
            source_type="x",
            source_id="x",
            chain_id="x",
            step=1,
            exercise=exercise,
            problem=None,
        )
        session.commit()
        task_id = task.id  # type: ignore[union-attr]
    assert client.post(f"/v1/reviews/tasks/{task_id}/start", json={}).status_code == 404
    assert client.post(f"/v1/reviews/tasks/{task_id}/skip").status_code == 404
    assert task_id not in str(client.get("/v1/reviews/queue").json())


candidate_strategy = st.builds(
    Candidate,
    kind=st.sampled_from(["task", "practice", "onboarding"]),
    key=st.uuids().map(str),
    capability_slug=st.sampled_from([f"t{i}.c{j}" for i in range(4) for j in range(3)]),
    topic=st.just("x"),
    task_type=st.sampled_from(
        ["recall", "explain", "trace", "debug", "implementation", "transfer", "reinterview"]
    ),
    minutes=st.floats(0.5, 15),
    priority=st.floats(0, 40),
    due_at=st.none(),
    reason=st.just("r"),
    exercise_id=st.one_of(st.none(), st.sampled_from(["e1", "e2", "e3"])),
).map(lambda c: Candidate(**{**c.__dict__, "topic": c.capability_slug.split(".")[0]}))


@settings(max_examples=200, deadline=None)
@given(st.lists(candidate_strategy, max_size=30), st.integers(5, 30))
def test_composer_invariants(candidates: list[Candidate], budget: int) -> None:
    chosen = compose(candidates, budget)
    assert sum(item.minutes for item in chosen) <= budget + 1e-9
    assert len({item.key for item in chosen}) == len(chosen)
    exercises = [item.exercise_id for item in chosen if item.exercise_id]
    assert len(exercises) == len(set(exercises))
    assert all(item.task_type != "reinterview" for item in chosen)
    assert sum(1 for item in chosen if item.task_type in CODE_TYPES) <= (2 if budget >= 25 else 1)
    assert (
        max((sum(1 for i in chosen if i.topic == t) for t in {i.topic for i in chosen}), default=0)
        <= 2
    )
    capabilities = [item.capability_slug for item in chosen if not item.retry]
    assert len(capabilities) == len(set(capabilities))
    assert compose(list(reversed(candidates)), budget) == chosen or len(
        {c.priority for c in candidates}
    ) < len(candidates)


def test_new_user_drill_onboards_across_topics(client: TestClient, seeded_engine: Engine) -> None:
    drill = client.post("/v1/drills", json={"budget_minutes": 10}).json()
    assert drill["items"] and drill["planned_minutes"] <= 10
    topics = [item["topic"] for item in drill["items"]]
    assert len(set(topics)) == len(topics)
    assert all(item["kind"] == "onboarding" for item in drill["items"])
    assert "calibration" in drill["mix"] and "Arrays & Hashing" in drill["mix"]
    assert client.post("/v1/drills", json={"budget_minutes": 10}).json()["id"] == drill["id"]


def test_due_items_take_priority_and_drill_completes_exactly_once(
    client: TestClient, seeded_engine: Engine
) -> None:
    with Session(seeded_engine) as session:
        overdue = make_task(session, "bs-recall-log", due_offset_h=-72)
        make_task(session, "hp-recall-when", due_offset_h=-2)
    drill = client.post("/v1/drills", json={"budget_minutes": 5}).json()
    assert drill["items"][0]["task_id"] == overdue or overdue in {
        i["task_id"] for i in drill["items"]
    }
    for item in drill["items"]:
        started = client.post(
            f"/v1/reviews/tasks/{item['task_id']}/start", json={"drill_session_id": drill["id"]}
        ).json()
        client.post(
            f"/v1/reviews/attempts/{started['attempt_id']}/answer",
            json={"answer": "each step halves the search so it's logarithmic"},
        )
        client.post(
            f"/v1/reviews/attempts/{started['attempt_id']}/answer", json={"answer": "duplicate"}
        )
    view = client.get(f"/v1/drills/{drill['id']}").json()
    assert view["completed_items"] == len(drill["items"]) and view["current_index"] is None
    finished = client.post(f"/v1/drills/{drill['id']}/actions", json={"action": "complete"}).json()
    assert finished["status"] == "completed"
    with Session(seeded_engine) as session:
        evidence = session.scalars(
            select(CapabilityEvidence).where(CapabilityEvidence.source_type == "review")
        ).all()
        assert len(evidence) == len(drill["items"])
        names = [row.name for row in session.scalars(select(AnalyticsEvent))]
        assert names.count("drill_completed") == 1


def test_abandoned_drill_invalidates_unstarted_practice(
    client: TestClient, seeded_engine: Engine
) -> None:
    drill = client.post("/v1/drills", json={"budget_minutes": 10}).json()
    paused = client.post(f"/v1/drills/{drill['id']}/actions", json={"action": "pause"}).json()
    assert paused["status"] == "paused"
    resumed = client.post(f"/v1/drills/{drill['id']}/actions", json={"action": "resume"}).json()
    assert resumed["status"] == "active"
    client.post(f"/v1/drills/{drill['id']}/actions", json={"action": "abandon"})
    with Session(seeded_engine) as session:
        statuses = {session.get(ReviewTask, item["task_id"]).status for item in drill["items"]}  # type: ignore[union-attr]
        assert statuses == {"invalidated"}
    assert client.get("/v1/drills/active").json() is None


def test_drill_budget_validation(client: TestClient) -> None:
    assert client.post("/v1/drills", json={"budget_minutes": 3}).status_code == 422
