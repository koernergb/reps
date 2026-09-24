"""Deterministic adaptive drill composer.

Priorities (highest first), all integers/floats with stable tie-breaks by (due_at, id):
1. Due review tasks: 10 + 2 per overdue day (capped at 14 days) + 4 x (1 - mastery).
2. Practice for the weakest capabilities (Weak/Developing, with evidence): 5 + 4 x (1 - mastery).
3. Onboarding recognition items when there is no learner evidence at all: 1 (round-robin topics).

Constraints: total estimated minutes <= budget; at most one item per capability (unless the
item is a Rebuild retry); at most two items per topic; at most one code item unless the budget
is at least 25 minutes; no exercise twice. Items are then ordered from lighter to heavier
exercise types with topics interleaved.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

TYPE_ORDER = {
    "recall": 0,
    "recognition": 1,
    "key_insight": 2,
    "explain": 3,
    "trace": 4,
    "pseudocode": 5,
    "debug": 6,
    "code_fragment": 7,
    "implementation": 8,
    "transfer": 9,
}
CODE_TYPES = {"debug", "code_fragment", "implementation", "transfer"}
EXCLUDED_TYPES = {"reinterview"}
MAX_PER_TOPIC = 2


@dataclass(frozen=True)
class Candidate:
    kind: str  # "task" | "practice"
    key: str  # task id or exercise id
    capability_slug: str
    topic: str
    task_type: str
    minutes: float
    priority: float
    due_at: datetime | None
    reason: str
    exercise_id: str | None = None
    retry: bool = False


def compose(candidates: list[Candidate], budget_minutes: float) -> list[Candidate]:
    ordered = sorted(
        (item for item in candidates if item.task_type not in EXCLUDED_TYPES),
        key=lambda item: (
            -item.priority,
            item.due_at.isoformat() if item.due_at else "9999",
            item.key,
        ),
    )
    chosen: list[Candidate] = []
    used_minutes = 0.0
    per_capability: Counter[str] = Counter()
    per_topic: Counter[str] = Counter()
    exercises: set[str] = set()
    code_items = 0
    max_code = 2 if budget_minutes >= 25 else 1
    for item in ordered:
        if used_minutes + item.minutes > budget_minutes:
            continue
        if per_capability[item.capability_slug] and not item.retry:
            continue
        if per_topic[item.topic] >= MAX_PER_TOPIC:
            continue
        if item.exercise_id and item.exercise_id in exercises:
            continue
        if item.task_type in CODE_TYPES:
            if code_items >= max_code:
                continue
            code_items += 1
        chosen.append(item)
        used_minutes += item.minutes
        per_capability[item.capability_slug] += 1
        per_topic[item.topic] += 1
        if item.exercise_id:
            exercises.add(item.exercise_id)
    return interleave(chosen)


def interleave(items: list[Candidate]) -> list[Candidate]:
    """Lighter items first; avoid consecutive items from the same topic where possible."""
    remaining = sorted(items, key=lambda item: (TYPE_ORDER.get(item.task_type, 5), item.key))
    result: list[Candidate] = []
    while remaining:
        previous_topic = result[-1].topic if result else None
        index = next((i for i, item in enumerate(remaining) if item.topic != previous_topic), 0)
        result.append(remaining.pop(index))
    return result


def describe_mix(items: list[Candidate]) -> str:
    due = sum(1 for item in items if item.kind == "task")
    practice = len(items) - due
    parts = []
    if due:
        parts.append(f"{due} scheduled review{'s' if due != 1 else ''}")
    if practice:
        parts.append(f"{practice} practice item{'s' if practice != 1 else ''} for weak areas")
    topics = sorted({item.topic for item in items})
    if topics:
        parts.append(f"covering {', '.join(topics)}")
    return ", ".join(parts) or "Nothing to practice right now."
