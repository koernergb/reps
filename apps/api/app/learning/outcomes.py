"""MVP learning-outcome metrics (definitions and denominators in docs/metrics.md).

These are descriptive, per-learner numbers for the local tool. They are not causal claims and
should not be optimized against until the definitions are reviewed (Milestone 11 rule).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnalyticsEvent,
    InterviewEvaluation,
    InterviewEvent,
    InterviewSession,
    ReviewAttempt,
    ReviewTask,
)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def outcome_metrics(db: Session, user_id: str) -> dict[str, Any]:
    sessions = db.scalars(select(InterviewSession).where(InterviewSession.user_id == user_id)).all()
    evaluations = {
        evaluation.session_id: evaluation
        for evaluation in db.scalars(
            select(InterviewEvaluation)
            .where(InterviewEvaluation.user_id == user_id)
            .order_by(InterviewEvaluation.created_at)
        )
    }
    completed = [session for session in sessions if session.id in evaluations]
    activity = sorted(
        _utc(moment)
        for moment in db.scalars(
            select(AnalyticsEvent.occurred_at).where(AnalyticsEvent.user_id == user_id)
        )
    )
    first = activity[0] if activity else None
    weeks: dict[str, int] = defaultdict(int)
    for session in sessions:
        weeks[_utc(session.started_at).strftime("%G-W%V")] += 1
    for attempt in db.scalars(
        select(ReviewAttempt.started_at).where(ReviewAttempt.user_id == user_id)
    ):
        weeks[_utc(attempt).strftime("%G-W%V")] += 1
    hints = [session.hints_used for session in completed]
    failed_submissions = []
    time_to_approach = []
    for session in completed:
        facts = (evaluations[session.id].report or {}).get("facts", {})
        failed_submissions.append(
            max(0, int(facts.get("submissions", 0)) - int(bool(facts.get("passed_hidden"))))
        )
        approach = db.scalar(
            select(InterviewEvent.occurred_at)
            .where(
                InterviewEvent.session_id == session.id,
                InterviewEvent.event_type.in_(("approach_proposed", "approach_changed")),
            )
            .order_by(InterviewEvent.sequence)
            .limit(1)
        )
        if approach is not None:
            time_to_approach.append((_utc(approach) - _utc(session.started_at)).total_seconds())
    now = datetime.now(UTC)
    due_tasks = db.scalars(
        select(ReviewTask).where(
            ReviewTask.user_id == user_id,
            ReviewTask.source_type.in_(("interview", "solution_view", "review_retry")),
            ReviewTask.due_at <= now,
        )
    ).all()
    returned = [task for task in due_tasks if task.status == "completed"]
    transfer_tasks = [task for task in returned if task.task_type in ("transfer", "reinterview")]
    transfer_success = 0
    for task in transfer_tasks:
        attempt = db.scalar(
            select(ReviewAttempt).where(
                ReviewAttempt.task_id == task.id, ReviewAttempt.status == "submitted"
            )
        )
        if attempt is not None and (attempt.correctness or 0) >= 0.8 and attempt.hints_used <= 1:
            transfer_success += 1
    return {
        "activated": bool(completed),
        "first_activity_at": first.isoformat() if first else None,
        "week_2_retained": bool(
            first
            and any(
                first + timedelta(days=7) <= moment < first + timedelta(days=14)
                for moment in activity
            )
        ),
        "sessions_per_week": dict(sorted(weeks.items())),
        "interviews_completed": len(completed),
        "hints_per_problem": round(sum(hints) / len(hints), 2) if hints else None,
        "median_seconds_to_first_approach": sorted(time_to_approach)[len(time_to_approach) // 2]
        if time_to_approach
        else None,
        "failed_submissions_per_interview": round(
            sum(failed_submissions) / len(failed_submissions), 2
        )
        if failed_submissions
        else None,
        "retest_return_rate": round(len(returned) / len(due_tasks), 2) if due_tasks else None,
        "transfer_attempts_after_remediation": len(transfer_tasks),
        "transfer_success_after_remediation": round(transfer_success / len(transfer_tasks), 2)
        if transfer_tasks
        else None,
    }
