"""Interview session lifecycle.

Invariants enforced here (not by the model):
- Every mutation from the learner carries `expected_version`; stale or out-of-order requests get
  409 and change nothing. Retries with the same idempotency key return the current view.
- Event sequence numbers are allocated atomically in the database.
- State changes only happen through `state_machine.validate_transition`.
- The mock timer is server-authoritative; expiry is applied lazily on the next request.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus.loader import LoadedProblem, get_corpus
from app.errors import ApiError
from app.interview.events import EVENT_SCHEMA_VERSION, LEARNER_UTTERANCES, validate_payload
from app.interview.guard import GuardContext, check_message, hidden_fingerprints
from app.interview.interviewer import (
    PROMPT_VERSION,
    TURN_SCHEMA_VERSION,
    InterviewerTurn,
    TurnContext,
    capability_tags_for,
    classify_learner_message,
    llm_turn,
    policy_turn,
)
from app.interview.policy import POLICIES, ModePolicy, time_limit_for
from app.interview.state_machine import (
    TRANSITIONS,
    InvalidTransition,
    State,
    TransitionContext,
    Trigger,
    is_terminal,
    validate_transition,
)
from app.llm.audit import record_call
from app.llm.provider import LLMProvider, LLMUnavailable, build_provider
from app.models import (
    ExecutionJob,
    HintLog,
    InterviewEvent,
    InterviewSession,
    LearnerCapabilityState,
    Problem,
    User,
)

logger = structlog.get_logger()

TRANSCRIPT_EVENTS = (
    "interviewer_message",
    *LEARNER_UTTERANCES,
    "hint_given",
    "state_changed",
    "run_tests",
    "solution_submitted",
    "test_success",
    "test_failure",
    "timer_expired",
    "leak_blocked",
    "solution_viewed",
)

# Tests may replace this to inject a fake provider.
provider_factory = build_provider


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# --- persistence helpers -------------------------------------------------------------------


def append_event(
    db: Session,
    interview: InterviewSession,
    event_type: str,
    payload: dict[str, Any],
    *,
    actor: str,
    idempotency_key: str | None = None,
    client_timestamp: datetime | None = None,
) -> InterviewEvent:
    validated = validate_payload(event_type, payload)
    sequence = db.execute(
        update(InterviewSession)
        .where(InterviewSession.id == interview.id)
        .values(event_count=InterviewSession.event_count + 1)
        .returning(InterviewSession.event_count)
        .execution_options(synchronize_session=False)
    ).scalar_one()
    interview.event_count = sequence
    event = InterviewEvent(
        session_id=interview.id,
        sequence=sequence,
        event_type=event_type,
        occurred_at=utcnow(),
        schema_version=EVENT_SCHEMA_VERSION,
        payload=validated,
        actor=actor,
        idempotency_key=idempotency_key,
        client_timestamp=client_timestamp,
    )
    db.add(event)
    db.flush()
    return event


def get_owned(db: Session, user_id: str, session_id: str) -> InterviewSession:
    interview = db.get(InterviewSession, session_id)
    if interview is None or interview.user_id != user_id:
        raise ApiError(404, "session_not_found", "Interview session not found.")
    return interview


def already_processed(db: Session, interview: InterviewSession, key: str | None) -> bool:
    if not key:
        return False
    return (
        db.scalar(
            select(InterviewEvent.id).where(
                InterviewEvent.session_id == interview.id, InterviewEvent.idempotency_key == key
            )
        )
        is not None
    )


def claim_version(db: Session, interview: InterviewSession, expected_version: int) -> None:
    """Atomically advance the session version or reject a stale/out-of-order request."""
    claimed = db.execute(
        update(InterviewSession)
        .where(InterviewSession.id == interview.id, InterviewSession.version == expected_version)
        .values(version=expected_version + 1, last_activity_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if not claimed.rowcount:  # type: ignore[attr-defined]
        db.rollback()
        db.refresh(interview)
        raise ApiError(
            409,
            "stale_version",
            f"This interview changed (now version {interview.version}). Refresh and try again.",
        )
    interview.version = expected_version + 1
    interview.last_activity_at = utcnow()


def policy_of(interview: InterviewSession) -> ModePolicy:
    return ModePolicy.from_dict(interview.policy)


def loaded_problem(db: Session, interview: InterviewSession) -> LoadedProblem:
    problem = db.get(Problem, interview.problem_id)
    assert problem is not None
    return get_corpus().problem(problem.slug)


# --- state transitions ----------------------------------------------------------------------


def execution_count(db: Session, interview: InterviewSession) -> int:
    return len(
        db.scalars(
            select(ExecutionJob.id).where(
                ExecutionJob.session_id == interview.id, ExecutionJob.status == "completed"
            )
        ).all()
    )


def transition(
    db: Session,
    interview: InterviewSession,
    target: State,
    trigger: Trigger,
    reason: str | None = None,
) -> None:
    context = TransitionContext(
        executions=execution_count(db, interview),
        has_code_changes=bool(interview.current_code)
        and interview.current_code != loaded_problem(db, interview).definition.starter_code,
    )
    validate_transition(interview.state, target, trigger, context)  # type: ignore[arg-type]
    append_event(
        db,
        interview,
        "state_changed",
        {"from_state": interview.state, "to_state": target, "trigger": trigger, "reason": reason},
        actor="system",
    )
    interview.state = target


def interviewer_says(
    db: Session,
    interview: InterviewSession,
    user_id: str,
    context: TurnContext,
) -> InterviewerTurn:
    """Produce, guard, and record the interviewer's next message."""
    provider: LLMProvider | None = provider_factory()
    turn: InterviewerTurn
    source = "policy"
    prompt_id: str | None = None
    if provider is not None:
        try:
            turn, result, prompt_id = llm_turn(provider, context)
            source = "llm"
            record_call(
                db,
                user_id=user_id,
                session_id=interview.id,
                task="interviewer",
                provider=result.provider,
                model=result.model,
                prompt_version=prompt_id,
                schema_version=TURN_SCHEMA_VERSION,
                status="ok",
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                attempts=result.attempts,
            )
        except LLMUnavailable as exc:
            record_call(
                db,
                user_id=user_id,
                session_id=interview.id,
                task="interviewer",
                provider=provider.name,
                model=provider.model,
                prompt_version=f"interviewer/{PROMPT_VERSION}",
                schema_version=TURN_SCHEMA_VERSION,
                status="error",
                error_code=exc.code,
                attempts=exc.attempts,
            )
            append_event(
                db,
                interview,
                "llm_fallback",
                {"task": "interviewer", "error_code": exc.code},
                actor="system",
            )
            turn = policy_turn(context)
    else:
        turn = policy_turn(context)
    problem = context.problem
    guard = check_message(
        turn.message,
        GuardContext(
            reference_solution=problem.definition.reference_solution,
            hidden_inputs=hidden_fingerprints(test.args for test in problem.hidden_tests),
            key_insight=problem.definition.key_insight,
        ),
    )
    message = turn.message
    if not guard.allowed:
        append_event(
            db,
            interview,
            "leak_blocked",
            {"reasons": guard.reasons, "source": source},
            actor="system",
        )
        message = guard.message
        logger.warning("interviewer_leak_blocked", session_id=interview.id, reasons=guard.reasons)
    append_event(
        db,
        interview,
        "interviewer_message",
        {
            "content": message,
            "state": interview.state,
            "source": source,
            "prompt_version": prompt_id,
        },
        actor="interviewer",
    )
    return turn


