"""Server-side interview mode policies (Practice vs Mock).

The policy is snapshotted onto the session at creation, so a session never silently changes
mode or constraints mid-interview.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Mode = Literal["practice", "mock"]
Intervention = Literal[
    "hint",
    "idle_checkin",
    "concept_explanation",
    "debug_help",
    "clarification_detail",
    "unsolicited_nudge",
]


@dataclass(frozen=True)
class ModePolicy:
    mode: Mode
    version: str
    max_hint_level: int
    hint_budget: int
    time_limit_s: int | None
    clarification_style: Literal["full", "minimal"]
    idle_checkin_s: int | None
    unsolicited_nudges: bool
    concept_explanations: bool
    debug_help: bool
    independence_weight: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModePolicy:
        return cls(**data)


PRACTICE = ModePolicy(
    mode="practice",
    version="practice/v1",
    max_hint_level=5,
    hint_budget=5,
    time_limit_s=None,
    clarification_style="full",
    idle_checkin_s=180,
    unsolicited_nudges=True,
    concept_explanations=True,
    debug_help=True,
    independence_weight=0.6,
)

MOCK = ModePolicy(
    mode="mock",
    version="mock/v1",
    max_hint_level=1,
    hint_budget=1,
    time_limit_s=45 * 60,
    clarification_style="minimal",
    idle_checkin_s=600,
    unsolicited_nudges=False,
    concept_explanations=False,
    debug_help=False,
    independence_weight=1.0,
)

POLICIES: dict[str, ModePolicy] = {"practice": PRACTICE, "mock": MOCK}


def allowed_interventions(
    policy: ModePolicy, *, hints_used: int, max_hint_level: int, idle_s: float
) -> set[Intervention]:
    """Deterministic set of interventions the interviewer may make right now."""
    allowed: set[Intervention] = set()
    if hints_used < policy.hint_budget and max_hint_level < policy.max_hint_level:
        allowed.add("hint")
    if policy.idle_checkin_s is not None and idle_s >= policy.idle_checkin_s:
        allowed.add("idle_checkin")
    if policy.concept_explanations:
        allowed.add("concept_explanation")
    if policy.debug_help:
        allowed.add("debug_help")
    if policy.clarification_style == "full":
        allowed.add("clarification_detail")
    if policy.unsolicited_nudges:
        allowed.add("unsolicited_nudge")
    return allowed


def time_limit_for(policy: ModePolicy, multiplier: float) -> int | None:
    """Apply an accommodation multiplier (1.0-2.0) to the time contract."""
    if policy.time_limit_s is None:
        return None
    return round(policy.time_limit_s * max(1.0, min(multiplier, 2.0)))
