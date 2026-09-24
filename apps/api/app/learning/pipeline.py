"""Glue between evaluation, the learner model, scheduling, and analytics."""

from __future__ import annotations

from collections import defaultdict

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import track
from app.config import get_settings
from app.evaluation.schemas import Report
from app.learning.evidence import interview_evidence, recompute_many
from app.models import (
    Capability,
    InterviewEvaluation,
    InterviewSession,
    Problem,
    ReviewAttempt,
    ReviewTask,
    User,
)
from app.scheduling.scheduler import PlannedTask, Weak, plan_chain, schedule_chain, utcnow

logger = structlog.get_logger()
MIN_SCHEDULING_CONFIDENCE = 0.3


def apply_evaluation(db: Session, evaluation: InterviewEvaluation) -> None:
    interview = db.get(InterviewSession, evaluation.session_id)
    assert interview is not None
    user = db.get(User, interview.user_id)
    assert user is not None
    touched = interview_evidence(db, evaluation)
    recompute_many(db, user.id, touched)
    complete_linked_attempts(db, interview, evaluation)
    report = Report.model_validate(evaluation.report)
    if get_settings().feature_scheduling and evaluation.status != "failed":
        schedule_from_report(db, user, interview, report)
    track(
        db,
        user.id,
        "interview_evaluated",
        {
            "mode": interview.mode,
            "result": report.facts.result,
            "hints_used": report.facts.hints_used,
            "weakness_count": len(report.weaknesses),
            "evaluator": evaluation.evaluator,
            "status": evaluation.status,
        },
    )
    db.commit()


def schedule_from_report(
    db: Session, user: User, interview: InterviewSession, report: Report
) -> list[ReviewTask]:
    problem = db.get(Problem, interview.problem_id)
    types = {
        slug: capability_type
        for slug, capability_type in db.execute(
            select(Capability.slug, Capability.capability_type)
        ).tuples()
    }
    by_topic: dict[str, list[Weak]] = defaultdict(list)
    for weakness in report.weaknesses:
        # Low-confidence interpretation must not create large workloads; facts always count.
        if weakness.source != "facts" and weakness.confidence < MIN_SCHEDULING_CONFIDENCE:
            continue
        if weakness.capability.startswith("interview.") and weakness.capability not in (
            "interview.independence",
        ):
            continue
        topic = weakness.capability.split(".", 1)[0]
        capability_type = types.get(weakness.capability)
        if capability_type is None:
            continue
        by_topic[topic].append(
            Weak(weakness.capability, capability_type, weakness.severity, weakness.confidence)
        )
    created: list[ReviewTask] = []
    title = problem.title if problem else "an interview"
    for weaknesses in by_topic.values():
        planned = plan_chain(weaknesses, title)
        created += schedule_chain(
            db,
            user,
            planned,
            source_type="interview",
            source_id=interview.id,
            source_problem=problem,
            anchor=interview.completed_at or utcnow(),
        )
    if created:
        track(db, user.id, "remediation_scheduled", {"tasks": len(created), "source": "interview"})
    return created


def complete_linked_attempts(
    db: Session, interview: InterviewSession, evaluation: InterviewEvaluation
) -> None:
    """Close review attempts (transfer/re-interview tasks) that launched this interview."""
    report = Report.model_validate(evaluation.report)
    attempts = db.scalars(
        select(ReviewAttempt).where(
            ReviewAttempt.user_id == interview.user_id, ReviewAttempt.status == "in_progress"
        )
    ).all()
    for attempt in attempts:
        if (attempt.evaluation or {}).get("interview_session_id") != interview.id:
            continue
        attempt.status = "submitted"
        attempt.completed_at = utcnow()
        attempt.correctness = (
            1.0
            if report.facts.passed_hidden
            else (0.6 * report.facts.best_hidden_passed / max(1, report.facts.hidden_total))
        )
        attempt.hints_used = report.facts.hints_used
        attempt.evaluation = {
            **(attempt.evaluation or {}),
            "result": report.facts.result,
            "evaluation_id": evaluation.id,
        }
        if attempt.task_id:
            task = db.get(ReviewTask, attempt.task_id)
            if task is not None and task.status in ("pending", "snoozed"):
                task.status = "completed"
                task.completed_at = utcnow()
                task.updated_at = utcnow()


SOLUTION_CAPABILITY = {
    "key_insight": "invariant",
    "pseudocode": "invariant",
    "implementation": "implementation",
    "transfer": "transfer",
    "reinterview": "transfer",
}
SOLUTION_CHAIN: list[tuple[int, str, str]] = [
    (0, "key_insight", "Explain the key insight without looking at the solution."),
    (1, "pseudocode", "Reconstruct the approach in pseudocode."),
    (3, "implementation", "Implement it from memory."),
    (10, "transfer", "Solve a related problem."),
    (21, "reinterview", "Solve an unseen problem with a related structure."),
]


def schedule_solution_view(
    db: Session, user: User, problem: Problem, source_id: str
) -> list[ReviewTask]:
    topic = problem.topic.slug if problem.topic else None
    if topic is None:
        return []
    planned = [
        PlannedTask(
            capability_slug=f"{topic}.{SOLUTION_CAPABILITY[task_type]}",
            task_type=task_type,
            offset_days=offset,
            reason=f"You viewed the solution to {problem.title}. {text}",
        )
        for offset, task_type, text in SOLUTION_CHAIN
    ]
    return schedule_chain(
        db,
        user,
        planned,
        source_type="solution_view",
        source_id=source_id,
        source_problem=problem,
    )