def build_context(
    db: Session,
    interview: InterviewSession,
    *,
    learner_message: str | None,
    entering_state: bool,
) -> TurnContext:
    problem = loaded_problem(db, interview)
    policy = policy_of(interview)
    events = db.scalars(
        select(InterviewEvent)
        .where(InterviewEvent.session_id == interview.id)
        .order_by(InterviewEvent.sequence)
    ).all()
    transcript: list[tuple[str, str]] = []
    turns_in_state = 0
    approach_proposed = False
    last_execution = ""
    for event in events:
        if event.event_type == "state_changed":
            turns_in_state = 0
        if event.event_type == "interviewer_message":
            transcript.append(("interviewer", event.payload["content"]))
            turns_in_state += 1
        elif event.event_type in LEARNER_UTTERANCES:
            transcript.append(("learner", event.payload["content"]))
            if event.event_type in ("approach_proposed", "approach_changed"):
                approach_proposed = True
        elif event.event_type in ("test_success", "test_failure"):
            payload = event.payload
            hidden = (
                f", hidden {payload['hidden_passed']}/{payload['hidden_total']}"
                if payload.get("hidden_total") is not None
                else ""
            )
            last_execution = (
                f"{payload['kind']}: {payload['verdict']} (visible "
                f"{payload['visible_passed']}/{payload['visible_total']}{hidden})"
            )
    return TurnContext(
        problem=problem,
        policy=policy,
        state=interview.state,  # type: ignore[arg-type]
        learner_message=learner_message,
        transcript=transcript,
        code=interview.current_code or "",
        execution_summary=last_execution,
        weaknesses=known_weaknesses(db, interview.user_id, problem.definition.topic),
        hints_remaining=max(0, policy.hint_budget - interview.hints_used),
        entering_state=entering_state,
        interviewer_turns_in_state=turns_in_state,
        approach_proposed=approach_proposed,
        capability_slugs=[weight.slug for weight in problem.definition.capabilities],
    )


