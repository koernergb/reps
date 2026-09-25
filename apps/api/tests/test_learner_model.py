from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.learning.evidence import rebuild_user_state, recompute_capability, upsert_evidence
from app.learning.model import (
    MAX_STEP,
    PRIOR_MASTERY,
    Evidence,
    compute_state,
    effective_score,
)
from app.local_mode import LOCAL_USER_ID
from app.models import Capability, CapabilityEvidence, LearnerCapabilityState

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def ev(day: float = 0, score: float = 1.0, **kwargs: Any) -> Evidence:
    values: dict[str, Any] = {"confidence": 0.8, "hint_level": 0, "exercise_type": "interview"}
    values.update(kwargs)
    return Evidence(occurred_at=T0 + timedelta(days=day), score=score, **values)


@pytest.mark.parametrize(
    ("evidence", "check"),
    [
        ([ev(score=1.0)], lambda s: s.band == "Developing" and s.mastery > PRIOR_MASTERY),
        ([ev(score=0.0)], lambda s: s.band == "Weak" and s.mastery < PRIOR_MASTERY),
        (
            [ev(score=1.0, hint_level=3)],
            lambda s: s.mastery < compute_state([ev(score=1.0)]).mastery,
        ),
        (
            [ev(score=1.0, confidence=0.2)],
            lambda s: s.mastery < compute_state([ev(score=1.0)]).mastery,
        ),
        ([ev(day=i, score=1.0) for i in range(8)], lambda s: s.band == "Strong"),
        (
            [ev(day=i, score=1.0, exercise_type="recall") for i in range(8)],
            lambda s: s.band == "Reliable",
        ),
        ([ev(day=i, score=1.0, hint_level=2) for i in range(10)], lambda s: s.band != "Strong"),
        (
            [ev(day=i, score=1.0, repeat_exposure=True) for i in range(3)],
            lambda s: s.mastery < compute_state([ev(day=i, score=1.0) for i in range(3)]).mastery,
        ),
        ([ev(day=0, score=1.0), ev(day=1, score=0.0)], lambda s: s.stability_days == 1.0),
        ([ev(day=i * 3, score=1.0) for i in range(4)], lambda s: s.stability_days > 5),
        ([ev(day=i * 10, score=1.0) for i in range(4)], lambda s: s.stability_days > 20),
        (
            [
                ev(day=0, score=1.0),
                *[ev(day=i, score=1.0, repeat_exposure=True) for i in range(1, 6)],
            ],
            lambda s: s.stability_days < 7,
        ),
        ([ev(day=i * 0.01, score=1.0) for i in range(10)], lambda s: s.stability_days < 3),
        ([ev(score=1.0, excluded=True)], lambda s: s.evidence_count == 0),
    ],
)
def test_table_driven_updates(evidence: list[Evidence], check: Any) -> None:
    assert check(compute_state(evidence))


def test_assisted_evidence_cannot_establish_transfer() -> None:
    assisted = [
        ev(day=i, score=1.0, assisted=True, transfer=True, exercise_type="transfer")
        for i in range(10)
    ]
    state = compute_state(assisted, capability_type="transfer")
    assert state.band in ("Weak", "Developing")
    assert all(effective_score(item) <= 0.5 for item in assisted)


def test_transfer_needs_independent_transfer_for_strong() -> None:
    interviews = [ev(day=i, score=1.0) for i in range(8)]
    assert compute_state(interviews, "transfer").band == "Reliable"
    with_transfer = [*interviews, ev(day=9, score=1.0, transfer=True, exercise_type="transfer")]
    assert compute_state(with_transfer, "transfer").band == "Strong"


def test_explanation_is_plain_language() -> None:
    state = compute_state(
        [
            ev(day=0, score=0.2, exercise_type="debug", hint_level=2),
            ev(day=1, score=0.1, exercise_type="debug", hint_level=2),
        ]
    )
    assert state.explanation.startswith("Weak: 2 recent misses in debugging with a level-2 hint")
    assert "0." not in state.explanation


