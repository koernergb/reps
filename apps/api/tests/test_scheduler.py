from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.local_mode import LOCAL_USER_ID
from app.models import Capability, LearnerCapabilityState, Problem, ReviewTask, User
from app.scheduling.scheduler import (
    PlannedTask,
    Weak,
    due_at_for,
    plan_chain,
    schedule_chain,
)


def test_due_dates_are_local_4am_across_dst() -> None:
    zone = ZoneInfo("America/New_York")
    before = due_at_for(date(2026, 3, 7), zone)
    after = due_at_for(date(2026, 3, 9), zone)
    assert before.astimezone(zone).hour == 4 and after.astimezone(zone).hour == 4
    assert (after - before) == timedelta(hours=47)
    fall = due_at_for(date(2026, 11, 2), zone) - due_at_for(date(2026, 10, 31), zone)
    assert fall == timedelta(hours=49)
    assert (
        due_at_for(date(2026, 6, 1), ZoneInfo("Asia/Kolkata"))
        .astimezone(ZoneInfo("Asia/Kolkata"))
        .hour
        == 4
    )


def test_sliding_window_scenario_matches_brief() -> None:
    planned = plan_chain(
        [
            Weak("sliding-window.recognition", "recognition", "high", 0.8),
            Weak("sliding-window.invariant", "reasoning", "high", 0.8),
            Weak("sliding-window.boundaries", "debugging", "medium", 0.8),
        ],
        "Longest Repeat-Free Substring",
    )
    steps = [(item.offset_days, item.task_type) for item in planned]
    assert steps[:2] == [(1, "explain"), (1, "recognition")]
    assert (2, "debug") in steps
    assert (7, "implementation") in steps
    assert (14, "transfer") in steps
    assert (3, "trace") in steps
    assert len(steps) <= 6
    assert [item.offset_days for item in planned] == sorted(item.offset_days for item in planned)
    assert all(item.offset_days >= 0 for item in planned)
    explain = next(item for item in planned if item.task_type == "explain")
    assert explain.capability_slug == "sliding-window.invariant"


def test_low_severity_creates_a_light_plan() -> None:
    planned = plan_chain([Weak("heap.complexity", "complexity", "low", 0.9)], "x")
    assert [(item.offset_days, item.task_type) for item in planned] == [(5, "recall")]
    assert plan_chain([], "x") == []


def schedule(
    session: Session, planned: list[PlannedTask], anchor: datetime | None = None
) -> list[ReviewTask]:
    user = session.get(User, LOCAL_USER_ID)
    assert user is not None
    problem = session.scalar(select(Problem).where(Problem.slug == "longest-unique-substring"))
    tasks = schedule_chain(
        session,
        user,
        planned,
        source_type="interview",
        source_id=str(uuid4()),
        source_problem=problem,
        anchor=anchor,
    )
    session.commit()
    return tasks


