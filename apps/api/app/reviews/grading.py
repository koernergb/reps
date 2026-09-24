"""Answer grading for review exercises.

Deterministic first: exact accepted answers and rubric keyword coverage. An LLM grader, when
configured, interprets free-text answers against the same rubric; its output is validated and
the deterministic grade is used if it is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.llm.prompts import fence, load_prompt
from app.llm.provider import LLMProvider, LLMUnavailable

Action = Literal["advance", "review", "coach", "rebuild"]
PROMPT_VERSION = "v1"
WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "to",
    "of",
    "and",
    "or",
    "in",
    "it",
    "that",
    "this",
    "we",
    "you",
    "be",
    "so",
    "for",
    "with",
    "on",
    "at",
    "by",
    "as",
    "its",
    "each",
    "can",
    "if",
    "then",
}


class AnswerGrade(BaseModel):
    correctness: float = Field(ge=0, le=1)
    missing_points: list[str]
    misconceptions: list[str]
    recommended_action: Action
    feedback: str


@dataclass(frozen=True)
class Rubric:
    prompt: str
    key_points: list[list[str]]
    accepted_answers: list[str]
    reference: str
    misconception: str | None


def normalize(text: str) -> str:
    return " ".join(WORD.findall(text.lower()))


def compact(text: str) -> str:
    return re.sub(r"[\s\[\](){},'\"]", "", text.lower())


def action_for(correctness: float, has_misconception_signal: bool) -> Action:
    if correctness >= 0.8:
        return "advance"
    if correctness >= 0.5:
        return "review"
    return "rebuild" if has_misconception_signal else "coach"


def rubric_grade(rubric: Rubric, answer: str) -> AnswerGrade:
    stripped = answer.strip()
    if rubric.accepted_answers:
        if any(compact(stripped) == compact(option) for option in rubric.accepted_answers):
            return AnswerGrade(
                correctness=1.0,
                missing_points=[],
                misconceptions=[],
                recommended_action="advance",
                feedback="Correct.",
            )
        if not rubric.key_points:
            return AnswerGrade(
                correctness=0.0,
                missing_points=["exact result"],
                misconceptions=[],
                recommended_action=action_for(0.0, bool(rubric.misconception)),
                feedback="That doesn't match the expected result. Compare with the reference.",
            )
    normalized = f" {normalize(stripped)} "
    matched: list[bool] = []
    for alternatives in rubric.key_points:
        matched.append(
            any(
                f" {normalize(option)} " in normalized or normalize(option) in normalized
                for option in alternatives
                if normalize(option)
            )
        )
    coverage = sum(matched) / len(matched) if matched else 0.0
    if len(WORD.findall(stripped)) < 3:
        coverage = min(coverage, 0.3)
    missing = [
        alternatives[0]
        for alternatives, hit in zip(rubric.key_points, matched, strict=True)
        if not hit
    ]
    correctness = round(coverage, 2)
    return AnswerGrade(
        correctness=correctness,
        missing_points=missing,
        misconceptions=[],
        recommended_action=action_for(
            correctness, bool(rubric.misconception) and correctness < 0.3
        ),
        feedback=(
            "Solid answer."
            if correctness >= 0.8
            else "Partly there. Missing: " + ", ".join(missing[:3]) + "."
            if missing
            else "Compare your answer with the reference."
        ),
    )


def overlap_grade(reference: str, answer: str) -> AnswerGrade:
    """Rubric-free grading against a reference text (key-insight and pseudocode checks)."""
    wanted = {word for word in WORD.findall(reference.lower()) if word not in STOPWORDS}
    given = {word for word in WORD.findall(answer.lower()) if word not in STOPWORDS}
    ratio = len(wanted & given) / len(wanted) if wanted else 0.0
    correctness = round(min(1.0, ratio / 0.45), 2)
    if len(given) < 4:
        correctness = min(correctness, 0.3)
    return AnswerGrade(
        correctness=correctness,
        missing_points=[] if correctness >= 0.8 else ["core idea"],
        misconceptions=[],
        recommended_action=action_for(correctness, False),
        feedback="That captures the idea."
        if correctness >= 0.8
        else "Some of the core idea is missing. Compare with the reference below.",
    )


def llm_grade(provider: LLMProvider, rubric: Rubric, answer: str) -> tuple[AnswerGrade, str]:
    template = load_prompt("grader", PROMPT_VERSION)
    system = template.render(
        prompt=rubric.prompt,
        key_points="; ".join(" / ".join(options) for options in rubric.key_points)
        or "(see reference)",
        reference=rubric.reference,
        misconception=rubric.misconception or "none specified",
        answer=fence("learner_answer", answer, 3000),
    )
    result = provider.generate(system=system, user="Grade the answer.", schema=AnswerGrade)
    return result.value, template.id


def grade(rubric: Rubric, answer: str, provider: LLMProvider | None) -> tuple[AnswerGrade, str]:
    """Returns (grade, grader id)."""
    if rubric.accepted_answers and not rubric.key_points:
        return rubric_grade(rubric, answer), "rubric/v1"
    deterministic = (
        rubric_grade(rubric, answer)
        if rubric.key_points
        else overlap_grade(rubric.reference, answer)
    )
    if provider is None or (deterministic.correctness == 1.0 and rubric.accepted_answers):
        return deterministic, "rubric/v1" if rubric.key_points else "overlap/v1"
    try:
        graded, prompt_id = llm_grade(provider, rubric, answer)
    except LLMUnavailable:
        return deterministic, "rubric/v1-fallback"
    return graded, prompt_id