def known_weaknesses(db: Session, user_id: str, topic: str) -> list[str]:
    from app.models import Capability

    rows = db.execute(
        select(Capability.name)
        .join(LearnerCapabilityState, LearnerCapabilityState.capability_id == Capability.id)
        .where(
            LearnerCapabilityState.user_id == user_id,
            LearnerCapabilityState.band.in_(("Weak", "Developing")),
            LearnerCapabilityState.evidence_count > 0,
            Capability.slug.like(f"{topic}.%"),
        )
        .order_by(LearnerCapabilityState.mastery)
        .limit(3)
    ).scalars()
    return list(rows)


# --- mock timer -----------------------------------------------------------------------------


def expire_if_needed(db: Session, interview: InterviewSession) -> bool:
    deadline = as_utc(interview.deadline_at)
    if deadline is None or is_terminal(interview.state) or utcnow() < deadline:
        return False
    append_event(
        db, interview, "timer_expired", {"deadline_at": deadline.isoformat()}, actor="system"
    )
    finish(db, interview, "COMPLETE", "timer", result="timed_out", reason="time limit reached")
    db.commit()
    run_evaluation(db, interview)
    return True


def finish(
    db: Session,
    interview: InterviewSession,
    target: State,
    trigger: Trigger,
    *,
    result: str,
    reason: str,
) -> None:
    transition(db, interview, target, trigger, reason)
    interview.completed_at = utcnow()
    interview.result = result
    append_event(
        db,
        interview,
        "interview_completed" if target == "COMPLETE" else "interview_abandoned",
        {"result": result, "reason": reason},
        actor="system",
    )
    interview.version += 1


# --- public operations ----------------------------------------------------------------------


def start_session(
    db: Session,
    user: User,
    problem_slug: str,
    mode: str,
    time_multiplier: float = 1.0,
    reduce_motion: bool = False,
) -> InterviewSession:
    settings = get_settings()
    if not settings.feature_interviews:
        raise ApiError(503, "interviews_disabled", "Interviews are currently disabled.")
    if mode == "mock" and not settings.feature_mock_mode:
        raise ApiError(503, "mock_disabled", "Mock interviews are currently disabled.")
    problem = db.scalar(
        select(Problem).where(Problem.slug == problem_slug, Problem.status != "retired")
    )
    if problem is None:
        raise ApiError(404, "problem_not_found", "Problem not found.")
    if problem.status != "reviewed" and not settings.allow_unreviewed_content:
        raise ApiError(409, "problem_unreviewed", "This problem has not passed content review.")
    policy = POLICIES[mode]
    now = utcnow()
    time_limit = time_limit_for(policy, time_multiplier)
    interview = InterviewSession(
        user_id=user.id,
        problem_id=problem.id,
        mode=mode,
        state="INTRO",
        started_at=now,
        version=1,
        event_count=0,
        policy=policy.to_dict(),
        problem_version=problem.content_version,
        current_code=problem.starter_code,
        time_limit_s=time_limit,
        deadline_at=now + timedelta(seconds=time_limit) if time_limit else None,
        last_activity_at=now,
        accommodations={"time_multiplier": time_multiplier, "reduce_motion": reduce_motion},
    )
    db.add(interview)
    db.flush()
    append_event(
        db,
        interview,
        "interview_started",
        {
            "mode": mode,
            "policy_version": policy.version,
            "problem_slug": problem.slug,
            "problem_version": problem.content_version,
            "time_limit_s": time_limit,
        },
        actor="system",
    )
    append_event(db, interview, "problem_opened", {"problem_slug": problem.slug}, actor="system")
    interviewer_says(
        db,
        interview,
        user.id,
        build_context(db, interview, learner_message=None, entering_state=True),
    )
    db.commit()
    logger.info("interview_started", session_id=interview.id, mode=mode, problem=problem.slug)
    return interview


