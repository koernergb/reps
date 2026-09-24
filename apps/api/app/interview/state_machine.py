"""Application-controlled interview state machine.

The LLM may *recommend* a transition; only `validate_transition` decides whether it happens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

State = Literal[
    "INTRO",
    "CLARIFICATION",
    "APPROACH_DISCUSSION",
    "IMPLEMENTATION",
    "TESTING",
    "COMPLEXITY",
    "FOLLOW_UP",
    "COMPLETE",
    "ABANDONED",
]
STATES: tuple[State, ...] = (
    "INTRO",
    "CLARIFICATION",
    "APPROACH_DISCUSSION",
    "IMPLEMENTATION",
    "TESTING",
    "COMPLEXITY",
    "FOLLOW_UP",
    "COMPLETE",
    "ABANDONED",
)
TERMINAL: frozenset[State] = frozenset({"COMPLETE", "ABANDONED"})
Trigger = Literal["learner", "interviewer", "execution", "timer", "system"]

# Forward progress plus the realistic backward moves (re-clarify, rethink, fix a bug).
TRANSITIONS: dict[State, frozenset[State]] = {
    "INTRO": frozenset({"CLARIFICATION", "APPROACH_DISCUSSION"}),
    "CLARIFICATION": frozenset({"APPROACH_DISCUSSION"}),
    "APPROACH_DISCUSSION": frozenset({"CLARIFICATION", "IMPLEMENTATION"}),
    "IMPLEMENTATION": frozenset({"APPROACH_DISCUSSION", "TESTING", "COMPLEXITY"}),
    "TESTING": frozenset({"IMPLEMENTATION", "COMPLEXITY"}),
    "COMPLEXITY": frozenset({"FOLLOW_UP", "COMPLETE"}),
    "FOLLOW_UP": frozenset({"COMPLETE"}),
    "COMPLETE": frozenset(),
    "ABANDONED": frozenset(),
}

NEXT_STATE: dict[State, State] = {
    "INTRO": "CLARIFICATION",
    "CLARIFICATION": "APPROACH_DISCUSSION",
    "APPROACH_DISCUSSION": "IMPLEMENTATION",
    "IMPLEMENTATION": "TESTING",
    "TESTING": "COMPLEXITY",
    "COMPLEXITY": "FOLLOW_UP",
    "FOLLOW_UP": "COMPLETE",
}


@dataclass(frozen=True)
class TransitionContext:
    executions: int
    has_code_changes: bool


class InvalidTransition(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_transition(
    current: State, target: State, trigger: Trigger, context: TransitionContext
) -> None:
    if current in TERMINAL:
        raise InvalidTransition("session_finished", "This interview has already ended.")
    if target == current:
        raise InvalidTransition("no_op_transition", f"The interview is already in {current}.")
    if target == "ABANDONED":
        if trigger not in ("learner", "system"):
            raise InvalidTransition("invalid_trigger", "Only the learner can abandon.")
        return
    if target == "COMPLETE" and trigger in ("learner", "timer", "system"):
        # Ending early is always allowed for the learner and the mock timer.
        return
    if target not in TRANSITIONS[current]:
        raise InvalidTransition("invalid_transition", f"Cannot move from {current} to {target}.")
    if target in ("TESTING", "COMPLEXITY") and not context.has_code_changes:
        raise InvalidTransition(
            "code_required", "Write some code before moving on to testing or complexity."
        )
    if target == "COMPLEXITY" and context.executions == 0 and trigger == "interviewer":
        raise InvalidTransition(
            "execution_required", "Run your code at least once before discussing complexity."
        )


def is_terminal(state: str) -> bool:
    return state in TERMINAL
