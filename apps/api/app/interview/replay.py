"""Reconstruct interview state from its event stream alone."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models import InterviewEvent


@dataclass(frozen=True)
class ReplayedSession:
    state: str
    hints_used: int
    max_hint_level: int
    current_code: str | None
    result: str | None
    executions: int
    event_count: int


def replay(events: Sequence[InterviewEvent], starter_code: str | None) -> ReplayedSession:
    state = "INTRO"
    hints = 0
    level = 0
    code = starter_code
    result = None
    executions = 0
    for event in sorted(events, key=lambda item: item.sequence):
        payload = event.payload
        if event.event_type == "state_changed":
            state = payload["to_state"]
        elif event.event_type == "hint_given":
            hints += 1
            level = max(level, payload["level"])
        elif event.event_type == "code_edit":
            code = payload["code"]
        elif event.event_type in ("interview_completed", "interview_abandoned"):
            result = payload["result"]
        elif event.event_type in ("run_tests", "solution_submitted"):
            executions += 1
    return ReplayedSession(
        state=state,
        hints_used=hints,
        max_hint_level=level,
        current_code=code,
        result=result,
        executions=executions,
        event_count=len(events),
    )
