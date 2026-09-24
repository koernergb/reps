"""Deterministic interview facts derived from events and sandbox results only."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.corpus.loader import LoadedProblem
from app.evaluation.schemas import Facts, Result
from app.interview.events import LEARNER_UTTERANCES
from app.interview.interviewer import assess_complexity
from app.models import ExecutionJob, InterviewEvent, InterviewSession


def _utc(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


def derive_result(
    *,
    final_state: str,
    session_result: str | None,
    passed_hidden: bool,
    submissions: int,
    max_hint_level: int,
    solution_viewed: bool,
) -> Result:
    if session_result == "abandoned" or final_state == "ABANDONED":
        return "abandoned"
    if passed_hidden and solution_viewed:
        return "solved_after_solution_view"
    if passed_hidden and max_hint_level == 0:
        return "solved_independently"
    if passed_hidden and max_hint_level <= 2:
        return "solved_with_minor_hints"
    if passed_hidden:
        return "solved_with_major_hints"
    if session_result == "timed_out":
        return "timed_out"
    return "failed" if submissions else "incomplete"


def compute_facts(
    interview: InterviewSession,
    events: Sequence[InterviewEvent],
    jobs: Sequence[ExecutionJob],
    problem: LoadedProblem,
) -> Facts:
    completed_jobs = [job for job in jobs if job.status == "completed"]
    submits = [job for job in completed_jobs if job.kind == "submit"]
    runs = [job for job in completed_jobs if job.kind == "run"]
    hidden_total = len(problem.hidden_tests)
    best_hidden = 0
    kinds: set[str] = set()
    for job in submits:
        hidden = (job.result_public or {}).get("hidden") or {}
        best_hidden = max(best_hidden, int(hidden.get("passed", 0)))
        kinds.update((hidden.get("failures") or {}).keys())
        if job.verdict in ("syntax_error", "load_error"):
            kinds.add(job.verdict)
    passed_hidden = any(job.verdict == "passed" for job in submits)
    latest = completed_jobs[-1] if completed_jobs else None
    latest_public = (latest.result_public or {}) if latest else {}
    first_code_seq = next(
        (event.sequence for event in events if event.event_type == "code_edit"), None
    )
    approach_seq = next(
        (
            event.sequence
            for event in events
            if event.event_type in ("approach_proposed", "approach_changed")
        ),
        None,
    )
    complexity_answers = [
        event.payload["content"] for event in events if event.event_type == "complexity_answer"
    ]
    time_ok: bool | None = None
    space_ok: bool | None = None
    if complexity_answers:
        joined = " ".join(complexity_answers)
        time_ok, space_ok = assess_complexity(
            joined, problem.definition.time_complexity, problem.definition.space_complexity
        )
    solution_viewed = interview.solution_viewed_at is not None or any(
        event.event_type == "solution_viewed" for event in events
    )
    started = _utc(interview.started_at) or datetime.now(UTC)
    ended = _utc(interview.completed_at) or (_utc(events[-1].occurred_at) if events else None)
    return Facts(
        result=derive_result(
            final_state=interview.state,
            session_result=interview.result,
            passed_hidden=passed_hidden,
            submissions=len(submits),
            max_hint_level=interview.max_hint_level,
            solution_viewed=solution_viewed,
        ),
        passed_hidden=passed_hidden,
        best_hidden_passed=hidden_total if passed_hidden else best_hidden,
        hidden_total=hidden_total,
        visible_passed=int(latest_public.get("visible_passed", 0)),
        visible_total=int(latest_public.get("visible_total", len(problem.visible_tests))),
        runs=len(runs),
        submissions=len(submits),
        first_submission_passed=bool(submits) and submits[0].verdict == "passed",
        hidden_failure_kinds=sorted(kinds),
        hints_used=interview.hints_used,
        max_hint_level=interview.max_hint_level,
        solution_viewed=solution_viewed,
        clarifications_asked=sum(1 for e in events if e.event_type == "clarification_asked"),
        learner_utterances=sum(1 for e in events if e.event_type in LEARNER_UTTERANCES),
        approach_before_code=approach_seq is not None
        and (first_code_seq is None or approach_seq < first_code_seq),
        complexity_time_correct=time_ok,
        complexity_space_correct=space_ok,
        duration_s=max(0, round(((ended or started) - started).total_seconds())),
        final_state=interview.state,
        mode=interview.mode,
    )
