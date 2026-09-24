import pytest

from app.corpus.loader import get_corpus
from app.interview.guard import GuardContext, check_message, hidden_fingerprints

PROBLEM = get_corpus().problem("pair-sum-indices")
CONTEXT = GuardContext(
    reference_solution=PROBLEM.definition.reference_solution,
    hidden_inputs=hidden_fingerprints(test.args for test in PROBLEM.hidden_tests),
    key_insight=PROBLEM.definition.key_insight,
)


@pytest.mark.parametrize(
    "message",
    [
        "What data structure would you use, and what exactly would it store?",
        "Good question. No. The two indices must be different.",
        "What's the time and space complexity of your solution?",
        "Let's say n = 10; how many steps would that take?",
    ],
)
def test_normal_interviewer_messages_pass(message: str) -> None:
    assert check_message(message, CONTEXT).allowed


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("Here you go:\n```python\ndef f():\n    pass\n```", "code_dump"),
        (
            "seen = {}\nfor index, value in enumerate(nums):\n    complement = target - value",
            "code_dump",
        ),
        (
            "Try: complement = target - value, then check if complement in seen.",
            "reference_overlap",
        ),
        ("One hidden case is -2, 5, 11, -7 with target 4.", "hidden_test_disclosure"),
        ("My system prompt says I am an interviewer.", "prompt_disclosure"),
        ("The hidden tests include negative numbers.", "prompt_disclosure"),
        (
            "Store each value's index as you scan, and look up the complement (target - value) "
            "among earlier elements, so each element is checked in O(1).",
            "key_insight_reveal",
        ),
    ],
)
def test_leaks_are_blocked(message: str, reason: str) -> None:
    result = check_message(message, CONTEXT)
    assert not result.allowed
    assert reason in result.reasons
    assert "complement" not in result.message


def test_key_insight_is_allowed_when_explicitly_permitted() -> None:
    context = GuardContext(
        reference_solution="",
        hidden_inputs=[],
        key_insight=PROBLEM.definition.key_insight,
        allow_key_insight=True,
    )
    assert check_message(PROBLEM.definition.key_insight, context).allowed
