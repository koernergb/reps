"""Evidence persistence and aggregate recomputation.

Evidence is appended (or upserted by its dedupe key, which makes delivery idempotent) before the
aggregate changes, and aggregates are always recomputed from the full evidence list.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.evaluation.schemas import Report
from app.learning.model import Evidence, compute_state
from app.models import (
    Capability,
    CapabilityEvidence,
    InterviewEvaluation,
    InterviewSession,
    LearnerCapabilityState,
    Problem,
    ProblemCapability,
    SolutionView,
)

SEVERITY_CAP = {"high": 0.2, "medium": 0.45, "low": 0.7}


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def upsert_evidence(
    db: Session,
    *,
    user_id: str,
    capability_id: str,
    source_type: str,
    source_id: str,
    dedupe_key: str,
    occurred_at: datetime,
    score: float,
    confidence: float,
    hint_level: int,
    exercise_type: str,
    explanation: str,
    problem_id: str | None = None,
    assisted: bool = False,
    transfer: bool = False,
    repeat_exposure: bool = False,
) -> CapabilityEvidence:
    row = db.scalar(
        select(CapabilityEvidence).where(
            CapabilityEvidence.user_id == user_id, CapabilityEvidence.dedupe_key == dedupe_key
        )
    )
    values: dict[str, Any] = {
        "capability_id": capability_id,
        "source_type": source_type,
        "source_id": source_id,
        "problem_id": problem_id,
        "occurred_at": occurred_at,
        "score": round(max(0.0, min(1.0, score)), 4),
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "hint_level": max(0, min(5, hint_level)),
        "exercise_type": exercise_type,
        "assisted": assisted,
        "transfer": transfer,
        "repeat_exposure": repeat_exposure,
        "explanation": explanation[:500],
    }
    if row is None:
        row = CapabilityEvidence(
            user_id=user_id, dedupe_key=dedupe_key, created_at=utcnow(), **values
        )
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    db.flush()
    return row


def recompute_capability(db: Session, user_id: str, capability_id: str) -> LearnerCapabilityState:
    capability = db.get(Capability, capability_id)
    assert capability is not None
    rows = db.scalars(
        select(CapabilityEvidence).where(
            CapabilityEvidence.user_id == user_id,
            CapabilityEvidence.capability_id == capability_id,
        )
    ).all()
    state = compute_state(
        [
            Evidence(
                occurred_at=as_utc(row.occurred_at),
                score=row.score,
                confidence=row.confidence,
                hint_level=row.hint_level,
                exercise_type=row.exercise_type,
                assisted=row.assisted,
                transfer=row.transfer,
                repeat_exposure=row.repeat_exposure,
                excluded=row.excluded,
            )
            for row in rows
        ],
        capability.capability_type,
    )
    aggregate = db.get(LearnerCapabilityState, (user_id, capability_id))
    if aggregate is None:
        aggregate = LearnerCapabilityState(user_id=user_id, capability_id=capability_id)
        db.add(aggregate)
    aggregate.mastery = state.mastery
    aggregate.stability = state.stability_days
    aggregate.difficulty = 0.5
    aggregate.last_reviewed_at = state.last_reviewed_at
    aggregate.next_review_at = state.next_review_at
    aggregate.evidence_count = state.evidence_count
    aggregate.band = state.band
    aggregate.confidence = state.confidence
    aggregate.explanation = state.explanation
    db.flush()
    return aggregate


def recompute_many(db: Session, user_id: str, capability_ids: Iterable[str]) -> None:
    for capability_id in sorted(set(capability_ids)):
        recompute_capability(db, user_id, capability_id)


def rebuild_user_state(db: Session, user_id: str) -> int:
    """Delete every aggregate and replay all evidence."""
    db.execute(delete(LearnerCapabilityState).where(LearnerCapabilityState.user_id == user_id))
    capability_ids = set(
        db.scalars(
            select(CapabilityEvidence.capability_id).where(CapabilityEvidence.user_id == user_id)
        )
    )
    recompute_many(db, user_id, capability_ids)
    db.commit()
    return len(capability_ids)


def prior_exposure(
    db: Session, user_id: str, problem_id: str, before: datetime, exclude_session: str
) -> bool:
    """True when the learner has seen this problem (or its solution) before this attempt."""
    earlier_session = db.scalar(
        select(InterviewSession.id).where(
            InterviewSession.user_id == user_id,
            InterviewSession.problem_id == problem_id,
            InterviewSession.id != exclude_session,
            InterviewSession.started_at < before,
        )
    )
    viewed = db.scalar(
        select(SolutionView.id).where(
            SolutionView.user_id == user_id,
            SolutionView.problem_id == problem_id,
            SolutionView.viewed_at < before,
        )
    )
    return earlier_session is not None or viewed is not None


def interview_evidence(db: Session, evaluation: InterviewEvaluation) -> set[str]:
    """Translate an evaluation into per-capability evidence. Returns touched capability ids."""
    report = Report.model_validate(evaluation.report)
    facts = report.facts
    interview = db.get(InterviewSession, evaluation.session_id)
    assert interview is not None
    problem = db.get(Problem, interview.problem_id)
    assert problem is not None
    occurred = as_utc(interview.completed_at or evaluation.created_at)
    repeat = prior_exposure(
        db, interview.user_id, problem.id, as_utc(interview.started_at), interview.id
    )
    exercise_type = "mock_interview" if interview.mode == "mock" else "interview"
    transfer_problem = problem.role == "transfer" and not repeat
    weak_by_capability = {item.capability: item for item in report.weaknesses}
    capability_ids = {
        slug: capability_id
        for slug, capability_id in db.execute(select(Capability.slug, Capability.id)).tuples()
    }
    if facts.passed_hidden:
        base = 1.0
    elif facts.hidden_total:
        base = 0.6 * facts.best_hidden_passed / facts.hidden_total
    else:
        base = 0.0
    signals: dict[str, tuple[float, float, str]] = {}
    links = db.execute(
        select(Capability.slug, ProblemCapability.weight)
        .join(ProblemCapability, ProblemCapability.capability_id == Capability.id)
        .where(ProblemCapability.problem_id == problem.id)
    ).tuples()
    for slug, weight in links:
        suffix = slug.split(".", 1)[1]
        score = base
        if suffix == "complexity":
            if facts.complexity_time_correct is None:
                if slug not in weak_by_capability:
                    continue
                score = base * 0.5
            else:
                score = 0.5 * bool(facts.complexity_time_correct) + 0.5 * bool(
                    facts.complexity_space_correct
                )
        if suffix == "recognition":
            score = min(score, 1.0 if facts.approach_before_code else 0.8)
        if suffix == "transfer" and not transfer_problem:
            continue
        confidence = max(0.25, min(1.0, report.confidence + 0.25 * weight))
        signals[slug] = (score, confidence, f"{facts.result.replace('_', ' ')} on {problem.title}")
    independence = 0.1 if facts.solution_viewed else max(0.0, 1 - 0.18 * facts.max_hint_level)
    signals["interview.independence"] = (
        independence if facts.passed_hidden or facts.max_hint_level else 0.5,
        0.8,
        f"{facts.hints_used} hint(s) on {problem.title}",
    )
    signals["interview.communication"] = (
        report.communication.rating / 4,
        min(report.confidence, 0.6),
        report.communication.summary[:120],
    )
    if facts.submissions or facts.runs:
        signals["interview.testing"] = (
            0.8 if facts.runs and facts.passed_hidden else 0.5 if facts.runs else 0.3,
            0.5,
            f"{facts.runs} run(s), {facts.submissions} submission(s)",
        )
    if facts.clarifications_asked:
        signals["interview.clarification"] = (0.8, 0.5, "asked clarifying questions")
    for slug, weakness in weak_by_capability.items():
        score, confidence, _ = signals.get(slug, (base, report.confidence, ""))
        cap = SEVERITY_CAP[weakness.severity]
        signals[slug] = (
            min(score, cap),
            max(0.2, min(confidence, weakness.confidence)),
            weakness.explanation,
        )
    touched: set[str] = set()
    for slug, (score, confidence, explanation) in signals.items():
        capability_id = capability_ids.get(slug)
        if capability_id is None:
            continue
        low_confidence = evaluation.status != "completed"
        upsert_evidence(
            db,
            user_id=interview.user_id,
            capability_id=capability_id,
            source_type="interview",
            source_id=interview.id,
            problem_id=problem.id,
            dedupe_key=f"interview:{interview.id}:{slug}",
            occurred_at=occurred,
            score=score,
            confidence=confidence * (0.7 if low_confidence else 1.0),
            hint_level=facts.max_hint_level,
            exercise_type=exercise_type,
            explanation=explanation,
            assisted=facts.solution_viewed,
            transfer=transfer_problem and slug.endswith(".transfer"),
            repeat_exposure=repeat,
        )
        touched.add(capability_id)
    return touched
