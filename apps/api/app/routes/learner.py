from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.analytics import track
from app.deps import SessionDependency, UserDependency
from app.learning.evidence import rebuild_user_state
from app.learning.outcomes import outcome_metrics
from app.models import (
    Capability,
    CapabilityEvidence,
    InterviewSession,
    LearnerCapabilityState,
    Problem,
    ReviewTask,
    Topic,
)
from app.reviews.service import queue

router = APIRouter(prefix="/v1/learner", tags=["learner"])


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


@router.get("/capabilities")
def capabilities(
    db: SessionDependency,
    user: UserDependency,
    topic: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        select(LearnerCapabilityState, Capability, Topic)
        .join(Capability, Capability.id == LearnerCapabilityState.capability_id)
        .join(Topic, Topic.id == Capability.topic_id)
        .where(LearnerCapabilityState.user_id == user.id, LearnerCapabilityState.evidence_count > 0)
    )
    if topic:
        query = query.where(Topic.slug == topic)
    rows = db.execute(query.order_by(LearnerCapabilityState.mastery)).all()
    return [
        {
            "slug": capability.slug,
            "name": capability.name,
            "type": capability.capability_type,
            "topic": {"slug": topic_row.slug, "name": topic_row.name},
            "band": state.band,
            "explanation": state.explanation,
            "evidence_count": state.evidence_count,
            "confidence": "low"
            if state.confidence < 0.4
            else "medium"
            if state.confidence < 0.75
            else "high",
            "last_reviewed_at": iso(state.last_reviewed_at),
            "next_review_at": iso(state.next_review_at),
        }
        for state, capability, topic_row in rows
    ]


@router.get("/capabilities/{slug}/evidence")
def capability_evidence(
    slug: str,
    db: SessionDependency,
    user: UserDependency,
    source_type: str | None = None,
    days: int | None = Query(default=None, ge=1, le=3650),
) -> list[dict[str, Any]]:
    query = (
        select(CapabilityEvidence, Problem.title)
        .join(Capability, Capability.id == CapabilityEvidence.capability_id)
        .outerjoin(Problem, Problem.id == CapabilityEvidence.problem_id)
        .where(CapabilityEvidence.user_id == user.id, Capability.slug == slug)
    )
    if source_type:
        query = query.where(CapabilityEvidence.source_type == source_type)
    if days:
        query = query.where(
            CapabilityEvidence.occurred_at >= datetime.now(UTC) - timedelta(days=days)
        )
    rows = db.execute(query.order_by(CapabilityEvidence.occurred_at.desc()).limit(200)).all()
    return [
        {
            "id": row.id,
            "occurred_at": iso(row.occurred_at),
            "source_type": row.source_type,
            "source_id": row.source_id,
            "exercise_type": row.exercise_type,
            "problem_title": title,
            "outcome": "success" if row.score >= 0.7 else "partial" if row.score >= 0.4 else "miss",
            "hint_level": row.hint_level,
            "assisted": row.assisted,
            "transfer": row.transfer,
            "repeat_exposure": row.repeat_exposure,
            "excluded": row.excluded,
            "explanation": row.explanation,
        }
        for row, title in rows
    ]


@router.post("/rebuild")
def rebuild(db: SessionDependency, user: UserDependency) -> dict[str, int]:
    count = rebuild_user_state(db, user.id)
    track(db, user.id, "state_rebuilt", {"capabilities": count})
    db.commit()
    return {"capabilities": count}


@router.get("/dashboard")
def dashboard(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    review_queue = queue(db, user)
    weak = capabilities(db, user)
    recent = db.execute(
        select(InterviewSession, Problem.title)
        .join(Problem, Problem.id == InterviewSession.problem_id)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.started_at.desc())
        .limit(5)
    ).all()
    topic_rows = db.execute(
        select(Topic.slug, Topic.name, LearnerCapabilityState.mastery, LearnerCapabilityState.band)
        .join(Capability, Capability.topic_id == Topic.id)
        .join(LearnerCapabilityState, LearnerCapabilityState.capability_id == Capability.id)
        .where(LearnerCapabilityState.user_id == user.id, LearnerCapabilityState.evidence_count > 0)
    ).all()
    topics: dict[str, dict[str, Any]] = {}
    for slug, name, mastery, band in topic_rows:
        entry = topics.setdefault(slug, {"slug": slug, "name": name, "bands": {}, "masteries": []})
        entry["bands"][band] = entry["bands"].get(band, 0) + 1
        entry["masteries"].append(mastery)
    patterns = []
    for entry in topics.values():
        average = sum(entry["masteries"]) / len(entry["masteries"])
        band = (
            "Weak"
            if average < 0.35
            else "Developing"
            if average < 0.6
            else "Reliable"
            if average < 0.8
            else "Strong"
        )
        patterns.append(
            {"slug": entry["slug"], "name": entry["name"], "band": band, "bands": entry["bands"]}
        )
    completed_tasks = db.scalars(
        select(ReviewTask.id).where(ReviewTask.user_id == user.id, ReviewTask.status == "completed")
    ).all()
    return {
        "due_count": len(review_queue["due"]),
        "due": review_queue["due"][:6],
        "upcoming": review_queue["upcoming"][:6],
        "weak_capabilities": [item for item in weak if item["band"] in ("Weak", "Developing")][:6],
        "patterns": sorted(patterns, key=lambda item: item["name"]),
        "recent_interviews": [
            {
                "id": interview.id,
                "problem_title": title,
                "mode": interview.mode,
                "state": interview.state,
                "result": (interview.evaluation or {}).get("result") or interview.result,
                "started_at": interview.started_at.isoformat(),
            }
            for interview, title in recent
        ],
        "reviews_completed": len(completed_tasks),
    }


@router.get("/metrics")
def learning_metrics(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return outcome_metrics(db, user.id)
