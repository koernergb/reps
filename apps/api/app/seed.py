from __future__ import annotations

from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import create_database_engine, create_session_factory
from app.local_mode import LOCAL_USER_ID
from app.models import (
    Capability,
    Problem,
    ProblemCapability,
    ProblemEvaluator,
    Topic,
    User,
)


def stable_id(kind: str, slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://reps.local/{kind}/{slug}"))


TOPICS: list[dict[str, str]] = [
    {"slug": "arrays-hashing", "name": "Arrays & Hashing"},
    {"slug": "stack", "name": "Stack"},
    {"slug": "binary-search", "name": "Binary Search"},
]

CAPABILITIES: list[dict[str, str]] = [
    {
        "slug": "hash-map-complement-recognition",
        "topic": "arrays-hashing",
        "name": "Recognize complement lookup",
        "description": "Recognize when prior values can be indexed to find a required complement.",
        "type": "recognition",
    },
    {
        "slug": "hash-map-single-pass-implementation",
        "topic": "arrays-hashing",
        "name": "Implement a single-pass hash map",
        "description": "Store and query values in an order that avoids reusing the same element.",
        "type": "implementation",
    },
    {
        "slug": "stack-matching-invariant",
        "topic": "stack",
        "name": "Maintain the unmatched-opener invariant",
        "description": "Use a stack to represent opening delimiters that still require a match.",
        "type": "reasoning",
    },
    {
        "slug": "binary-search-boundaries",
        "topic": "binary-search",
        "name": "Update binary-search boundaries",
        "description": "Move inclusive search boundaries without losing the target or looping forever.",
        "type": "implementation",
    },
    {
        "slug": "logarithmic-complexity",
        "topic": "binary-search",
        "name": "Explain logarithmic complexity",
        "description": "Explain why halving a search space produces logarithmic time.",
        "type": "complexity",
    },
]

PROBLEMS: list[dict[str, Any]] = [
    {
        "slug": "pair-sum-indices",
        "title": "Pair Sum Indices",
        "statement": "Given a list of integers and a target, return the indices of two distinct elements whose values add to the target. Exactly one valid pair exists.",
        "difficulty": "easy",
        "time_complexity": "O(n)",
        "space_complexity": "O(n)",
        "starter_code": "def pair_sum_indices(nums: list[int], target: int) -> list[int]:\n    pass\n",
        "examples": [{"input": {"nums": [4, 7, 1, 9], "target": 8}, "output": [1, 2]}],
        "constraints": ["2 <= len(nums) <= 10,000", "Return two distinct indices."],
        "visible_tests": [
            {"args": [[4, 7, 1, 9], 8], "expected": [1, 2]},
            {"args": [[3, 3], 6], "expected": [0, 1]},
        ],
        "reference_solution": "def pair_sum_indices(nums, target):\n    seen = {}\n    for index, value in enumerate(nums):\n        complement = target - value\n        if complement in seen:\n            return [seen[complement], index]\n        seen[value] = index\n    raise ValueError('pair required')\n",
        "hidden_tests": [
            {"args": [[-2, 5, 11, -7], 4], "expected": [2, 3]},
            {"args": [[0, 4, 0], 0], "expected": [0, 2]},
        ],
        "mistakes": [
            "Stores the current value before checking and reuses one index.",
            "Uses a nested scan.",
        ],
        "follow_ups": ["How would the tradeoff change if the input were sorted?"],
        "capabilities": [
            ("hash-map-complement-recognition", 0.6),
            ("hash-map-single-pass-implementation", 0.4),
        ],
    },
    {
        "slug": "balanced-delimiters",
        "title": "Balanced Delimiters",
        "statement": "Return whether a string containing only (), [], and {} is properly nested and every opening delimiter is closed by the matching type.",
        "difficulty": "easy",
        "time_complexity": "O(n)",
        "space_complexity": "O(n)",
        "starter_code": "def balanced_delimiters(text: str) -> bool:\n    pass\n",
        "examples": [{"input": {"text": "([]){}"}, "output": True}],
        "constraints": ["0 <= len(text) <= 10,000", "Input contains delimiter characters only."],
        "visible_tests": [
            {"args": ["([]){}"], "expected": True},
            {"args": ["([)]"], "expected": False},
        ],
        "reference_solution": "def balanced_delimiters(text):\n    pairs = {')': '(', ']': '[', '}': '{'}\n    stack = []\n    for char in text:\n        if char in pairs:\n            if not stack or stack.pop() != pairs[char]:\n                return False\n        else:\n            stack.append(char)\n    return not stack\n",
        "hidden_tests": [
            {"args": [""], "expected": True},
            {"args": ["]"], "expected": False},
            {"args": ["(("], "expected": False},
        ],
        "mistakes": ["Pops an empty stack.", "Does not reject unmatched opening delimiters."],
        "follow_ups": ["What does the stack represent after each character?"],
        "capabilities": [("stack-matching-invariant", 1.0)],
    },
    {
        "slug": "find-sorted-value",
        "title": "Find a Sorted Value",
        "statement": "Given an ascending list of distinct integers and a target, return its index or -1 when it is absent. Your solution must run in logarithmic time.",
        "difficulty": "easy",
        "time_complexity": "O(log n)",
        "space_complexity": "O(1)",
        "starter_code": "def find_sorted_value(nums: list[int], target: int) -> int:\n    pass\n",
        "examples": [{"input": {"nums": [-3, 0, 5, 12], "target": 5}, "output": 2}],
        "constraints": ["0 <= len(nums) <= 100,000", "Values are strictly increasing."],
        "visible_tests": [
            {"args": [[-3, 0, 5, 12], 5], "expected": 2},
            {"args": [[1, 4, 8], 6], "expected": -1},
        ],
        "reference_solution": "def find_sorted_value(nums, target):\n    left, right = 0, len(nums) - 1\n    while left <= right:\n        middle = left + (right - left) // 2\n        if nums[middle] == target:\n            return middle\n        if nums[middle] < target:\n            left = middle + 1\n        else:\n            right = middle - 1\n    return -1\n",
        "hidden_tests": [
            {"args": [[], 1], "expected": -1},
            {"args": [[7], 7], "expected": 0},
            {"args": [[1, 3, 9, 20], 20], "expected": 3},
        ],
        "mistakes": [
            "Uses a strict left < right condition and skips one candidate.",
            "Does not move beyond middle.",
        ],
        "follow_ups": ["Why is the running time logarithmic?"],
        "capabilities": [("binary-search-boundaries", 0.7), ("logarithmic-complexity", 0.3)],
    },
]


def seed_database(session: Session) -> None:
    if session.get(User, LOCAL_USER_ID) is None:
        session.add(
            User(
                id=LOCAL_USER_ID,
                email=None,
                display_name="Local learner",
                mode="local",
            )
        )

    topics_by_slug: dict[str, Topic] = {}
    for item in TOPICS:
        topic = session.scalar(select(Topic).where(Topic.slug == item["slug"]))
        if topic is None:
            topic = Topic(id=stable_id("topic", item["slug"]), **item)
            session.add(topic)
        topics_by_slug[item["slug"]] = topic

    capabilities_by_slug: dict[str, Capability] = {}
    for item in CAPABILITIES:
        capability = session.scalar(select(Capability).where(Capability.slug == item["slug"]))
        if capability is None:
            capability = Capability(
                id=stable_id("capability", item["slug"]),
                topic=topics_by_slug[item["topic"]],
                slug=item["slug"],
                name=item["name"],
                description=item["description"],
                capability_type=item["type"],
            )
            session.add(capability)
        capabilities_by_slug[item["slug"]] = capability

    for item in PROBLEMS:
        problem = session.scalar(select(Problem).where(Problem.slug == item["slug"]))
        if problem is not None:
            continue
        problem = Problem(
            id=stable_id("problem", item["slug"]),
            slug=item["slug"],
            title=item["title"],
            statement=item["statement"],
            difficulty=item["difficulty"],
            language="python",
            time_complexity=item["time_complexity"],
            space_complexity=item["space_complexity"],
            starter_code=item["starter_code"],
            examples=item["examples"],
            constraints=item["constraints"],
            visible_tests=item["visible_tests"],
            status="development",
        )
        problem.evaluator = ProblemEvaluator(
            reference_solution=item["reference_solution"],
            hidden_tests=item["hidden_tests"],
            common_mistakes=item["mistakes"],
            follow_up_questions=item["follow_ups"],
            evaluator_version=1,
        )
        capability_weights = cast(list[tuple[str, float]], item["capabilities"])
        for capability_slug, weight in capability_weights:
            problem.capability_links.append(
                ProblemCapability(capability=capabilities_by_slug[capability_slug], weight=weight)
            )
        session.add(problem)

    session.commit()


def main() -> None:
    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        seed_database(session)
    engine.dispose()


if __name__ == "__main__":
    main()
