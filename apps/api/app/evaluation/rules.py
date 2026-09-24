"""Rule-based interpretation and fact-derived weaknesses.

`fact_weaknesses` are always included in a report because they follow directly from
deterministic evidence (execution results, hint levels, complexity answers). `rules_semantic`
is the offline stand-in for the LLM's semantic interpretation.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.corpus.loader import LoadedProblem
from app.evaluation.schemas import (
    Assessment,
    Claim,
    Facts,
    Level,
    Scorecard,
    ScoreDimension,
    Weakness,
)
from app.models import InterviewEvent

SCORECARD_RUBRIC = "scorecard/v1"


def _ids(events: Sequence[InterviewEvent], *types: str) -> list[str]:
    return [event.id for event in events if event.event_type in types]


def fact_weaknesses(
    facts: Facts, events: Sequence[InterviewEvent], problem: LoadedProblem
) -> list[Weakness]:
    topic = problem.definition.topic
    weaknesses: list[Weakness] = []
    submit_ids = _ids(events, "solution_submitted", "test_failure")
    hint_ids = _ids(events, "hint_given")
    if facts.submissions and not facts.passed_hidden:
        if "timeout" in facts.hidden_failure_kinds:
            weaknesses.append(
                Weakness(
                    capability=f"{topic}.complexity",
                    severity="medium",
                    explanation="Hidden tests timed out on larger inputs, which suggests the "
                    "solution's complexity is higher than needed.",
                    evidence_event_ids=submit_ids,
                    confidence=0.8,
                    source="facts",
                )
            )
        if {"wrong_answer", "error"} & set(facts.hidden_failure_kinds):
            weaknesses.append(
                Weakness(
                    capability=f"{topic}.boundaries",
                    severity="high" if facts.best_hidden_passed == 0 else "medium",
                    explanation=f"The final submission passed {facts.best_hidden_passed} of "
                    f"{facts.hidden_total} hidden tests; some cases produced wrong answers or "
                    "errors.",
                    evidence_event_ids=submit_ids,
                    confidence=0.8,
                    source="facts",
                )
            )
    if not facts.passed_hidden and facts.final_state not in ("ABANDONED",):
        weaknesses.append(
            Weakness(
                capability=f"{topic}.implementation",
                severity="high" if facts.submissions == 0 else "medium",
                explanation="No submission passed every test before the interview ended.",
                evidence_event_ids=submit_ids or _ids(events, "interview_completed"),
                confidence=0.7,
                source="facts",
            )
        )
    if facts.max_hint_level >= 1:
        severity = (
            "low"
            if facts.max_hint_level == 1
            else ("medium" if facts.max_hint_level <= 2 else "high")
        )
        weaknesses.append(
            Weakness(
                capability=f"{topic}.recognition",
                severity=severity,
                explanation=f"Needed hints up to level {facts.max_hint_level} of 5 to find "
                "the approach.",
                evidence_event_ids=hint_ids,
                confidence=0.75,
                source="facts",
            )
        )
        weaknesses.append(
            Weakness(
                capability="interview.independence",
                severity=severity,
                explanation=f"Used {facts.hints_used} hint(s) during the interview.",
                evidence_event_ids=hint_ids,
                confidence=0.9,
                source="facts",
            )
        )
    if facts.max_hint_level >= 3:
        weaknesses.append(
            Weakness(
                capability=f"{topic}.invariant",
                severity="medium",
                explanation="Needed a structural hint (level 3+), so the core invariant was "
                "not yet reliable.",
                evidence_event_ids=hint_ids,
                confidence=0.7,
                source="facts",
            )
        )
    if facts.solution_viewed:
        weaknesses.append(
            Weakness(
                capability="interview.independence",
                severity="high",
                explanation="Viewed the reference solution; later success on this problem "
                "counts as assisted.",
                evidence_event_ids=_ids(events, "solution_viewed"),
                confidence=1.0,
                source="facts",
            )
        )
    complexity_ids = _ids(events, "complexity_answer")
    if facts.complexity_time_correct is False or facts.complexity_space_correct is False:
        wrong = [
            label
            for label, ok in (
                ("time", facts.complexity_time_correct),
                ("space", facts.complexity_space_correct),
            )
            if ok is False
        ]
        weaknesses.append(
            Weakness(
                capability=f"{topic}.complexity",
                severity="medium",
                explanation=f"The stated {' and '.join(wrong)} complexity did not match "
                f"{problem.definition.time_complexity} time / "
                f"{problem.definition.space_complexity} space.",
                evidence_event_ids=complexity_ids,
                confidence=0.7,
                source="facts",
            )
        )
    return weaknesses


def rules_semantic(
    facts: Facts, events: Sequence[InterviewEvent]
) -> tuple[list[Claim], list[Weakness], Assessment, Assessment, float, Level]:
    strengths: list[Claim] = []
    weaknesses: list[Weakness] = []
    if facts.passed_hidden and facts.max_hint_level == 0:
        strengths.append(
            Claim(
                text="Reached a correct solution without hints.",
                evidence_event_ids=_ids(events, "test_success"),
            )
        )
    if facts.first_submission_passed:
        strengths.append(
            Claim(
                text="The first submission passed every test.",
                evidence_event_ids=_ids(events, "solution_submitted")[:1],
            )
        )
    if facts.complexity_time_correct and facts.complexity_space_correct:
        strengths.append(
            Claim(
                text="Stated time and space complexity correctly.",
                evidence_event_ids=_ids(events, "complexity_answer"),
            )
        )
    if facts.runs and facts.submissions and facts.passed_hidden:
        strengths.append(
            Claim(
                text="Ran visible tests before relying on the final submission.",
                evidence_event_ids=_ids(events, "run_tests")[:2],
            )
        )
    if facts.approach_before_code:
        strengths.append(
            Claim(
                text="Explained an approach before starting to code.",
                evidence_event_ids=_ids(events, "approach_proposed")[:1],
            )
        )
    else:
        weaknesses.append(
            Weakness(
                capability="interview.communication",
                severity="low",
                explanation="Started coding without first explaining an approach.",
                evidence_event_ids=_ids(events, "code_edit")[:1],
                confidence=0.5,
                source="rules",
            )
        )
    if facts.clarifications_asked == 0 and facts.learner_utterances > 0:
        weaknesses.append(
            Weakness(
                capability="interview.clarification",
                severity="low",
                explanation="Did not ask any clarifying questions about inputs or edge cases.",
                evidence_event_ids=_ids(events, "approach_proposed", "reasoning_statement")[:1],
                confidence=0.4,
                source="rules",
            )
        )
    if facts.submissions and not facts.runs and not facts.first_submission_passed:
        weaknesses.append(
            Weakness(
                capability="interview.testing",
                severity="low",
                explanation="Submitted without running visible tests first, and the "
                "submission failed.",
                evidence_event_ids=_ids(events, "solution_submitted")[:1],
                confidence=0.6,
                source="rules",
            )
        )
    utterances = facts.learner_utterances
    communication = Assessment(
        rating=1 if utterances == 0 else 2 if utterances < 3 else 3 if utterances < 7 else 4,
        summary=f"{utterances} explanation or question message(s) during the interview "
        "(rule-based estimate of how much reasoning was shared).",
    )
    reasoning_rating = 3 if facts.approach_before_code else 2
    if facts.max_hint_level >= 3:
        reasoning_rating = 1
    elif facts.max_hint_level >= 1:
        reasoning_rating = min(reasoning_rating, 2)
    reasoning = Assessment(
        rating=reasoning_rating,
        summary="Rule-based estimate from approach timing and hint depth.",
    )
    confidence = 0.55 if utterances >= 3 else 0.4
    if facts.passed_hidden and facts.max_hint_level == 0 and not facts.solution_viewed:
        transfer: Level = "medium" if facts.mode == "practice" else "high"
    elif facts.passed_hidden and facts.max_hint_level <= 2:
        transfer = "medium" if facts.mode == "mock" else "low"
    else:
        transfer = "low"
    return strengths, weaknesses, communication, reasoning, confidence, transfer


def scorecard(facts: Facts, reasoning: Assessment, communication: Assessment) -> Scorecard:
    if facts.passed_hidden and facts.first_submission_passed:
        correctness = ScoreDimension(score=4, explanation="First submission passed every test.")
    elif facts.passed_hidden:
        correctness = ScoreDimension(score=3, explanation="Passed every test after revisions.")
    elif facts.hidden_total and facts.best_hidden_passed * 2 >= facts.hidden_total:
        correctness = ScoreDimension(
            score=2,
            explanation=f"Best submission passed {facts.best_hidden_passed}/"
            f"{facts.hidden_total} hidden tests.",
        )
    else:
        correctness = ScoreDimension(score=1, explanation="No substantially passing submission.")
    if facts.complexity_time_correct and facts.complexity_space_correct:
        complexity = ScoreDimension(score=4, explanation="Time and space both correct.")
    elif facts.complexity_time_correct or facts.complexity_space_correct:
        complexity = ScoreDimension(score=3, explanation="One of time/space was correct.")
    elif facts.complexity_time_correct is None:
        complexity = ScoreDimension(score=1, explanation="Complexity was not discussed.")
    else:
        complexity = ScoreDimension(score=2, explanation="Stated complexity was incorrect.")
    if facts.solution_viewed:
        independence = ScoreDimension(score=1, explanation="Viewed the reference solution.")
    else:
        level = facts.max_hint_level
        independence = ScoreDimension(
            score=4 if level == 0 else 3 if level == 1 else 2 if level == 2 else 1,
            explanation="No hints used." if level == 0 else f"Highest hint level: {level}.",
        )
    return Scorecard(
        rubric_version=SCORECARD_RUBRIC,
        correctness=correctness,
        reasoning=ScoreDimension(score=reasoning.rating, explanation=reasoning.summary),
        communication=ScoreDimension(score=communication.rating, explanation=communication.summary),
        complexity=complexity,
        independence=independence,
    )