evidence_strategy = st.builds(
    Evidence,
    occurred_at=st.integers(0, 120).map(lambda day: T0 + timedelta(days=day)),
    score=st.floats(0, 1),
    confidence=st.floats(0, 1),
    hint_level=st.integers(0, 5),
    exercise_type=st.sampled_from(
        ["recall", "explain", "debug", "implementation", "interview", "transfer"]
    ),
    assisted=st.booleans(),
    transfer=st.booleans(),
    repeat_exposure=st.booleans(),
)


@settings(max_examples=200, deadline=None)
@given(st.lists(evidence_strategy, max_size=25))
def test_state_is_bounded_and_deterministic(items: list[Evidence]) -> None:
    state = compute_state(items)
    assert 0 <= state.mastery <= 1
    assert 0 <= state.confidence <= 1
    assert state.stability_days >= 0
    assert compute_state(list(reversed(items))) == compute_state(items) or len(
        {i.occurred_at for i in items}
    ) < len(items)


@settings(max_examples=200, deadline=None)
@given(st.lists(evidence_strategy, max_size=10), evidence_strategy)
def test_single_evidence_change_is_bounded(prefix: list[Evidence], item: Evidence) -> None:
    ordered = sorted(prefix, key=lambda e: e.occurred_at)
    later = Evidence(**{**item.__dict__, "occurred_at": T0 + timedelta(days=500)})
    before = compute_state(ordered).mastery
    after = compute_state([*ordered, later]).mastery
    assert abs(after - before) <= MAX_STEP + 1e-9


@settings(max_examples=150, deadline=None)
@given(st.lists(evidence_strategy, max_size=10), st.floats(0, 1), st.floats(0, 1))
def test_monotonic_in_score_for_comparable_evidence(
    prefix: list[Evidence], low: float, high: float
) -> None:
    low, high = sorted((low, high))
    ordered = sorted(prefix, key=lambda e: e.occurred_at)
    last = T0 + timedelta(days=500)
    worse = compute_state([*ordered, ev(day=500, score=low)]).mastery
    better = compute_state([*ordered, ev(day=500, score=high)]).mastery
    assert better >= worse - 1e-9
    assert last > T0


def test_duplicate_delivery_and_rebuild(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        capability = session.scalar(select(Capability).where(Capability.slug == "stack.invariant"))
        assert capability is not None
        for attempt in range(3):
            for _ in range(2):  # duplicate delivery of each evidence item
                upsert_evidence(
                    session,
                    user_id=LOCAL_USER_ID,
                    capability_id=capability.id,
                    source_type="review",
                    source_id=f"attempt-{attempt}",
                    dedupe_key=f"review:attempt-{attempt}",
                    occurred_at=T0 + timedelta(days=attempt),
                    score=0.9,
                    confidence=0.8,
                    hint_level=0,
                    exercise_type="explain",
                    explanation="test",
                )
        recompute_capability(session, LOCAL_USER_ID, capability.id)
        session.commit()
        assert session.scalar(
            select(CapabilityEvidence.id).where(CapabilityEvidence.dedupe_key == "review:attempt-0")
        )
        state = session.get(LearnerCapabilityState, (LOCAL_USER_ID, capability.id))
        assert state is not None and state.evidence_count == 3
        snapshot = (
            state.mastery,
            state.stability,
            state.band,
            state.explanation,
            state.evidence_count,
        )
        assert rebuild_user_state(session, LOCAL_USER_ID) == 1
        rebuilt = session.get(LearnerCapabilityState, (LOCAL_USER_ID, capability.id))
        assert rebuilt is not None
        assert (
            rebuilt.mastery,
            rebuilt.stability,
            rebuilt.band,
            rebuilt.explanation,
            rebuilt.evidence_count,
        ) == snapshot
