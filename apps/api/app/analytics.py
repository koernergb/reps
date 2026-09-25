"""Product analytics with an explicit event/property allowlist.

Analytics never carry learner content: no code, transcripts, answers, emails, prompts, hidden
tests, or secrets. `track` rejects unknown events and non-allowlisted properties, and string
values are limited to short enum-like tokens.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import AnalyticsEvent

EVENTS: dict[str, frozenset[str]] = {
    "interview_started": frozenset({"mode", "difficulty", "from_task"}),
    "interview_completed": frozenset({"mode", "result", "duration_s"}),
    "interview_evaluated": frozenset(
        {"mode", "result", "hints_used", "weakness_count", "evaluator", "status"}
    ),
    "hint_given": frozenset({"level", "mode", "surface"}),
    "execution_requested": frozenset({"kind", "surface"}),
    "remediation_scheduled": frozenset({"tasks", "source"}),
    "review_completed": frozenset(
        {"task_type", "score_band", "hints_used", "latency_s", "recommended_action", "from_drill"}
    ),
    "review_snoozed": frozenset({"task_type", "days"}),
    "review_skipped": frozenset({"task_type"}),
    "exercise_reported": frozenset({"task_type"}),
    "drill_started": frozenset({"budget_minutes", "items", "planned_minutes"}),
    "drill_completed": frozenset({"items", "completed", "planned_minutes", "actual_minutes"}),
    "drill_abandoned": frozenset({"items", "completed", "abandon_index"}),
    "solution_viewed": frozenset({"surface"}),
    "diagnosis_flagged": frozenset({"has_capability"}),
    "state_rebuilt": frozenset({"capabilities"}),
}
FORBIDDEN_KEYS = re.compile(
    r"code|transcript|answer|content|email|prompt|hidden|secret|token|message|text", re.I
)
SAFE_STRING = re.compile(r"^[a-z0-9_.:-]{1,48}$")


class AnalyticsContractError(ValueError):
    pass


def validate(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    allowed = EVENTS.get(name)
    if allowed is None:
        raise AnalyticsContractError(f"unknown analytics event {name}")
    cleaned: dict[str, Any] = {}
    for key, value in properties.items():
        if key not in allowed or FORBIDDEN_KEYS.search(key):
            raise AnalyticsContractError(f"property {key} is not allowed on {name}")
        if isinstance(value, str) and not SAFE_STRING.match(value):
            raise AnalyticsContractError(f"property {key} must be a short token")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise AnalyticsContractError(f"property {key} must be a scalar")
        cleaned[key] = value
    return cleaned


def track(db: Session, user_id: str, name: str, properties: dict[str, Any] | None = None) -> None:
    db.add(
        AnalyticsEvent(
            user_id=user_id,
            name=name,
            properties=validate(name, properties or {}),
            occurred_at=datetime.now(UTC),
        )
    )
