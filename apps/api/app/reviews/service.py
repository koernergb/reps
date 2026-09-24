"""Retrieve / Coach / Rebuild review flows over scheduled tasks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analytics import track
from app.corpus.loader import LoadedExercise, get_corpus
from app.errors import ApiError
from app.learning.evidence import recompute_capability, upsert_evidence
from app.llm.provider import build_provider
from app.models import (
    Capability,
    ExecutionJob,
    Exercise,
    HintLog,
    Problem,
    ReviewAttempt,
    ReviewTask,
    SolutionView,
    User,
)
from app.reviews.grading import AnswerGrade, Rubric, grade
from app.scheduling.scheduler import (
    ACTIVE,
    TASK_LABELS,
    end_of_local_day,
    reschedule_after_failure,
    user_zone,
)

CODE_TASKS = {"debug", "code_fragment", "implementation", "transfer"}
INTERVIEW_TASKS = {"reinterview"}
HIDE_TOPIC = {"transfer", "reinterview", "recognition"}
ESTIMATED_MINUTES = {
    "implementation": 12.0,
    "transfer": 15.0,
    "reinterview": 40.0,
    "key_insight": 2.0,
    "pseudocode": 4.0,
}

provider_factory = build_provider


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def owned_task(db: Session, user: User, task_id: str) -> ReviewTask:
    task = db.get(ReviewTask, task_id)
    if task is None or task.user_id != user.id:
        raise ApiError(404, "task_not_found", "Review task not found.")
    return task


def owned_attempt(db: Session, user: User, attempt_id: str) -> ReviewAttempt:
    attempt = db.get(ReviewAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise ApiError(404, "attempt_not_found", "Review attempt not found.")
    return attempt


def corpus_exercise(exercise: Exercise | None) -> LoadedExercise | None:
    if exercise is None or not exercise.source_id:
        return None
    return get_corpus().exercises.get(exercise.source_id)


def estimated_minutes(task: ReviewTask) -> float:
    if task.exercise is not None:
        return float(task.exercise.estimated_minutes)
    return ESTIMATED_MINUTES.get(task.task_type, 5.0)


def task_view(db: Session, task: ReviewTask) -> dict[str, Any]:
    capability = task.capability
    problem = task.problem
    return {
        "id": task.id,
        "task_type": task.task_type,
        "label": TASK_LABELS.get(task.task_type, task.task_type),
        "status": task.status,
        "due_at": as_utc(task.due_at).isoformat(),
        "reason": task.reason,
        "capability": {"slug": capability.slug, "name": capability.name},
        "estimated_minutes": estimated_minutes(task),
        "problem_slug": problem.slug if problem else None,
        "problem_title": None if task.task_type in HIDE_TOPIC or problem is None else problem.title,
        "source_type": task.source_type,
        "step": task.step,
        "attempt_count": task.attempt_count,
    }


def queue(db: Session, user: User, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    zone = user_zone(user)
    horizon = end_of_local_day(now, zone)
    rows = db.scalars(
        select(ReviewTask)
        .where(ReviewTask.user_id == user.id, ReviewTask.status.in_(ACTIVE))
        .order_by(ReviewTask.due_at, ReviewTask.id)
    ).all()
    due, upcoming = [], []
    for task in rows:
        if task.status == "snoozed" and task.snoozed_until and as_utc(task.snoozed_until) > now:
            upcoming.append(task_view(db, task))
        elif as_utc(task.due_at) < horizon:
            due.append(task_view(db, task))
        else:
            upcoming.append(task_view(db, task))
    return {"due": due, "upcoming": upcoming[:30], "server_now": now.isoformat()}


def item_view(db: Session, attempt: ReviewAttempt, task: ReviewTask | None) -> dict[str, Any]:
    exercise = db.get(Exercise, attempt.exercise_id) if attempt.exercise_id else None
    loaded = corpus_exercise(exercise)
    problem = db.get(Problem, attempt.problem_id) if attempt.problem_id else None
    task_type = task.task_type if task else (exercise.exercise_type if exercise else "recall")
    prompt = (
        exercise.prompt
        if exercise
        else {
            "key_insight": "Without looking at the solution, explain the key insight that makes "
            "this problem efficient. Why does it work?",
            "pseudocode": "Reconstruct the approach in pseudocode (plain steps, no need for exact "
            "Python). Include the data structures and the main loop.",
            "implementation": "Implement the solution from scratch, then submit it.",
            "transfer": "Solve this problem. It may use a technique you have practiced recently.",
            "reinterview": "Complete this interview without hints if you can.",
        }.get(task_type, "Answer the question.")
    )
    hints_total = len(loaded.definition.hints) + 1 if loaded else (5 if problem else 1)
    starter = (loaded.starter_code if loaded else None) or (
        problem.starter_code if problem and task_type in CODE_TASKS else None
    )
    return {
        "attempt_id": attempt.id,
        "task": task_view(db, task) if task else None,
        "task_type": task_type,
        "mode": attempt.mode,
        "status": attempt.status,
        "prompt": prompt,
        "kind": "code"
        if task_type in CODE_TASKS
        else "interview"
        if task_type in INTERVIEW_TASKS
        else "text",
        "problem_slug": problem.slug if problem else None,
        "starter_code": starter,
        "hints_used": attempt.hints_used,
        "hints_total": hints_total,
        "hints": [
            hint.hint_text
            for hint in db.scalars(
                select(HintLog)
                .where(HintLog.review_attempt_id == attempt.id)
                .order_by(HintLog.hint_level)
            )
        ],
        "result": attempt.evaluation.get("feedback") if attempt.status == "submitted" else None,
        "interview_session_id": (attempt.evaluation or {}).get("interview_session_id"),
    }


def start(
    db: Session, user: User, task_id: str, drill_session_id: str | None = None
) -> dict[str, Any]:
    task = owned_task(db, user, task_id)
    if task.status not in ACTIVE:
        raise ApiError(409, "task_closed", "This review is no longer active.")
    existing = db.scalar(
        select(ReviewAttempt).where(
            ReviewAttempt.task_id == task.id,
            ReviewAttempt.user_id == user.id,
            ReviewAttempt.status == "in_progress",
        )
    )
    if existing is not None:
        return item_view(db, existing, task)
    attempt = ReviewAttempt(
        user_id=user.id,
        exercise_id=task.exercise_id,
        problem_id=task.problem_id or (task.exercise.problem_id if task.exercise else None),
        task_id=task.id,
        drill_session_id=drill_session_id,
        mode="retrieve",
        status="in_progress",
        started_at=utcnow(),
        hints_used=0,
        evaluation={},
    )
    db.add(attempt)
    db.flush()
    if task.task_type in INTERVIEW_TASKS and task.problem is not None:
        from app.interview.service import start_session

        interview = start_session(db, user, task.problem.slug, "mock")
        attempt.evaluation = {"interview_session_id": interview.id}
    task.attempt_count += 1
    task.updated_at = utcnow()
    db.commit()
    return item_view(db, attempt, task)


def request_hint(db: Session, user: User, attempt_id: str) -> dict[str, Any]:
    attempt = owned_attempt(db, user, attempt_id)
    if attempt.status != "in_progress":
        raise ApiError(409, "attempt_closed", "This attempt is already finished.")
    task = db.get(ReviewTask, attempt.task_id) if attempt.task_id else None
    exercise = db.get(Exercise, attempt.exercise_id) if attempt.exercise_id else None
    loaded = corpus_exercise(exercise)
    problem = db.get(Problem, attempt.problem_id) if attempt.problem_id else None
    level = attempt.hints_used + 1
    if loaded is not None:
        ladder = [
            *loaded.definition.hints,
            f"Full explanation: {loaded.definition.reference_answer}",
        ]
    elif problem is not None and problem.evaluator is not None:
        ladder = list(problem.evaluator.hints)
    else:
        ladder = []
    if level > len(ladder):
        raise ApiError(409, "hint_unavailable", "No more hints for this item.")
    text = ladder[level - 1]
    attempt.hints_used = level
    # Coach mode begins at the first hint; a full explanation means the answer was shown.
    attempt.mode = "coach"
    if level == len(ladder):
        attempt.evaluation = {**(attempt.evaluation or {}), "assisted": True}
    capability = db.get(Capability, task.capability_id) if task else None
    db.add(
        HintLog(
            user_id=user.id,
            exercise_id=attempt.exercise_id,
            review_attempt_id=attempt.id,
            hint_level=min(5, level),
            hint_text=text,
            occurred_at=utcnow(),
            capability_tags=[capability.slug] if capability else [],
        )
    )
    db.commit()
    return item_view(db, attempt, task)


def rubric_for(attempt: ReviewAttempt, db: Session, task: ReviewTask | None) -> Rubric:
    exercise = db.get(Exercise, attempt.exercise_id) if attempt.exercise_id else None
    loaded = corpus_exercise(exercise)
    if loaded is not None:
        definition = loaded.definition
        return Rubric(
            prompt=definition.prompt,
            key_points=definition.key_points,
            accepted_answers=definition.accepted_answers,
            reference=definition.reference_answer,
            misconception=definition.misconception,
        )
    problem = db.get(Problem, attempt.problem_id) if attempt.problem_id else None
    reference = problem.evaluator.key_insight if problem and problem.evaluator else ""
    return Rubric(
        prompt=f"Key insight for {problem.title if problem else 'the problem'}",
        key_points=[],
        accepted_answers=[],
        reference=reference,
        misconception=None,
    )


def code_grade(db: Session, attempt: ReviewAttempt, job_id: str) -> AnswerGrade:
    job = db.get(ExecutionJob, job_id)
    if job is None or job.user_id != attempt.user_id or job.problem_id != attempt.problem_id:
        raise ApiError(404, "execution_not_found", "Submit your code before finishing.")
    if job.kind != "submit" or job.status != "completed":
        raise ApiError(409, "submission_required", "Finish with a completed submission.")
    hidden = (job.result_public or {}).get("hidden") or {}
    if job.verdict == "passed":
        correctness = 1.0
    elif hidden.get("total"):
        correctness = round(0.6 * hidden.get("passed", 0) / hidden["total"], 2)
    else:
        correctness = 0.0
    return AnswerGrade(
        correctness=correctness,
        missing_points=[] if correctness == 1.0 else ["passing all tests"],
        misconceptions=[],
        recommended_action="advance"
        if correctness == 1.0
        else "review"
        if correctness >= 0.3
        else "coach",
        feedback="All tests pass."
        if correctness == 1.0
        else f"Passed {hidden.get('passed', 0)} of {hidden.get('total', 0)} hidden tests.",
    )


def answer(
    db: Session,
    user: User,
    attempt_id: str,
    *,
    text: str | None,
    job_id: str | None,
    confidence: int | None,
) -> dict[str, Any]:
    attempt = owned_attempt(db, user, attempt_id)
    task = db.get(ReviewTask, attempt.task_id) if attempt.task_id else None
    if attempt.status != "in_progress":
        return item_view(db, attempt, task)
    task_type = task.task_type if task else "recall"
    if task_type in INTERVIEW_TASKS:
        raise ApiError(409, "interview_task", "Finish the linked interview to complete this item.")
    if task_type in CODE_TASKS:
        if not job_id:
            raise ApiError(422, "submission_required", "Submit your code before finishing.")
        graded, grader = code_grade(db, attempt, job_id), "sandbox"
        attempt.answer = f"execution:{job_id}"
    else:
        if not text or not text.strip():
            raise ApiError(422, "answer_required", "Write an answer first.")
        rubric = rubric_for(attempt, db, task)
        graded, grader = grade(rubric, text, provider_factory())
        attempt.answer = text[:8000]
    now = utcnow()
    attempt.completed_at = now
    attempt.status = "submitted"
    attempt.correctness = graded.correctness
    attempt.confidence = confidence
    attempt.latency_ms = round((now - as_utc(attempt.started_at)).total_seconds() * 1000)
    if graded.recommended_action == "rebuild":
        attempt.mode = "rebuild"
    loaded = corpus_exercise(db.get(Exercise, attempt.exercise_id) if attempt.exercise_id else None)
    rubric_reference = (
        rubric_for(attempt, db, task).reference if task_type not in CODE_TASKS else None
    )
    feedback = {
        "correctness": graded.correctness,
        "band": "correct"
        if graded.correctness >= 0.8
        else "partial"
        if graded.correctness >= 0.5
        else "missed",
        "feedback": graded.feedback,
        "missing_points": graded.missing_points,
        "misconceptions": graded.misconceptions,
        "recommended_action": graded.recommended_action,
        "reference_answer": rubric_reference,
        "grader": grader,
        "rebuild": {
            "misconception": loaded.definition.misconception,
            "explanation": loaded.definition.reference_answer,
            "confirmation_question": loaded.definition.confirmation_question,
        }
        if graded.recommended_action == "rebuild" and loaded and loaded.definition.misconception
        else None,
    }
    assisted = bool((attempt.evaluation or {}).get("assisted"))
    attempt.evaluation = {**(attempt.evaluation or {}), "feedback": feedback}
    if task is not None:
        problem_seen = bool(
            attempt.problem_id
            and db.scalar(
                select(SolutionView.id).where(
                    SolutionView.user_id == user.id, SolutionView.problem_id == attempt.problem_id
                )
            )
        )
        upsert_evidence(
            db,
            user_id=user.id,
            capability_id=task.capability_id,
            source_type="review",
            source_id=attempt.id,
            problem_id=attempt.problem_id,
            dedupe_key=f"review:{attempt.id}",
            occurred_at=now,
            score=graded.correctness,
            confidence=0.8
            if grader in ("sandbox", "rubric/v1") and task_type != "explain"
            else 0.6,
            hint_level=min(5, attempt.hints_used),
            exercise_type=task_type,
            explanation=f"{TASK_LABELS.get(task_type, task_type)}: {feedback['band']}",
            assisted=assisted or (problem_seen and task_type in ("implementation",)),
            transfer=task_type == "transfer",
            repeat_exposure=task_type == "implementation",
        )
        recompute_capability(db, user.id, task.capability_id)
        task.status = "completed"
        task.completed_at = now
        task.updated_at = now
        if graded.correctness < 0.5:
            reschedule_after_failure(db, user, task)
    track(
        db,
        user.id,
        "review_completed",
        {
            "task_type": task_type,
            "score_band": feedback["band"],
            "hints_used": attempt.hints_used,
            "latency_s": round((attempt.latency_ms or 0) / 1000),
            "recommended_action": graded.recommended_action,
            "from_drill": attempt.drill_session_id is not None,
        },
    )
    db.commit()
    return item_view(db, attempt, task)


def confirm(db: Session, user: User, attempt_id: str, text: str) -> dict[str, Any]:
    """Rebuild step: answer the confirmation question after reading the explanation."""
    attempt = owned_attempt(db, user, attempt_id)
    task = db.get(ReviewTask, attempt.task_id) if attempt.task_id else None
    feedback = (attempt.evaluation or {}).get("feedback") or {}
    rebuild = feedback.get("rebuild")
    if attempt.status != "submitted" or not rebuild:
        raise ApiError(409, "no_rebuild", "This item has no confirmation step.")
    rubric = rubric_for(attempt, db, task)
    graded, _ = grade(
        Rubric(
            prompt=rebuild.get("confirmation_question") or rubric.prompt,
            key_points=rubric.key_points,
            accepted_answers=[],
            reference=rubric.reference,
            misconception=None,
        ),
        text,
        provider_factory(),
    )
    if task is not None:
        upsert_evidence(
            db,
            user_id=user.id,
            capability_id=task.capability_id,
            source_type="review_confirmation",
            source_id=attempt.id,
            dedupe_key=f"confirmation:{attempt.id}",
            occurred_at=utcnow(),
            score=graded.correctness,
            confidence=0.4,
            hint_level=5,
            exercise_type="confirmation",
            explanation="Rebuild confirmation after an explanation",
            assisted=True,
        )
        recompute_capability(db, user.id, task.capability_id)
    feedback["confirmation"] = {
        "answer": text[:2000],
        "correctness": graded.correctness,
        "feedback": graded.feedback,
    }
    attempt.evaluation = {**attempt.evaluation, "feedback": feedback}
    db.commit()
    return item_view(db, attempt, task)


def snooze(db: Session, user: User, task_id: str, days: int) -> dict[str, Any]:
    task = owned_task(db, user, task_id)
    if task.status not in ACTIVE:
        raise ApiError(409, "task_closed", "This review is no longer active.")
    days = max(1, min(7, days))
    until = utcnow() + timedelta(days=days)
    task.status = "snoozed"
    task.snoozed_until = until
    task.due_at = max(as_utc(task.due_at), until)
    task.updated_at = utcnow()
    track(db, user.id, "review_snoozed", {"task_type": task.task_type, "days": days})
    db.commit()
    return task_view(db, task)


def close(
    db: Session, user: User, task_id: str, status: str, note: str | None = None
) -> dict[str, Any]:
    task = owned_task(db, user, task_id)
    if task.status not in ACTIVE:
        raise ApiError(409, "task_closed", "This review is no longer active.")
    task.status = status
    task.updated_at = utcnow()
    if note:
        task.reason = f"{task.reason} [reported: {note[:300]}]"
    track(
        db,
        user.id,
        "exercise_reported" if status == "invalidated" else "review_skipped",
        {"task_type": task.task_type},
    )
    db.commit()
    return task_view(db, task)


def history(db: Session, user: User, limit: int = 100) -> list[dict[str, Any]]:
    attempts = db.scalars(
        select(ReviewAttempt)
        .where(ReviewAttempt.user_id == user.id, ReviewAttempt.status == "submitted")
        .order_by(ReviewAttempt.completed_at.desc())
        .limit(limit)
    ).all()
    result = []
    for attempt in attempts:
        task = db.get(ReviewTask, attempt.task_id) if attempt.task_id else None
        feedback = (attempt.evaluation or {}).get("feedback") or {}
        result.append(
            {
                "attempt_id": attempt.id,
                "completed_at": as_utc(attempt.completed_at).isoformat()
                if attempt.completed_at
                else None,
                "task_type": task.task_type if task else None,
                "capability": task.capability.name if task else None,
                "capability_slug": task.capability.slug if task else None,
                "band": feedback.get("band"),
                "hints_used": attempt.hints_used,
            }
        )
    return result


def pending_for_drill(db: Session, user: User) -> list[ReviewTask]:
    now = utcnow()
    horizon = end_of_local_day(now, user_zone(user))
    return list(
        db.scalars(
            select(ReviewTask).where(
                ReviewTask.user_id == user.id,
                ReviewTask.status.in_(ACTIVE),
                ReviewTask.due_at < horizon,
                or_(ReviewTask.snoozed_until.is_(None), ReviewTask.snoozed_until <= now),
            )
        )
    )
