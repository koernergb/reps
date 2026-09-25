"""Load and expand the curated corpus from `packages/problem-corpus`."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.corpus.schema import ExerciseDef, ExerciseFile, ProblemDef, Taxonomy, TestCase

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[4] / "packages" / "problem-corpus"

# Only generator-friendly builtins are available to trusted corpus expressions.
_SAFE_BUILTINS: dict[str, Any] = {
    "range": range,
    "list": list,
    "len": len,
    "str": str,
    "int": int,
    "sum": sum,
    "min": min,
    "max": max,
    "sorted": sorted,
    "reversed": reversed,
    "zip": zip,
    "enumerate": enumerate,
    "abs": abs,
    "tuple": tuple,
    "dict": dict,
    "chr": chr,
    "ord": ord,
}


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class ConcreteTest:
    id: str
    args: list[Any]
    expected: Any
    label: str | None = None


@dataclass(frozen=True)
class LoadedProblem:
    definition: ProblemDef
    path: Path
    visible_tests: list[ConcreteTest]
    hidden_tests: list[ConcreteTest]


@dataclass(frozen=True)
class LoadedExercise:
    definition: ExerciseDef
    path: Path
    starter_code: str | None = None


@dataclass(frozen=True)
class Corpus:
    taxonomy: Taxonomy
    problems: dict[str, LoadedProblem]
    exercises: dict[str, LoadedExercise]

    def problem(self, slug: str) -> LoadedProblem:
        try:
            return self.problems[slug]
        except KeyError as exc:
            raise CorpusError(f"unknown problem {slug}") from exc


def evaluate_expression(expression: str) -> Any:
    """Evaluate a trusted corpus generator expression with a restricted namespace."""
    return eval(
        compile(expression, "<corpus-expression>", "eval"),
        {"__builtins__": _SAFE_BUILTINS},
        {},
    )


def expand_tests(prefix: str, tests: list[TestCase]) -> list[ConcreteTest]:
    expanded: list[ConcreteTest] = []
    for index, test in enumerate(tests, start=1):
        args = test.args if test.args is not None else evaluate_expression(test.args_expr or "")
        if not isinstance(args, list):
            raise CorpusError(f"{prefix}{index}: args must evaluate to a list")
        expected = (
            evaluate_expression(test.expected_expr)
            if test.expected_expr is not None
            else test.expected
        )
        expanded.append(ConcreteTest(f"{prefix}{index}", args, expected, test.label))
    return expanded


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_corpus(corpus_dir: Path | None = None) -> Corpus:
    root = corpus_dir or DEFAULT_CORPUS_DIR
    taxonomy = Taxonomy.model_validate(_read_yaml(root / "taxonomy.yaml"))
    problems: dict[str, LoadedProblem] = {}
    for path in sorted((root / "problems").rglob("*.yaml")):
        try:
            definition = ProblemDef.model_validate(_read_yaml(path))
        except Exception as exc:
            raise CorpusError(f"{path.relative_to(root)}: {exc}") from exc
        if definition.slug in problems:
            raise CorpusError(f"duplicate problem slug {definition.slug}")
        problems[definition.slug] = LoadedProblem(
            definition=definition,
            path=path,
            visible_tests=expand_tests("v", definition.visible_tests),
            hidden_tests=expand_tests("h", definition.hidden_tests),
        )
    exercises: dict[str, LoadedExercise] = {}
    for path in sorted((root / "exercises").glob("*.yaml")):
        try:
            exercise_file = ExerciseFile.model_validate(_read_yaml(path))
        except Exception as exc:
            raise CorpusError(f"{path.relative_to(root)}: {exc}") from exc
        for exercise in exercise_file.exercises:
            if exercise.id in exercises:
                raise CorpusError(f"duplicate exercise id {exercise.id}")
            starter = exercise.starter_code
            if exercise.from_mistake and exercise.problem in problems:
                wrong = [
                    item
                    for item in problems[exercise.problem].definition.wrong_solutions
                    if item.mistake == exercise.from_mistake
                ]
                if not wrong:
                    raise CorpusError(f"exercise {exercise.id}: unknown mistake")
                starter = wrong[0].code
            exercises[exercise.id] = LoadedExercise(
                definition=exercise, path=path, starter_code=starter
            )
    return Corpus(taxonomy=taxonomy, problems=problems, exercises=exercises)


@lru_cache(maxsize=1)
def get_corpus() -> Corpus:
    return load_corpus()
