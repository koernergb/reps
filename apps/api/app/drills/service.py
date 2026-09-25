from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import track
from app.config import get_settings
from app.corpus.loader import get_corpus
from app.drills.composer import Candidate, compose, describe_mix
from app.errors import ApiError
from app.models import (
    Capability,
    DrillSession,
    Exercise,
    LearnerCapabilityState,
    ReviewAttempt,
    ReviewTask,
    User,
)
from app.reviews.service import estimated_minutes, pending_for_drill, task_view
from app.scheduling.scheduler import create_task
from app.scheduling.scheduler import utcnow as scheduler_now

ONBOARDING_TOPICS = (
    "arrays-hashing",
    "two-pointers",
    "sliding-window",
    "stack",
    "binary-search",
    "linked-list",
    "trees",
    "heap",
    "graphs",
    "dp-1d",
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def gather_candidates(db: Session, user: User) -> list[Candidate]:
    mastery = {
        state.capability_id: state
        for state in db.scalars(
            select(LearnerCapabilityState).where(LearnerCapabilityState.user_id == user.id)
        )
    }
    now = utcnow()
    candidates: list[Candidate] = []
    for task in pending_for_drill(db, user):
        state = mastery.get(task.capability_id)
        overdue = max(0.0, (now - as_utc(task.due_at)).total_seconds() / 86400)
        candidates.append(
            Candidate(
                kind="task",
                key=task.id,
                capability_slug=task.capability.slug,
                topic=task.capability.slug.split(".", 1)[0],
                task_type=task.task_type,
                minutes=estimated_minutes(task),
                priority=10 + 2 * min(overdue, 14) + 4 * (1 - (state.mastery if state else 0)),
                due_at=as_utc(task.due_at),
                reason=task.reason,
                exercise_id=task.exercise_id,
                retry=task.source_type == "review_retry",
            )
        )
    exercises = db.scalars(
        select(Exercise).where(Exercise.status != "retired").order_by(Exercise.source_id)
    ).all()
    by_capability: dict[str, list[Exercise]] = {}
    for exercise in exercises:
        by_capability.setdefault(exercise.capability_id, []).append(exercise)
    recent = set(
        db.scalars(
            select(ReviewAttempt.exercise_id).where(
                ReviewAttempt.user_id == user.id, ReviewAttempt.exercise_id.is_not(None)
            )
        )
    )
    capabilities = {row.id: row for row in db.scalars(select(Capability))}
    weak_states = sorted(
        (
            state
            for state in mastery.values()
            if state.band in ("Weak", "Developing") and state.evidence_count > 0
        ),
        key=lambda state: (state.mastery, state.capability_id),
    )
    for state in weak_states:
        options = [
            item for item in by_capability.get(state.capability_id, []) if item.id not in recent
        ]
        if not options:
            continue
        exercise = options[0]
        capability = capabilities[state.capability_id]
        candidates.append(
            Candidate(
                kind="practice",
                key=f"practice:{exercise.id}",
                capability_slug=capability.slug,
                topic=capability.slug.split(".", 1)[0],
                task_type=exercise.exercise_type,
                minutes=exercise.estimated_minutes,
                priority=5 + 4 * (1 - state.mastery),
                due_at=None,
                reason=f"Practice for a {state.band.lower()} area: {capability.name}.",
                exercise_id=exercise.id,
            )
        )
    if not mastery:
        for index, topic in enumerate(ONBOARDING_TOPICS):
            options = [
                item
                for item in exercises
                if capabilities[item.capability_id].slug == f"{topic}.recognition"
                and item.exercise_type in ("recall", "recognition")
            ]
            if not options:
                continue
            exercise = options[0]
            candidates.append(
                Candidate(
                    kind="onboarding",
                    key=f"practice:{exercise.id}",
                    capability_slug=f"{topic}.recognition",
                    topic=topic,
                    task_type=exercise.exercise_type,
                    minutes=exercise.estimated_minutes,
                    priority=1 - index * 0.01,
                    due_at=None,
                    reason="Getting started: a quick recognition check to calibrate your plan.",
                    exercise_id=exercise.id,
                )
            )
    return candidates


def create_drill(db: Session, user: User, budget_minutes: int) -> DrillSession:
    if not get_settings().feature_drills:
        raise ApiError(503, "drills_disabled", "Drills are currently disabled.")
    if not 5 <= budget_minutes <= 30:
        raise ApiError(422, "invalid_budget", "Choose a budget between 5 and 30 minutes.")
    active = db.scalar(
        select(DrillSession).where(
            DrillSession.user_id == user.id, DrillSession.status.in_(("active", "paused"))
        )
    )
    if active is not None:
        return active
    drill = DrillSession(
        user_id=user.id,
        budget_minutes=budget_minutes,
        status="active",
        plan=[],
        started_at=utcnow(),
    )
    db.add(drill)
    db.flush()
    chosen = compose(gather_candidates(db, user), budget_minutes)
    plan: list[dict[str, Any]] = []
    capabilities = {row.slug: row for row in db.scalars(select(Capability))}
    for item in chosen:
        task_id = item.key
        if item.kind in ("practice", "onboarding"):
            exercise = db.get(Exercise, item.exercise_id) if item.exercise_id else None
            task = create_task(
                db,
                user,
                capability=capabilities[item.capability_slug],
                task_type=item.task_type,
                due=scheduler_now(),
                reason=item.reason,
                source_type="drill",
                source_id=drill.id,
                chain_id=drill.id,
                step=len(plan) + 1,
                exercise=exercise,
                problem=None,
                dedupe_suffix=f":drill:{drill.id}",
            )
            if task is None:
                continue
            task_id = task.id
        plan.append(
            {
                "task_id": task_id,
                "kind": item.kind,
                "task_type": item.task_type,
                "capability_slug": item.capability_slug,
                "topic": item.topic,
                "minutes": item.minutes,
                "reason": item.reason,
            }
        )
    drill.plan = plan
    drill.planned_minutes = round(sum(item["minutes"] for item in plan), 1)
    track(
        db,
        user.id,
        "drill_started",
        {
            "budget_minutes": budget_minutes,
            "items": len(plan),
            "planned_minutes": drill.planned_minutes,
        },
    )
    db.commit()
    return drill


def owned_drill(db: Session, user: User, drill_id: str) -> DrillSession:
    drill = db.get(DrillSession, drill_id)
    if drill is None or drill.user_id != user.id:
        raise ApiError(404, "drill_not_found", "Drill not found.")
    return drill


def drill_view(db: Session, drill: DrillSession) -> dict[str, Any]:
    items = []
    completed = 0
    for index, item in enumerate(drill.plan):
        task = db.get(ReviewTask, item["task_id"])
        attempt = db.scalar(
            select(ReviewAttempt)
            .where(ReviewAttempt.task_id == item["task_id"])
            .order_by(ReviewAttempt.started_at.desc())
            .limit(1)
        )
        status = (
            "done"
            if attempt is not None and attempt.status == "submitted"
            else "skipped"
            if task is not None and task.status in ("skipped", "invalidated")
            else "in_progress"
            if attempt is not None
            else "pending"
        )
        if status in ("done", "skipped"):
            completed += 1
        feedback = (attempt.evaluation or {}).get("feedback") if attempt else None
        items.append(
            {
                "index": index,
                **item,
                "status": status,
                "band": feedback.get("band") if feedback else None,
                "task": task_view(db, task) if task else None,
            }
        )
    current = next(
        (item["index"] for item in items if item["status"] not in ("done", "skipped")), None
    )
    return {
        "id": drill.id,
        "status": drill.status,
        "budget_minutes": drill.budget_minutes,
        "planned_minutes": drill.planned_minutes,
        "mix": describe_mix(
            [
                Candidate(
                    kind=item["kind"],
                    key=item["task_id"],
                    capability_slug=item["capability_slug"],
                    topic=item["topic"],
                    task_type=item["task_type"],
                    minutes=item["minutes"],
                    priority=0,
                    due_at=None,
                    reason=item["reason"],
                )
                for item in drill.plan
            ],
            {topic.slug: topic.name for topic in get_corpus().taxonomy.topics},
        ),
        "items": items,
        "completed_items": completed,
        "current_index": current,
        "started_at": as_utc(drill.started_at).isoformat(),
        "completed_at": as_utc(drill.completed_at).isoformat() if drill.completed_at else None,
    }


def set_status(db: Session, user: User, drill: DrillSession, action: str) -> DrillSession:
    now = utcnow()
    if drill.status in ("completed", "abandoned"):
        return drill
    view = drill_view(db, drill)
    if action == "pause":
        drill.status = "paused"
        drill.paused_at = now
    elif action == "resume":
        drill.status = "active"
        drill.paused_at = None
    elif action in ("complete", "abandon"):
        drill.status = "completed" if action == "complete" else "abandoned"
        drill.completed_at = now
        # Practice items created for this drill disappear if they were never started.
        for item in view["items"]:
            if item["kind"] in ("practice", "onboarding") and item["status"] == "pending":
                task = db.get(ReviewTask, item["task_id"])
                if task is not None and task.status in ("pending", "snoozed"):
                    task.status = "invalidated"
                    task.updated_at = now
        actual = round((now - as_utc(drill.started_at)).total_seconds() / 60, 1)
        if action == "complete":
            track(
                db,
                user.id,
                "drill_completed",
                {
                    "items": len(drill.plan),
                    "completed": view["completed_items"],
                    "planned_minutes": drill.planned_minutes,
                    "actual_minutes": actual,
                },
            )
        else:
            track(
                db,
                user.id,
                "drill_abandoned",
                {
                    "items": len(drill.plan),
                    "completed": view["completed_items"],
                    "abandon_index": view["current_index"]
                    if view["current_index"] is not None
                    else -1,
                },
            )
    else:
        raise ApiError(422, "invalid_action", "Unknown drill action.")
    db.commit()
    return drill