# After an interviewer-recommended transition, the reply itself already leads into the next
# phase; only these states need a fresh prompt (a new question must be asked).
ENTRY_PROMPT_STATES = {"TESTING", "COMPLEXITY", "FOLLOW_UP"}

LEARNER_EVENTS_BY_STATE: dict[str, set[str]] = {
    "INTRO": {"clarification_asked", "reasoning_statement", "approach_proposed"},
    "CLARIFICATION": {"clarification_asked", "reasoning_statement"},
    "APPROACH_DISCUSSION": {
        "clarification_asked",
        "reasoning_statement",
        "approach_proposed",
        "approach_changed",
    },
    "IMPLEMENTATION": {"reasoning_statement", "clarification_asked", "approach_changed"},
    "TESTING": {"reasoning_statement", "clarification_asked"},
    "COMPLEXITY": {"complexity_answer", "reasoning_statement"},
    "FOLLOW_UP": {"followup_answer", "reasoning_statement"},
}


def post_message(
    db: Session,
    user: User,
    interview: InterviewSession,
    content: str,
    expected_version: int,
    idempotency_key: str,
    client_timestamp: datetime | None,
) -> None:
    if expire_if_needed(db, interview) or already_processed(db, interview, idempotency_key):
        return
    if is_terminal(interview.state):
        raise ApiError(409, "session_finished", "This interview has already ended.")
    claim_version(db, interview, expected_version)
    context = build_context(db, interview, learner_message=content, entering_state=False)
    turn = respond_to_learner(db, interview, user, context, idempotency_key, client_timestamp)
    apply_recommendation(db, interview, user, turn)
    db.commit()
    if interview.state == "COMPLETE":
        run_evaluation(db, interview)


def respond_to_learner(
    db: Session,
    interview: InterviewSession,
    user: User,
    context: TurnContext,
    idempotency_key: str,
    client_timestamp: datetime | None,
) -> InterviewerTurn:
    """Record the learner utterance, then the interviewer's reply.

    The utterance is classified deterministically first; an LLM classification replaces it only
    when it is valid for the current state.
    """
    assert context.learner_message is not None
    topic = context.problem.definition.topic
    provisional = classify_learner_message(
        context.state, context.learner_message, context.approach_proposed
    )
    utterance = append_event(
        db,
        interview,
        provisional,
        {
            "content": context.learner_message,
            "state": interview.state,
            "capability_tags": capability_tags_for(provisional, topic),
        },
        actor="learner",
        idempotency_key=idempotency_key,
        client_timestamp=client_timestamp,
    )
    turn = interviewer_says(db, interview, user.id, context)
    suggested = turn.learner_event_type
    if (
        suggested
        and suggested != provisional
        and suggested in LEARNER_EVENTS_BY_STATE.get(interview.state, set())
    ):
        tags = [tag for tag in turn.capability_tags if tag in context.capability_slugs]
        utterance.event_type = suggested
        utterance.payload = {
            **utterance.payload,
            "capability_tags": tags or capability_tags_for(suggested, topic),
        }
    return turn


def apply_recommendation(
    db: Session, interview: InterviewSession, user: User, turn: InterviewerTurn
) -> None:
    """Apply the interviewer's recommended transition only if the state machine allows it."""
    target = turn.recommended_transition
    if target is None or target not in TRANSITIONS.get(interview.state, frozenset()):  # type: ignore[call-overload]
        return
    try:
        transition(db, interview, target, "interviewer")
    except InvalidTransition:
        return
    if target == "COMPLETE":
        interview.completed_at = utcnow()
        interview.result = "completed"
        append_event(
            db,
            interview,
            "interview_completed",
            {"result": "completed", "reason": "interviewer wrapped up"},
            actor="system",
        )
        return
    if target in ENTRY_PROMPT_STATES:
        interviewer_says(
            db,
            interview,
            user.id,
            build_context(db, interview, learner_message=None, entering_state=True),
        )


