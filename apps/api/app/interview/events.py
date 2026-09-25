"""Versioned interview event payloads.

Every meaningful interview action is an event. Payload schemas are versioned; `validate_payload`
runs on append so malformed events never reach storage. Server timestamps (`occurred_at`) are
authoritative for ordering together with `sequence`; `client_timestamp` is informational only
(used to measure learner-perceived latency and never to order or to enforce time limits).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EVENT_SCHEMA_VERSION = 1
Actor = Literal["learner", "interviewer", "system"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterviewStarted(Payload):
    mode: Literal["practice", "mock"]
    policy_version: str
    problem_slug: str
    problem_version: int
    time_limit_s: int | None = None


class ProblemOpened(Payload):
    problem_slug: str


class Utterance(Payload):
    content: str = Field(max_length=8000)
    state: str
    capability_tags: list[str] = []


class InterviewerMessage(Payload):
    content: str = Field(max_length=4000)
    state: str
    source: Literal["llm", "policy"]
    prompt_version: str | None = None


class CodeEdit(Payload):
    code: str = Field(max_length=50_000)
    chars: int
    reason: Literal["checkpoint", "run", "submit"] = "checkpoint"


class ExecutionEvent(Payload):
    job_id: str
    kind: Literal["run", "submit"]
    verdict: str | None
    visible_passed: int = 0
    visible_total: int = 0
    hidden_passed: int | None = None
    hidden_total: int | None = None


class HintRequested(Payload):
    level: int = Field(ge=1, le=5)
    state: str


class HintGiven(Payload):
    level: int = Field(ge=1, le=5)
    content: str
    capability_tags: list[str]


class StateChanged(Payload):
    from_state: str
    to_state: str
    trigger: Literal["learner", "interviewer", "execution", "timer", "system"]
    reason: str | None = None


class InterviewEnded(Payload):
    result: str
    reason: str


class LeakBlocked(Payload):
    reasons: list[str]
    source: Literal["llm", "policy"]


class LLMFallback(Payload):
    task: str
    error_code: str


class SolutionViewed(Payload):
    problem_slug: str


class TimerExpired(Payload):
    deadline_at: str


EVENT_PAYLOADS: dict[str, type[Payload]] = {
    "interview_started": InterviewStarted,
    "problem_opened": ProblemOpened,
    "interviewer_message": InterviewerMessage,
    "clarification_asked": Utterance,
    "reasoning_statement": Utterance,
    "approach_proposed": Utterance,
    "approach_changed": Utterance,
    "complexity_answer": Utterance,
    "followup_answer": Utterance,
    "code_edit": CodeEdit,
    "run_tests": ExecutionEvent,
    "test_failure": ExecutionEvent,
    "test_success": ExecutionEvent,
    "solution_submitted": ExecutionEvent,
    "hint_requested": HintRequested,
    "hint_given": HintGiven,
    "state_changed": StateChanged,
    "interview_completed": InterviewEnded,
    "interview_abandoned": InterviewEnded,
    "leak_blocked": LeakBlocked,
    "llm_fallback": LLMFallback,
    "solution_viewed": SolutionViewed,
    "timer_expired": TimerExpired,
}
LEARNER_UTTERANCES = (
    "clarification_asked",
    "reasoning_statement",
    "approach_proposed",
    "approach_changed",
    "complexity_answer",
    "followup_answer",
)


def validate_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    schema = EVENT_PAYLOADS.get(event_type)
    if schema is None:
        raise ValueError(f"unknown event type {event_type}")
    return schema.model_validate(payload).model_dump()