def test_chain_selects_exercises_and_unseen_transfer_problems(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        planned = plan_chain([Weak("sliding-window.invariant", "reasoning", "high", 0.9)], "x")
        tasks = schedule(session, planned)
        by_type = {task.task_type: task for task in tasks}
        assert by_type["explain"].exercise is not None
        assert by_type["explain"].exercise.capability.slug.startswith("sliding-window.")
        assert by_type["implementation"].problem.slug == "longest-unique-substring"  # type: ignore[union-attr]
        transfer = by_type["transfer"].problem
        assert transfer is not None and transfer.slug != "longest-unique-substring"
        assert transfer.transfer_group == "variable-window"


def test_duplicates_are_prevented(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        planned = plan_chain([Weak("stack.invariant", "reasoning", "medium", 0.9)], "x")
        first = schedule(session, planned)
        second = schedule(session, planned)
        assert first and not second
        active = session.scalar(
            select(func.count()).select_from(ReviewTask).where(ReviewTask.status == "pending")
        )
        assert active == len(first)
        duplicate = ReviewTask(
            user_id=LOCAL_USER_ID,
            capability_id=first[0].capability_id,
            task_type=first[0].task_type,
            status="pending",
            due_at=first[0].due_at,
            source_type="x",
            source_id="x",
            chain_id="x",
            step=1,
            reason="x",
            dedupe_key=first[0].dedupe_key,
            created_at=first[0].created_at,
            updated_at=first[0].updated_at,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


def test_daily_cap_pushes_overflow_to_next_day(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        user = session.get(User, LOCAL_USER_ID)
        assert user is not None
        user.daily_review_cap = 2
        session.commit()
        slugs = ["arrays-hashing.invariant", "stack.invariant", "trees.invariant", "heap.invariant"]
        planned = [PlannedTask(slug, "explain", 1, "cap test") for slug in slugs]
        tasks = schedule(session, planned, anchor=datetime(2026, 5, 1, 12, tzinfo=UTC))
        days = sorted(task.due_at.date() for task in tasks)
        assert days.count(days[0]) == 2
        assert len(set(days)) == 2


def test_long_absence_keeps_tasks_due_not_duplicated(
    client: TestClient, seeded_engine: Engine
) -> None:
    with Session(seeded_engine) as session:
        planned = plan_chain([Weak("stack.recognition", "recognition", "medium", 0.9)], "x")
        schedule(session, planned, anchor=datetime.now(UTC) - timedelta(days=90))
    queue = client.get("/v1/reviews/queue").json()
    assert len(queue["due"]) == len({task["id"] for task in queue["due"]}) == len(planned)


def failed_interview(client: TestClient, run_jobs: Any) -> str:
    from app.corpus.loader import get_corpus

    wrong = get_corpus().problem("longest-unique-substring").definition.wrong_solutions[0].code
    view = client.post("/v1/interviews", json={"problem_slug": "longest-unique-substring"}).json()
    for target in ("APPROACH_DISCUSSION", "IMPLEMENTATION"):
        view = client.post(
            f"/v1/interviews/{view['id']}/advance",
            json={
                "target": target,
                "expected_version": view["version"],
                "idempotency_key": uuid4().hex,
            },
        ).json()
    client.post(
        "/v1/executions",
        json={
            "problem_slug": "longest-unique-substring",
            "code": wrong,
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
    return str(view["id"])


def test_failed_interview_to_review_to_state_change(
    client: TestClient, run_jobs: Any, seeded_engine: Engine
) -> None:
    failed_interview(client, run_jobs)
    with Session(seeded_engine) as session:
        tasks = session.scalars(
            select(ReviewTask).where(ReviewTask.status == "pending").order_by(ReviewTask.due_at)
        ).all()
        assert tasks, "a failed interview must create remediation without manual action"
        first = tasks[0]
        first.due_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()
        task_id, capability_id = first.id, first.capability_id
        before = session.get(LearnerCapabilityState, (LOCAL_USER_ID, capability_id))
        mastery_before = before.mastery if before else None
    due = client.get("/v1/reviews/queue").json()["due"]
    assert task_id in {task["id"] for task in due}
    assert all(task["reason"] for task in due)
    item = client.post(f"/v1/reviews/tasks/{task_id}/start", json={}).json()
    if item["kind"] == "code":
        from app.corpus.loader import get_corpus

        slug = item["problem_slug"]
        reference = get_corpus().problem(slug).definition.reference_solution
        job = client.post(
            "/v1/executions",
            json={
                "problem_slug": slug,
                "code": reference,
                "kind": "submit",
                "idempotency_key": uuid4().hex,
            },
        ).json()
        run_jobs()
        result = client.post(
            f"/v1/reviews/attempts/{item['attempt_id']}/answer", json={"job_id": job["id"]}
        ).json()
    else:
        result = client.post(
            f"/v1/reviews/attempts/{item['attempt_id']}/answer",
            json={
                "answer": "a contiguous window that grows and shrinks, longest substring",
                "confidence": 4,
            },
        ).json()
    assert result["status"] == "submitted"
    with Session(seeded_engine) as session:
        task = session.get(ReviewTask, task_id)
        assert task is not None and task.status == "completed"
        after = session.get(LearnerCapabilityState, (LOCAL_USER_ID, capability_id))
        assert after is not None and after.mastery != mastery_before
        assert session.get(Capability, capability_id) is not None
