"""Deterministic output guard for interviewer messages.

Runs on every interviewer message (LLM or policy) before it is stored or shown. It blocks
code dumps, reference-solution overlap, hidden-test disclosure, prompt disclosure, and
premature reveal of the key insight. The hint ladder is the only sanctioned path to the key
insight, and it bypasses this guard by design because hint text is curated corpus content.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

CODE_FENCE = re.compile(r"```|~~~")
CODE_LINE = re.compile(
    r"^\s*(def |class |for .+:|while .+:|if .+:|return\b|import |from \w+ import|\w+\s*=\s*.+)",
    re.MULTILINE,
)
PROMPT_MARKERS = (
    "system prompt",
    "you are a technical interviewer",
    "<problem_statement>",
    "<learner_message>",
    "hidden test",
    "reference solution",
    "evaluator material",
    "policy_version",
)
TOKEN = re.compile(r"[a-z_][a-z0-9_]*|\d+|[^\sa-z0-9_]", re.IGNORECASE)
SAFE_FALLBACK = (
    "I can't share that, but I'm happy to keep going. "
    "Tell me what you're thinking and I'll respond to your reasoning."
)


@dataclass(frozen=True)
class GuardContext:
    reference_solution: str
    hidden_inputs: list[str]
    key_insight: str
    allow_key_insight: bool = False


@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    message: str
    reasons: list[str]


COMPACT_STRIP = re.compile(r"[\s\[\]()'\"]")


def compact(text: str) -> str:
    return COMPACT_STRIP.sub("", text.lower())


def hidden_fingerprints(test_args: Iterable[list[Any]]) -> list[str]:
    """Compact fingerprints of hidden inputs that would identify a test if echoed."""
    prints: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, list):
            scalars = [item for item in value if isinstance(item, (int, float, str))]
            if len(value) >= 3 and len(scalars) == len(value) and len(value) <= 200:
                prints.add(compact(",".join(str(item) for item in value)))
            for item in value[:50]:
                visit(item)
        elif isinstance(value, str) and len(value) >= 8:
            prints.add(compact(value[:200]))

    for args in test_args:
        visit(args)
    return sorted(item for item in prints if len(item) >= 6)


def _ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    tokens = [token.lower() for token in TOKEN.findall(text)]
    return {tuple(tokens[index : index + n]) for index in range(len(tokens) - n + 1)}


def _reference_lines(reference: str) -> list[str]:
    lines = []
    for line in reference.splitlines():
        stripped = re.sub(r"\s+", " ", line.strip())
        if len(stripped) >= 18 and not stripped.startswith(("def ", "return ", "#")):
            lines.append(stripped.lower())
    return lines


def check_message(message: str, context: GuardContext) -> GuardResult:
    reasons: list[str] = []
    lowered = message.lower()
    normalized = re.sub(r"\s+", " ", lowered)
    if CODE_FENCE.search(message) or len(CODE_LINE.findall(message)) >= 2:
        reasons.append("code_dump")
    overlap = sum(1 for line in _reference_lines(context.reference_solution) if line in normalized)
    if overlap >= 1:
        reasons.append("reference_overlap")
    reference_grams = _ngrams(context.reference_solution, 6)
    if reference_grams and len(_ngrams(message, 6) & reference_grams) >= 3:
        reasons.append("reference_overlap")
    compact_message = compact(message)
    if any(fingerprint in compact_message for fingerprint in context.hidden_inputs):
        reasons.append("hidden_test_disclosure")
    if any(marker in lowered for marker in PROMPT_MARKERS):
        reasons.append("prompt_disclosure")
    if not context.allow_key_insight and context.key_insight:
        insight_grams = _ngrams(context.key_insight, 5)
        if insight_grams and len(_ngrams(message, 5) & insight_grams) / len(insight_grams) > 0.5:
            reasons.append("key_insight_reveal")
    unique = sorted(set(reasons))
    if unique:
        return GuardResult(False, SAFE_FALLBACK, unique)
    return GuardResult(True, message, [])
