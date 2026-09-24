"""Versioned post-interview report schema (REPORT_SCHEMA_VERSION)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REPORT_SCHEMA_VERSION = 1
Severity = Literal["low", "medium", "high"]
Level = Literal["low", "medium", "high"]
Result = Literal[
    "solved_independently",
    "solved_with_minor_hints",
    "solved_with_major_hints",
    "solved_after_solution_view",
    "incomplete",
    "failed",
    "timed_out",
    "abandoned",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Facts(Strict):
    """Deterministic facts. Nothing here comes from a model."""

    result: Result
    passed_hidden: bool
    best_hidden_passed: int
    hidden_total: int
    visible_passed: int
    visible_total: int
    runs: int
    submissions: int
    first_submission_passed: bool
    hidden_failure_kinds: list[str]
    hints_used: int
    max_hint_level: int
    solution_viewed: bool
    clarifications_asked: int
    learner_utterances: int
    approach_before_code: bool
    complexity_time_correct: bool | None
    complexity_space_correct: bool | None
    duration_s: int
    final_state: str
    mode: Literal["practice", "mock"]


class Claim(Strict):
    text: str = Field(max_length=400)
    evidence_event_ids: list[str]


class Weakness(Strict):
    capability: str
    severity: Severity
    explanation: str = Field(max_length=400)
    evidence_event_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    source: Literal["facts", "rules", "llm"]


class Assessment(Strict):
    rating: int = Field(ge=1, le=4)
    summary: str = Field(max_length=500)


class ScoreDimension(Strict):
    score: int = Field(ge=1, le=4)
    explanation: str


class Scorecard(Strict):
    rubric_version: str
    correctness: ScoreDimension
    reasoning: ScoreDimension
    communication: ScoreDimension
    complexity: ScoreDimension
    independence: ScoreDimension


class Report(Strict):
    schema_version: int = REPORT_SCHEMA_VERSION
    problem_slug: str
    facts: Facts
    strengths: list[Claim]
    weaknesses: list[Weakness]
    misconceptions: list[Claim]
    communication: Assessment
    reasoning: Assessment
    confidence: float = Field(ge=0, le=1)
    transfer_confidence: Level
    scorecard: Scorecard | None
    interpretation_source: Literal["llm", "rules"]
    notes: list[str]


# --- LLM output schema: semantic interpretation only ------------------------------------


class SemanticClaim(Strict):
    text: str
    evidence_sequences: list[int]


class SemanticWeakness(Strict):
    capability: str
    severity: Severity
    explanation: str
    evidence_sequences: list[int]
    confidence: float


class SemanticEvaluation(Strict):
    strengths: list[SemanticClaim]
    weaknesses: list[SemanticWeakness]
    misconceptions: list[SemanticClaim]
    communication_rating: int
    communication_summary: str
    reasoning_rating: int
    reasoning_summary: str
    overall_confidence: float
    transfer_confidence: Level
