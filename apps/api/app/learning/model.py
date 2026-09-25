"""MVP learner model: explicit, bounded, replayable capability updates.

The aggregate state for one capability is a pure function of its evidence list, so deleting the
aggregate and replaying evidence always reproduces it. All weights are named constants here and
documented in `docs/learning-model.md`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Band = Literal["Weak", "Developing", "Reliable", "Strong"]

MODEL_VERSION = "learner-model/v1"
LEARNING_RATE = 0.4
MAX_STEP = 0.25
# Neutral starting estimate: one clean success reaches "Developing", one miss drops to "Weak".
PRIOR_MASTERY = 0.3
MAX_STABILITY_DAYS = 60.0
HINT_PENALTY = {0: 0.0, 1: 0.1, 2: 0.2, 3: 0.35, 4: 0.5, 5: 0.65}
ASSISTED_SCORE_CAP = 0.5
REPEAT_EXPOSURE_WEIGHT = 0.5
TRANSFER_WEIGHT = 1.25
REPEAT_GROWTH_CAP = 1.2
SUCCESS_THRESHOLD = 0.7
FAILURE_THRESHOLD = 0.4
# How demanding each evidence type is; harder evidence moves the estimate more.
EXERCISE_DIFFICULTY: dict[str, float] = {
    "recall": 0.3,
    "recognition": 0.45,
    "key_insight": 0.5,
    "explain": 0.55,
    "confirmation": 0.35,
    "trace": 0.6,
    "pseudocode": 0.6,
    "debug": 0.7,
    "code_fragment": 0.7,
    "implementation": 0.85,
    "interview": 0.9,
    "transfer": 1.0,
    "mock_interview": 1.0,
    "reinterview": 1.0,
}
INDEPENDENT_TYPES = {"implementation", "interview", "transfer", "mock_interview", "reinterview"}
BAND_THRESHOLDS: tuple[tuple[float, Band], ...] = (
    (0.35, "Weak"),
    (0.6, "Developing"),
    (0.8, "Reliable"),
)
TYPE_LABELS = {
    "recall": "recall",
    "recognition": "pattern recognition",
    "key_insight": "key-insight check",
    "explain": "explanation",
    "confirmation": "confirmation question",
    "trace": "trace",
    "pseudocode": "pseudocode reconstruction",
    "debug": "debugging",
    "code_fragment": "code fragment",
    "implementation": "implementation",
    "interview": "practice interview",
    "transfer": "transfer problem",
    "mock_interview": "mock interview",
    "reinterview": "re-interview",
}


@dataclass(frozen=True)
class Evidence:
    occurred_at: datetime
    score: float
    confidence: float
    hint_level: int
    exercise_type: str
    assisted: bool = False
    transfer: bool = False
    repeat_exposure: bool = False
    excluded: bool = False


@dataclass(frozen=True)
class CapabilityState:
    mastery: float
    stability_days: float
    last_reviewed_at: datetime | None
    next_review_at: datetime | None
    evidence_count: int
    confidence: float
    band: Band
    explanation: str
    capability_type: str


def effective_score(evidence: Evidence) -> float:
    score = max(0.0, min(1.0, evidence.score))
    score *= 1 - HINT_PENALTY.get(max(0, min(5, evidence.hint_level)), 0.65)
    if evidence.assisted:
        score = min(score, ASSISTED_SCORE_CAP)
    return score


def evidence_weight(evidence: Evidence, days_since_previous: float | None) -> float:
    difficulty = EXERCISE_DIFFICULTY.get(evidence.exercise_type, 0.5)
    weight = max(0.0, min(1.0, evidence.confidence)) * (0.5 + 0.5 * difficulty)
    if evidence.repeat_exposure:
        weight *= REPEAT_EXPOSURE_WEIGHT
    if evidence.transfer and not evidence.assisted:
        weight *= TRANSFER_WEIGHT
    if days_since_previous is not None and days_since_previous > 1:
        # Success after a longer gap is stronger evidence of retention (bounded).
        weight *= 1 + min(0.5, days_since_previous / 30)
    return weight


def next_stability(
    current: float,
    score: float,
    confidence: float,
    gap_days: float | None = None,
    repeat_exposure: bool = False,
) -> float:
    """Review interval (days) after one piece of evidence.

    Growth on success is scaled by how much of the current interval actually elapsed, so
    massed practice (reviewing again long before the interval is up) earns little, and repeats
    of the same problem barely grow the interval because they mostly measure memory of that
    problem, not the skill.
    """
    if score >= SUCCESS_THRESHOLD:
        if current <= 0:
            return 1.0 if score < 0.9 else 2.0
        growth = 1.8 + 0.7 * score
        if repeat_exposure:
            growth = min(growth, REPEAT_GROWTH_CAP)
        if gap_days is not None:
            growth = 1 + (growth - 1) * min(1.0, max(0.0, gap_days) / current)
        return min(MAX_STABILITY_DAYS, current * growth)
    if score >= FAILURE_THRESHOLD:
        return min(MAX_STABILITY_DAYS, max(1.0, current * 1.2))
    if confidence < 0.5:
        # Uncertain failures shrink the interval rather than resetting it.
        return max(1.0, current * 0.6)
    return 1.0


def band_for(mastery: float, capability_type: str, evidence: Sequence[Evidence]) -> Band:
    band: Band = "Strong"
    for threshold, label in BAND_THRESHOLDS:
        if mastery < threshold:
            band = label
            break
    if band == "Strong":
        independent = [
            item
            for item in evidence
            if item.exercise_type in INDEPENDENT_TYPES
            and item.hint_level <= 1
            and not item.assisted
            and effective_score(item) >= SUCCESS_THRESHOLD
        ]
        if len(evidence) < 3 or not independent:
            band = "Reliable"
        if capability_type == "transfer" and not any(item.transfer for item in independent):
            band = "Reliable"
    if capability_type == "transfer" and all(item.assisted for item in evidence):
        # Solution exposure alone can never establish transfer.
        band = "Weak" if band == "Weak" else "Developing"
    return band


def explain(evidence: Sequence[Evidence], band: Band) -> str:
    recent = list(evidence)[-3:]
    if not recent:
        return "No evidence yet."
    misses = [item for item in recent if effective_score(item) < FAILURE_THRESHOLD]
    partial = [
        item for item in recent if FAILURE_THRESHOLD <= effective_score(item) < SUCCESS_THRESHOLD
    ]
    wins = [item for item in recent if effective_score(item) >= SUCCESS_THRESHOLD]
    parts = []
    plurals = {"miss": "misses", "partial success": "partial successes", "success": "successes"}

    def describe(items: list[Evidence], noun: str) -> str:
        types = sorted({TYPE_LABELS.get(item.exercise_type, item.exercise_type) for item in items})
        hint = max(item.hint_level for item in items)
        detail = f" with a level-{hint} hint" if hint else ""
        label = noun if len(items) == 1 else plurals[noun]
        return f"{len(items)} recent {label} in {', '.join(types)}{detail}"

    if misses:
        parts.append(describe(misses, "miss"))
    if partial:
        parts.append(describe(partial, "partial success"))
    if wins:
        parts.append(describe(wins, "success"))
    if any(item.assisted for item in recent):
        parts.append("some evidence came after viewing a solution")
    if any(item.repeat_exposure for item in recent):
        parts.append("repeated problems count for less")
    return f"{band}: " + "; ".join(parts) + "."


def compute_state(
    evidence: Sequence[Evidence], capability_type: str = "reasoning"
) -> CapabilityState:
    items = sorted((item for item in evidence if not item.excluded), key=lambda e: e.occurred_at)
    mastery = PRIOR_MASTERY
    stability = 0.0
    total_weight = 0.0
    previous: datetime | None = None
    for item in items:
        gap = (item.occurred_at - previous).total_seconds() / 86400 if previous else None
        weight = evidence_weight(item, gap)
        target = effective_score(item)
        step = LEARNING_RATE * weight * (target - mastery)
        mastery = max(0.0, min(1.0, mastery + max(-MAX_STEP, min(MAX_STEP, step))))
        stability = next_stability(stability, target, item.confidence, gap, item.repeat_exposure)
        total_weight += weight
        previous = item.occurred_at
    last = items[-1].occurred_at if items else None
    band = band_for(mastery, capability_type, items) if items else "Weak"
    return CapabilityState(
        mastery=round(mastery, 4),
        stability_days=round(stability, 3),
        last_reviewed_at=last,
        next_review_at=last + timedelta(days=stability) if last and stability else None,
        evidence_count=len(items),
        confidence=round(1 - math.exp(-total_weight), 3),
        band=band,
        explanation=explain(items, band),
        capability_type=capability_type,
    )
