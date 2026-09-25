import pytest

from app.interview.policy import MOCK, PRACTICE, allowed_interventions, time_limit_for
from app.interview.state_machine import (
    STATES,
    TERMINAL,
    TRANSITIONS,
    InvalidTransition,
    TransitionContext,
    validate_transition,
)

READY = TransitionContext(executions=1, has_code_changes=True)


@pytest.mark.parametrize(
    ("current", "target"),
    [(current, target) for current, targets in TRANSITIONS.items() for target in targets],
)
def test_every_declared_transition_is_valid(current: str, target: str) -> None:
    validate_transition(current, target, "learner", READY)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current in STATES
        for target in STATES
        if current not in TERMINAL
        and target not in TRANSITIONS[current]
        and target not in ("COMPLETE", "ABANDONED")
    ],
)
def test_undeclared_transitions_are_rejected(current: str, target: str) -> None:
    with pytest.raises(InvalidTransition):
        validate_transition(current, target, "interviewer", READY)  # type: ignore[arg-type]


@pytest.mark.parametrize("terminal", sorted(TERMINAL))
def test_terminal_states_accept_nothing(terminal: str) -> None:
    for target in STATES:
        with pytest.raises(InvalidTransition) as error:
            validate_transition(terminal, target, "learner", READY)  # type: ignore[arg-type]
        assert error.value.code == "session_finished"


def test_guards_require_code_and_execution() -> None:
    with pytest.raises(InvalidTransition) as error:
        validate_transition(
            "IMPLEMENTATION", "TESTING", "learner", TransitionContext(0, has_code_changes=False)
        )
    assert error.value.code == "code_required"
    with pytest.raises(InvalidTransition) as error:
        validate_transition(
            "IMPLEMENTATION", "COMPLEXITY", "interviewer", TransitionContext(0, True)
        )
    assert error.value.code == "execution_required"


def test_repeated_transition_and_trigger_rules() -> None:
    with pytest.raises(InvalidTransition) as error:
        validate_transition("TESTING", "TESTING", "learner", READY)
    assert error.value.code == "no_op_transition"
    with pytest.raises(InvalidTransition):
        validate_transition("INTRO", "ABANDONED", "interviewer", READY)
    validate_transition("INTRO", "COMPLETE", "learner", READY)
    validate_transition("IMPLEMENTATION", "COMPLETE", "timer", READY)
    with pytest.raises(InvalidTransition):
        validate_transition("INTRO", "COMPLETE", "interviewer", READY)


def test_practice_and_mock_allow_different_interventions_for_identical_context() -> None:
    practice = allowed_interventions(PRACTICE, hints_used=1, max_hint_level=1, idle_s=300.0)
    mock = allowed_interventions(MOCK, hints_used=1, max_hint_level=1, idle_s=300.0)
    assert "hint" in practice and "hint" not in mock
    assert "idle_checkin" in practice and "idle_checkin" not in mock
    assert {"concept_explanation", "debug_help", "unsolicited_nudge"} <= practice
    assert not {"concept_explanation", "debug_help", "unsolicited_nudge"} & mock
    fresh = allowed_interventions(MOCK, hints_used=0, max_hint_level=0, idle_s=0)
    assert "hint" in fresh


def test_time_multiplier_is_bounded_and_mock_only() -> None:
    assert time_limit_for(PRACTICE, 1.5) is None
    assert time_limit_for(MOCK, 1.0) == 45 * 60
    assert time_limit_for(MOCK, 1.5) == round(45 * 60 * 1.5)
    assert time_limit_for(MOCK, 5.0) == 45 * 60 * 2
    assert time_limit_for(MOCK, 0.5) == 45 * 60