def save_code(
    db: Session, interview: InterviewSession, code: str, idempotency_key: str, reason: str
) -> None:
    if expire_if_needed(db, interview) or already_processed(db, interview, idempotency_key):
        return
    if is_terminal(interview.state):
        raise ApiError(409, "session_finished", "This interview has already ended.")
    if code == interview.current_code:
        return
    append_event(
        db,
        interview,
        "code_edit",
        {"code": code, "chars": len(code), "reason": reason},
        actor="learner",
        idempotency_key=idempotency_key,
    )
    interview.current_code = code
    interview.last_activity_at = utcnow()
    db.commit()


def advance(
    db: Session,
    user: User,
    interview: InterviewSession,
    target: State,
    expected_version: int,
    idempotency_key: str,
) -> None:
    if expire_if_needed(db, interview) or already_processed(db, interview, idempotency_key):
        return
    claim_version(db, interview, expected_version)
    try:
        if target in ("COMPLETE", "ABANDONED"):
            finish(
                db,
                interview,
                target,
                "learner",
                result="abandoned" if target == "ABANDONED" else "completed",
                reason="learner ended the interview"
                if target == "COMPLETE"
                else "learner abandoned the interview",
            )
        else:
            transition(db, interview, target, "learner")
            interviewer_says(
                db,
                interview,
                user.id,
                build_context(db, interview, learner_message=None, entering_state=True),
            )
    except InvalidTransition as exc:
        db.rollback()
        raise ApiError(409, exc.code, exc.message) from exc
    # Tag the transition event with the request key so retries are idempotent.
    last = db.scalar(
        select(InterviewEvent)
        .where(
            InterviewEvent.session_id == interview.id, InterviewEvent.event_type == "state_changed"
        )
        .order_by(InterviewEvent.sequence.desc())
        .limit(1)
    )
    if last is not None:
        last.idempotency_key = idempotency_key
    db.commit()
    if interview.state == "COMPLETE":
        run_evaluation(db, interview)


HINT_TAGS = {
    1: ("recognition", "invariant"),
    2: ("recognition", "invariant"),
    3: ("implementation", "invariant"),
    4: ("implementation", "boundaries"),
    5: ("recognition", "invariant", "implementation"),
}


def request_hint(
    db: Session,
    user: User,
    interview: InterviewSession,
    expected_version: int,
    idempotency_key: str,
) -> None:
    if expire_if_needed(db, interview) or already_processed(db, interview, idempotency_key):
        return
    if is_terminal(interview.state):
        raise ApiError(409, "session_finished", "This interview has already ended.")
    policy = policy_of(interview)
    level = interview.max_hint_level + 1
    if interview.hints_used >= policy.hint_budget or level > policy.max_hint_level:
        raise ApiError(
            409,
            "hint_unavailable",
            "No more hints are available in this mode."
            if policy.mode == "mock"
            else "You've used every hint level for this problem.",
        )
    claim_version(db, interview, expected_version)
    problem = loaded_problem(db, interview)
    topic = problem.definition.topic
    tags = [f"{topic}.{suffix}" for suffix in HINT_TAGS[level]] + ["interview.independence"]
    text = problem.definition.hints[level - 1]
    append_event(
        db,
        interview,
        "hint_requested",
        {"level": level, "state": interview.state},
        actor="learner",
        idempotency_key=idempotency_key,
    )
    append_event(
        db,
        interview,
        "hint_given",
        {"level": level, "content": text, "capability_tags": tags},
        actor="interviewer",
    )
    db.add(
        HintLog(
            user_id=user.id,
            session_id=interview.id,
            hint_level=level,
            hint_text=text,
            occurred_at=utcnow(),
            capability_tags=tags,
        )
    )
    interview.hints_used += 1
    interview.max_hint_level = level
    db.commit()


def idle_checkin(
    db: Session, user: User, interview: InterviewSession, expected_version: int, idle_s: float
) -> bool:
    """Practice mode may check in after silence; mock mode waits much longer."""
    if expire_if_needed(db, interview) or is_terminal(interview.state):
        return False
    policy = policy_of(interview)
    last = as_utc(interview.last_activity_at) or utcnow()
    server_idle = (utcnow() - last).total_seconds()
    if policy.idle_checkin_s is None or min(idle_s, server_idle) < policy.idle_checkin_s:
        return False
    claim_version(db, interview, expected_version)
    append_event(
        db,
        interview,
        "interviewer_message",
        {
            "content": "Take your time. Want to talk me through where you are?"
            if policy.mode == "practice"
            else "How's it going?",
            "state": interview.state,
            "source": "policy",
            "prompt_version": None,
        },
        actor="interviewer",
    )
    db.commit()
    return True


