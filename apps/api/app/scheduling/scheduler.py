"""Conservative, deterministic remediation scheduler (MVP; no FSRS/Bayesian models).

A diagnosed weakness produces a progression: recall/recognition -> explain/trace ->
debug/fragment -> full reconstruction -> related transfer -> re-interview. Offsets come from
severity-specific templates; due dates are local-calendar based (tasks become due at
DAY_START_HOUR in the learner's timezone, so DST shifts never move a task to another day).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.models import (
    Capability,
    Exercise,
    InterviewSession,
    Problem,
    ReviewAttempt,
    ReviewTask,
    SolutionView,
    User,
)

logger = structlog.get_logger()

SCHEDULER_VERSION = "scheduler/v1"
DAY_START_HOUR = 4
MAX_CHAIN_STEPS = 6
MAX_LOOKAHEAD_DAYS = 120
ACTIVE = ("pending", "snoozed")
TaskStep = tuple[int, str]

# Templates keyed by capability type, then severity: (day offset, task type).
TEMPLATES: dict[str, dict[str, list[TaskStep]]] = {
    "recognition": {
        "high": [
            (1, "recognition"),
            (3, "explain"),
            (7, "implementation"),
            (14, "transfer"),
            (30, "reinterview"),
        ],
        "medium": [(1, "recognition"), (4, "explain"), (10, "transfer")],
        "low": [(3, "recall"), (10, "transfer")],
    },
    "reasoning": {
        "high": [
            (1, "explain"),
            (3, "trace"),
            (7, "implementation"),
            (14, "transfer"),
            (30, "reinterview"),
        ],
        "medium": [(1, "explain"), (4, "trace"), (10, "transfer")],
        "low": [(3, "explain"), (12, "transfer")],
    },
    "implementation": {
        "high": [
            (1, "trace"),
            (3, "debug"),
            (7, "implementation"),
            (14, "transfer"),
            (30, "reinterview"),
        ],
        "medium": [(2, "debug"), (5, "implementation"), (12, "transfer")],
        "low": [(4, "debug"), (14, "transfer")],
    },
    "debugging": {
        "high": [(1, "debug"), (3, "trace"), (7, "implementation"), (14, "transfer")],
        "medium": [(2, "debug"), (6, "implementation"), (14, "transfer")],
        "low": [(4, "debug")],
    },
    "complexity": {
        "high": [(1, "explain"), (4, "recall"), (10, "transfer")],
        "medium": [(2, "explain"), (8, "recall")],
        "low": [(5, "recall")],
    },
    "transfer": {
        "high": [(3, "explain"), (10, "transfer"), (30, "reinterview")],
        "medium": [(5, "explain"), (14, "transfer")],
        "low": [(14, "transfer")],
    },
    "independence": {
        "high": [(7, "implementation"), (21, "reinterview")],
        "medium": [(14, "reinterview")],
        "low": [],
    },
}
# Which capability type best matches each task type when a chain spans several weaknesses.
PREFERRED_TYPES: dict[str, tuple[str, ...]] = {
    "recall": ("complexity", "recognition", "reasoning"),
    "recognition": ("recognition", "reasoning"),
    "explain": ("reasoning", "complexity", "recognition", "transfer"),
    "trace": ("reasoning", "implementation", "debugging"),
    "debug": ("debugging", "implementation", "reasoning"),
    "code_fragment": ("implementation", "debugging"),
    "implementation": ("implementation", "debugging", "reasoning", "independence"),
    "transfer": ("transfer", "recognition", "reasoning"),
    "reinterview": ("independence", "transfer", "recognition"),
}
TEXT_TYPES = {"recall", "recognition", "explain", "trace"}
CODE_EXERCISE_TYPES = {"debug", "code_fragment"}
PROBLEM_TYPES = {"implementation", "transfer", "reinterview", "key_insight", "pseudocode"}
PROBLEM_SPECIFIC_TYPES = {"implementation", "key_insight", "pseudocode"}
TASK_LABELS = {
    "recall": "quick recall",
    "recognition": "pattern recognition",
    "explain": "explain the idea",
    "trace": "trace by hand",
    "debug": "fix a bug",
    "code_fragment": "finish the code",
    "implementation": "rebuild from scratch",
    "transfer": "related problem",
    "reinterview": "unseen interview",
    "key_insight": "explain the key insight",
    "pseudocode": "reconstruct in pseudocode",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def user_zone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_date(moment: datetime, zone: ZoneInfo) -> date:
    return as_utc(moment).astimezone(zone).date()


def due_at_for(day: date, zone: ZoneInfo) -> datetime:
    """The UTC instant a task becomes due on a local calendar day (DST-safe)."""
    return datetime.combine(day, time(DAY_START_HOUR), tzinfo=zone).astimezone(UTC)


def end_of_local_day(moment: datetime, zone: ZoneInfo) -> datetime:
    day = local_date(moment, zone) + timedelta(days=1)
    return datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)


@dataclass(frozen=True)
class Weak:
    slug: str
    capability_type: str
    severity: str
    confidence: float


@dataclass(frozen=True)
class PlannedTask:
    capability_slug: str
    task_type: str
    offset_days: int
    reason: str


def plan_chain(weaknesses: list[Weak], source_title: str) -> list[PlannedTask]:
    """Merge per-capability templates into one progressive chain for a topic."""
    if not weaknesses:
        return []
    rank = {"high": 0, "medium": 1, "low": 2}
    # The most severe weakness sets the spacing; others only add step types it lacks.
    steps: dict[str, int] = {}
    for weak in sorted(weaknesses, key=lambda item: (rank[item.severity], item.slug)):
        for offset, task_type in TEMPLATES.get(weak.capability_type, {}).get(weak.severity, []):
            steps.setdefault(task_type, offset)
    ordered = sorted(steps.items(), key=lambda item: (item[1], item[0]))[:MAX_CHAIN_STEPS]
    planned: list[PlannedTask] = []
    for task_type, offset in ordered:
        preferred = PREFERRED_TYPES.get(task_type, ())
        candidates = sorted(
            weaknesses,
            key=lambda weak: (
                preferred.index(weak.capability_type)
                if weak.capability_type in preferred
                else len(preferred),
                rank[weak.severity],
                weak.slug,
            ),
        )
        target = candidates[0]
        planned.append(
            PlannedTask(
                capability_slug=target.slug,
                task_type=task_type,
                offset_days=offset,
                reason=f"{target.severity.capitalize()} weakness from {source_title}: "
                f"{TASK_LABELS.get(task_type, task_type)} (day {offset}).",
            )
        )
    return planned


def seen_problem_ids(db: Session, user_id: str) -> set[str]:
    sessions = db.scalars(
        select(InterviewSession.problem_id).where(InterviewSession.user_id == user_id)
    )
    attempts = db.scalars(
        select(ReviewAttempt.problem_id).where(
            ReviewAttempt.user_id == user_id, ReviewAttempt.problem_id.is_not(None)
        )
    )
    viewed = db.scalars(select(SolutionView.problem_id).where(SolutionView.user_id == user_id))
    scheduled = db.scalars(
        select(ReviewTask.problem_id).where(
            ReviewTask.user_id == user_id,
            ReviewTask.problem_id.is_not(None),
            ReviewTask.status.in_(ACTIVE),
        )
    )
    return {item for group in (sessions, attempts, viewed, scheduled) for item in group if item}


def choose_problem(
    db: Session, user_id: str, topic: str, task_type: str, source: Problem | None
) -> Problem | None:
    if task_type in ("implementation", "key_insight", "pseudocode"):
        return source
    seen = seen_problem_ids(db, user_id)
    rows = db.scalars(
        select(Problem).where(Problem.status != "retired").order_by(Problem.slug)
    ).all()
    corpus = get_corpus()
    unseen = [row for row in rows if row.id not in seen and row.slug in corpus.problems]

    def topic_of(row: Problem) -> str:
        return corpus.problems[row.slug].definition.topic

    candidates: list[Problem] = []
    if source is not None:
        candidates += [row for row in unseen if row.transfer_group == source.transfer_group]
        candidates += [row for row in unseen if row.slug in (source.related_slugs or [])]
    candidates += [row for row in unseen if topic_of(row) == topic and row.role == "transfer"]
    candidates += [row for row in unseen if topic_of(row) == topic]
    if task_type == "reinterview":
        # Prefer a different surface story than the transfer step (different group).
        different = [
            row
            for row in candidates
            if source is None or row.transfer_group != source.transfer_group
        ]
        candidates = different or candidates
    return candidates[0] if candidates else None


def choose_exercise(
    db: Session, user_id: str, capability: Capability, task_type: str
) -> Exercise | None:
    recent_cutoff = utcnow() - timedelta(days=7)
    recent = set(
        db.scalars(
            select(ReviewAttempt.exercise_id).where(
                ReviewAttempt.user_id == user_id,
                ReviewAttempt.exercise_id.is_not(None),
                ReviewAttempt.started_at >= recent_cutoff,
            )
        )
    )
    active = set(
        db.scalars(
            select(ReviewTask.exercise_id).where(
                ReviewTask.user_id == user_id,
                ReviewTask.exercise_id.is_not(None),
                ReviewTask.status.in_(ACTIVE),
            )
        )
    )
    topic_prefix = capability.slug.split(".", 1)[0] + "."
    options = db.scalars(
        select(Exercise)
        .join(Capability, Capability.id == Exercise.capability_id)
        .where(Exercise.status != "retired", Capability.slug.like(f"{topic_prefix}%"))
        .order_by(Exercise.source_id)
    ).all()

    def rank(exercise: Exercise) -> tuple[int, int, int, str]:
        return (
            0 if exercise.capability_id == capability.id else 1,
            0 if exercise.exercise_type == task_type else 1,
            1 if exercise.id in recent or exercise.id in active else 0,
            exercise.source_id or "",
        )

    compatible = {
        "recall": {"recall", "recognition", "explain"},
        "recognition": {"recognition", "recall"},
        "explain": {"explain", "recall", "trace"},
        "trace": {"trace", "explain"},
        "debug": {"debug", "code_fragment"},
        "code_fragment": {"code_fragment", "debug"},
    }.get(task_type, {task_type})
    usable = [item for item in options if item.exercise_type in compatible]
    if not usable:
        return None
    best = sorted(usable, key=rank)[0]
    return best


def daily_count(db: Session, user_id: str, due_at: datetime, zone: ZoneInfo) -> int:
    day_start = due_at_for(local_date(due_at, zone), zone) - timedelta(hours=DAY_START_HOUR)
    day_end = day_start + timedelta(days=1)
    return int(
        db.scalar(
            select(func.count())
            .select_from(ReviewTask)
            .where(
                ReviewTask.user_id == user_id,
                ReviewTask.status.in_(ACTIVE),
                ReviewTask.due_at >= day_start,
                ReviewTask.due_at < day_end,
            )
        )
        or 0
    )


def place(db: Session, user: User, day: date, zone: ZoneInfo) -> datetime:
    """Find the first local day at or after `day` with capacity under the daily cap."""
    for extra in range(MAX_LOOKAHEAD_DAYS):
        candidate = due_at_for(day + timedelta(days=extra), zone)
        if daily_count(db, user.id, candidate, zone) < max(1, user.daily_review_cap):
            return candidate
    return due_at_for(day + timedelta(days=MAX_LOOKAHEAD_DAYS), zone)


def create_task(
    db: Session,
    user: User,
    *,
    capability: Capability,
    task_type: str,
    due: datetime,
    reason: str,
    source_type: str,
    source_id: str,
    chain_id: str,
    step: int,
    exercise: Exercise | None,
    problem: Problem | None,
    dedupe_suffix: str = "",
) -> ReviewTask | None:
    dedupe_key = f"{capability.slug}:{task_type}{dedupe_suffix}"
    # One active transfer/re-interview per capability; problem-specific rebuilds are distinct.
    if problem is not None and task_type in PROBLEM_SPECIFIC_TYPES:
        dedupe_key += f":{problem.slug}"
    existing = db.scalar(
        select(ReviewTask).where(
            ReviewTask.user_id == user.id,
            ReviewTask.dedupe_key == dedupe_key,
            ReviewTask.status.in_(ACTIVE),
        )
    )
    now = utcnow()
    if existing is not None:
        if due < as_utc(existing.due_at):
            existing.due_at = due
            existing.reason = reason
            existing.updated_at = now
        return None
    task = ReviewTask(
        user_id=user.id,
        capability_id=capability.id,
        exercise_id=exercise.id if exercise else None,
        problem_id=problem.id if problem else None,
        task_type=task_type,
        status="pending",
        due_at=due,
        source_type=source_type,
        source_id=source_id,
        chain_id=chain_id,
        step=step,
        reason=reason,
        dedupe_key=dedupe_key,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.flush()
    return task


def schedule_chain(
    db: Session,
    user: User,
    planned: list[PlannedTask],
    *,
    source_type: str,
    source_id: str,
    source_problem: Problem | None,
    anchor: datetime | None = None,
) -> list[ReviewTask]:
    zone = user_zone(user)
    anchor_day = local_date(anchor or utcnow(), zone)
    capabilities = {
        row.slug: row
        for row in db.scalars(
            select(Capability).where(
                Capability.slug.in_({item.capability_slug for item in planned})
            )
        )
    }
    chain_id = str(uuid4())
    created: list[ReviewTask] = []
    for index, item in enumerate(planned, start=1):
        capability = capabilities.get(item.capability_slug)
        if capability is None or item.offset_days < 0:
            continue
        topic = capability.slug.split(".", 1)[0]
        exercise = None
        problem = None
        if item.task_type in TEXT_TYPES | CODE_EXERCISE_TYPES:
            exercise = choose_exercise(db, user.id, capability, item.task_type)
            if exercise is None:
                continue
        else:
            corpus_topic = (
                topic
                if topic != "interview"
                else (
                    get_corpus().problems[source_problem.slug].definition.topic
                    if source_problem is not None and source_problem.slug in get_corpus().problems
                    else topic
                )
            )
            problem = choose_problem(db, user.id, corpus_topic, item.task_type, source_problem)
            if problem is None:
                continue
        due = place(db, user, anchor_day + timedelta(days=item.offset_days), zone)
        task = create_task(
            db,
            user,
            capability=capability,
            task_type=item.task_type,
            due=due,
            reason=item.reason,
            source_type=source_type,
            source_id=source_id,
            chain_id=chain_id,
            step=index,
            exercise=exercise,
            problem=problem,
        )
        if task is not None:
            created.append(task)
    logger.info("remediation_scheduled", source=source_type, tasks=len(created))
    return created


def reschedule_after_failure(db: Session, user: User, task: ReviewTask) -> ReviewTask | None:
    """A failed review gets one Rebuild retry the next day; later chain steps stay in place."""
    if task.attempt_count >= 3:
        return None
    capability = db.get(Capability, task.capability_id)
    assert capability is not None
    zone = user_zone(user)
    due = place(db, user, local_date(utcnow(), zone) + timedelta(days=1), zone)
    return create_task(
        db,
        user,
        capability=capability,
        task_type=task.task_type,
        due=due,
        reason=f"Retry after a missed {TASK_LABELS.get(task.task_type, task.task_type)}.",
        source_type="review_retry",
        source_id=task.id,
        chain_id=task.chain_id,
        step=task.step,
        exercise=db.get(Exercise, task.exercise_id) if task.exercise_id else None,
        problem=db.get(Problem, task.problem_id) if task.problem_id else None,
        dedupe_suffix=":retry",
    )
