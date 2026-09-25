"""Versioned schema for curated corpus content.

Corpus files are trusted, human-reviewed repository content. Learner-facing responses must be
built from the public fields only; evaluator fields (hidden tests, reference and wrong
solutions, hints, clarifications, follow-ups, mistakes) stay server-side.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CORPUS_SCHEMA_VERSION = 1

CapabilityType = Literal[
    "recall",
    "recognition",
    "reasoning",
    "implementation",
    "debugging",
    "communication",
    "complexity",
    "independence",
    "transfer",
]
Difficulty = Literal["easy", "medium", "hard"]
ProblemRole = Literal["recognition", "canonical", "boundary", "transfer"]
ContentStatus = Literal["development", "reviewed", "retired"]
Comparison = Literal["exact", "unordered", "nested_unordered", "float"]
Adapter = Literal["linked_list", "tree"]
ExerciseType = Literal["recall", "recognition", "explain", "trace", "debug", "code_fragment"]
ExpectedFailure = Literal["wrong_answer", "timeout", "error"]

MAX_PER_TEST_TIMEOUT_S = 5.0


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TopicDef(Strict):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    parent: str | None = None


class CapabilityDef(Strict):
    slug: str = Field(pattern=r"^[a-z0-9-]+\.[a-z0-9-]+$")
    topic: str
    name: str
    description: str
    type: CapabilityType


class Taxonomy(Strict):
    schema_version: Literal[1]
    topics: list[TopicDef]
    capabilities: list[CapabilityDef]


class TestCase(Strict):
    args: list[Any] | None = None
    # Trusted corpus-only generator for large performance inputs, evaluated with a restricted
    # namespace at load time. Never accepts learner content.
    args_expr: str | None = None
    expected: Any = None
    expected_expr: str | None = None
    label: str | None = None

    @model_validator(mode="after")
    def one_arg_source(self) -> TestCase:
        if (self.args is None) == (self.args_expr is None):
            raise ValueError("a test needs exactly one of args or args_expr")
        if self.expected_expr is not None and self.expected is not None:
            raise ValueError("a test cannot set both expected and expected_expr")
        return self


class Example(Strict):
    input: dict[str, Any]
    output: Any
    explanation: str | None = None


class Clarification(Strict):
    question: str
    answer: str


class Mistake(Strict):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str
    capability: str


class WrongSolution(Strict):
    mistake: str
    expect: ExpectedFailure
    code: str


class Weight(Strict):
    slug: str
    weight: float = Field(gt=0, le=1)


class ProblemDef(Strict):
    schema_version: Literal[1]
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    version: int = Field(ge=1)
    status: ContentStatus
    title: str
    topic: str
    patterns: list[str] = Field(min_length=1)
    role: ProblemRole
    difficulty: Difficulty
    transfer_group: str
    prerequisites: list[str] = []
    related: list[str] = []
    statement: str
    examples: list[Example] = Field(min_length=1)
    constraints: list[str] = Field(min_length=1)
    kind: Literal["function", "class"] = "function"
    entrypoint: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    input_adapters: list[Adapter | None] = []
    output_adapter: Adapter | None = None
    comparison: Comparison = "exact"
    per_test_timeout_s: float = Field(default=2.0, gt=0, le=MAX_PER_TEST_TIMEOUT_S)
    starter_code: str
    time_complexity: str
    space_complexity: str
    capabilities: list[Weight] = Field(min_length=1)
    hints: list[str] = Field(min_length=5, max_length=5)
    key_insight: str
    clarifications: list[Clarification] = Field(min_length=1)
    follow_ups: list[str] = Field(min_length=1)
    common_mistakes: list[Mistake] = Field(min_length=1)
    visible_tests: list[TestCase] = Field(min_length=1)
    hidden_tests: list[TestCase] = Field(min_length=2)
    reference_solution: str
    wrong_solutions: list[WrongSolution] = Field(min_length=1)

    @field_validator("capabilities")
    @classmethod
    def unique_capabilities(cls, value: list[Weight]) -> list[Weight]:
        slugs = [item.slug for item in value]
        if len(slugs) != len(set(slugs)):
            raise ValueError("duplicate capability weight")
        return value


class ExerciseDef(Strict):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    capability: str
    type: ExerciseType
    prompt: str
    problem: str | None = None
    # Free-text grading rubric: each key point lists accepted phrasings (any match).
    key_points: list[list[str]] = []
    reference_answer: str
    # Deterministic answers for trace/recognition items (normalized comparison).
    accepted_answers: list[str] = []
    # Code exercises reuse the linked problem's execution spec and tests (visible detail,
    # hidden aggregate). `from_mistake` seeds a debug exercise with a known-wrong solution.
    starter_code: str | None = None
    from_mistake: str | None = None
    hints: list[str] = Field(min_length=1, max_length=4)
    misconception: str | None = None
    confirmation_question: str | None = None
    estimated_minutes: float = Field(gt=0, le=15)
    status: ContentStatus = "development"

    @model_validator(mode="after")
    def grading_available(self) -> ExerciseDef:
        if self.type in ("debug", "code_fragment"):
            if not self.problem:
                raise ValueError("code exercises must link a problem for execution")
            if not (self.starter_code or self.from_mistake):
                raise ValueError("code exercises need starter_code or from_mistake")
        elif not (self.key_points or self.accepted_answers):
            raise ValueError("text exercises need key_points or accepted_answers")
        return self


class ExerciseFile(Strict):
    schema_version: Literal[1]
    topic: str
    exercises: list[ExerciseDef]