def on_execution_completed(db: Session, job: ExecutionJob) -> None:
    """Worker hook: record execution evidence on the interview and react to a passing submit."""
    if job.session_id is None:
        return
    interview = db.get(InterviewSession, job.session_id)
    if interview is None or is_terminal(interview.state):
        return
    if job.code != interview.current_code:
        append_event(
            db,
            interview,
            "code_edit",
            {"code": job.code, "chars": len(job.code), "reason": job.kind},
            actor="learner",
        )
        interview.current_code = job.code
    result = job.result_public or {}
    hidden = result.get("hidden") or {}
    payload = {
        "job_id": job.id,
        "kind": job.kind,
        "verdict": job.verdict,
        "visible_passed": int(result.get("visible_passed", 0)),
        "visible_total": int(result.get("visible_total", 0)),
        "hidden_passed": hidden.get("passed"),
        "hidden_total": hidden.get("total"),
    }
    append_event(
        db,
        interview,
        "solution_submitted" if job.kind == "submit" else "run_tests",
        payload,
        actor="learner",
    )
    if job.verdict is not None:
        append_event(
            db,
            interview,
            "test_success" if job.verdict == "passed" else "test_failure",
            payload,
            actor="system",
        )
    if (
        job.kind == "submit"
        and job.verdict == "passed"
        and interview.state in ("IMPLEMENTATION", "TESTING")
    ):
        try:
            transition(db, interview, "COMPLEXITY", "execution", "submission passed")
            interview.version += 1
            interviewer_says(
                db,
                interview,
                interview.user_id,
                build_context(db, interview, learner_message=None, entering_state=True),
            )
        except InvalidTransition:
            pass
    db.commit()


def run_evaluation(db: Session, interview: InterviewSession) -> None:
    if not get_settings().feature_semantic_evaluation:
        return
    from app.evaluation.service import evaluate_session

    try:
        evaluate_session(db, interview)
    except Exception:
        db.rollback()
        logger.exception("evaluation_failed", session_id=interview.id)


# --- views ----------------------------------------------------------------------------------


def session_view(db: Session, interview: InterviewSession) -> dict[str, Any]:
    problem = db.get(Problem, interview.problem_id)
    assert problem is not None
    policy = policy_of(interview)
    events = db.scalars(
        select(InterviewEvent)
        .where(
            InterviewEvent.session_id == interview.id,
            InterviewEvent.event_type.in_(TRANSCRIPT_EVENTS),
        )
        .order_by(InterviewEvent.sequence)
    ).all()
    from app.evaluation.service import latest_evaluation

    evaluation = latest_evaluation(db, interview.id)
    return {
        "id": interview.id,
        "problem_slug": problem.slug,
        "mode": interview.mode,
        "state": interview.state,
        "version": interview.version,
        "result": interview.result,
        "started_at": interview.started_at.isoformat(),
        "completed_at": interview.completed_at.isoformat() if interview.completed_at else None,
        "server_now": utcnow().isoformat(),
        "deadline_at": as_utc(interview.deadline_at).isoformat()  # type: ignore[union-attr]
        if interview.deadline_at
        else None,
        "time_limit_s": interview.time_limit_s,
        "accommodations": interview.accommodations,
        "policy": {
            "mode": policy.mode,
            "version": policy.version,
            "hint_budget": policy.hint_budget,
            "max_hint_level": policy.max_hint_level,
            "clarification_style": policy.clarification_style,
            "idle_checkin_s": policy.idle_checkin_s,
        },
        "hints_used": interview.hints_used,
        "max_hint_level": interview.max_hint_level,
        "current_code": interview.current_code,
        "allowed_transitions": sorted(TRANSITIONS.get(interview.state, frozenset())),  # type: ignore[call-overload]
        "solution_viewed": interview.solution_viewed_at is not None,
        "evaluation": {"id": evaluation.id, "status": evaluation.status} if evaluation else None,
        "transcript": [
            {
                "sequence": event.sequence,
                "type": event.event_type,
                "actor": event.actor,
                "occurred_at": event.occurred_at.isoformat(),
                "payload": {key: value for key, value in event.payload.items() if key != "code"},
            }
            for event in events
        ],
    }
