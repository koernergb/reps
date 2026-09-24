"""Corpus lint, execution validation, and coverage reporting.

Usage::

    python -m app.corpus.validate            # structural lint only
    python -m app.corpus.validate --execute  # also run reference and known-wrong solutions
    python -m app.corpus.validate --report   # print the coverage report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.corpus.loader import ConcreteTest, Corpus, LoadedProblem, load_corpus
from app.execution.backends import ExecutionBackend, SandboxLimits, TrustedSubprocessBackend
from app.execution.evaluate import ExecutionSpec, execute_tests

MIN_REFERENCE_LINE_CHARS = 24


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def spec_for(problem: LoadedProblem) -> ExecutionSpec:
    definition = problem.definition
    return ExecutionSpec(
        entrypoint=definition.entrypoint,
        kind=definition.kind,
        input_adapters=tuple(definition.input_adapters),
        output_adapter=definition.output_adapter,
        comparison=definition.comparison,
        per_test_timeout_s=definition.per_test_timeout_s,
    )


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for neighbor in graph.get(node, []):
            if state.get(neighbor) == 1:
                return [*stack[stack.index(neighbor) :], neighbor]
            if state.get(neighbor) is None:
                found = visit(neighbor)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in graph:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return None


def lint(corpus: Corpus) -> ValidationReport:
    report = ValidationReport()
    topics = {topic.slug for topic in corpus.taxonomy.topics}
    capabilities = {cap.slug: cap for cap in corpus.taxonomy.capabilities}
    if len(capabilities) != len(corpus.taxonomy.capabilities):
        report.error("taxonomy: duplicate capability slug")
    for capability in corpus.taxonomy.capabilities:
        if capability.topic not in topics:
            report.error(f"taxonomy: {capability.slug} references unknown topic")

    transfer_groups: dict[str, list[str]] = defaultdict(list)
    for slug, problem in corpus.problems.items():
        definition = problem.definition
        where = f"problem {slug}"
        if problem.path.stem != slug:
            report.error(f"{where}: file name must match slug")
        if definition.topic not in topics:
            report.error(f"{where}: unknown topic {definition.topic}")
        for weight in definition.capabilities:
            if weight.slug not in capabilities:
                report.error(f"{where}: unknown capability {weight.slug}")
        total_weight = sum(weight.weight for weight in definition.capabilities)
        if abs(total_weight - 1.0) > 1e-6:
            report.error(f"{where}: capability weights sum to {total_weight:.2f}, expected 1.0")
        mistake_ids = {mistake.id for mistake in definition.common_mistakes}
        for mistake in definition.common_mistakes:
            if mistake.capability not in capabilities:
                report.error(f"{where}: mistake {mistake.id} has unknown capability")
        for wrong in definition.wrong_solutions:
            if wrong.mistake not in mistake_ids:
                report.error(f"{where}: wrong solution references unknown mistake {wrong.mistake}")
        for reference in [*definition.prerequisites, *definition.related]:
            if reference not in corpus.problems:
                report.error(f"{where}: dangling problem reference {reference}")
            if reference == slug:
                report.error(f"{where}: references itself")
        seen_args: set[str] = set()
        for test in [*problem.visible_tests, *problem.hidden_tests]:
            key = json.dumps(test.args, sort_keys=True)
            if key in seen_args:
                report.error(f"{where}: duplicate test input {test.id}")
            seen_args.add(key)
        if definition.input_adapters and len(definition.input_adapters) > len(
            problem.visible_tests[0].args
        ):
            report.error(f"{where}: more input adapters than arguments")
        public_text = "\n".join(
            [
                definition.statement,
                definition.starter_code,
                json.dumps([example.model_dump() for example in definition.examples]),
                *definition.constraints,
            ]
        )
        for line in definition.reference_solution.splitlines():
            stripped = line.strip()
            if len(stripped) >= MIN_REFERENCE_LINE_CHARS and stripped in public_text:
                report.error(f"{where}: public content exposes reference line {stripped!r}")
        hidden_keys = {json.dumps(test.args, sort_keys=True) for test in problem.hidden_tests}
        for example in definition.examples:
            if json.dumps(list(example.input.values()), sort_keys=True) in hidden_keys:
                report.error(f"{where}: an example duplicates a hidden test")
        transfer_groups[definition.transfer_group].append(slug)

    cycle = _find_cycle(
        {slug: list(problem.definition.prerequisites) for slug, problem in corpus.problems.items()}
    )
    if cycle:
        report.error(f"circular prerequisites: {' -> '.join(cycle)}")

    for group, members in transfer_groups.items():
        if len(members) < 2:
            report.warnings.append(f"transfer group {group} has a single problem: {members[0]}")

    for exercise_id, exercise in corpus.exercises.items():
        exercise_def = exercise.definition
        if exercise_def.capability not in capabilities:
            report.error(f"exercise {exercise_id}: unknown capability {exercise_def.capability}")
        if exercise_def.problem and exercise_def.problem not in corpus.problems:
            report.error(f"exercise {exercise_id}: unknown problem {exercise_def.problem}")
        if exercise_def.type == "debug" and not exercise_def.misconception:
            report.error(f"exercise {exercise_id}: debug exercises must name the misconception")
    return report


def _short(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _example_tests(problem: LoadedProblem) -> list[ConcreteTest]:
    return [
        ConcreteTest(f"x{index}", list(example.input.values()), example.output)
        for index, example in enumerate(problem.definition.examples, start=1)
    ]


def execute(
    corpus: Corpus, backend: ExecutionBackend | None = None, only: set[str] | None = None
) -> ValidationReport:
    backend = backend or TrustedSubprocessBackend()
    report = ValidationReport()
    for slug, problem in corpus.problems.items():
        if only and slug not in only:
            continue
        definition = problem.definition
        spec = spec_for(problem)
        limits = SandboxLimits(per_test_timeout_s=definition.per_test_timeout_s)
        visible = [*problem.visible_tests, *_example_tests(problem)]
        first = execute_tests(
            backend, spec, definition.reference_solution, visible, problem.hidden_tests, limits
        )
        if first.verdict != "passed":
            failures = [
                f"{test.id}: {test.status} actual={_short(test.actual)} "
                f"expected={_short(test.expected)} {test.error or ''}"
                for test in first.tests
                if test.status != "passed"
            ]
            report.error(
                f"problem {slug}: reference solution {first.verdict}: {first.message} "
                + "; ".join(failures[:4])
            )
            continue
        second = execute_tests(
            backend, spec, definition.reference_solution, visible, problem.hidden_tests, limits
        )
        if [test.actual for test in first.tests] != [test.actual for test in second.tests]:
            report.error(f"problem {slug}: reference output is not deterministic")
        for wrong in definition.wrong_solutions:
            outcome = execute_tests(backend, spec, wrong.code, [], problem.hidden_tests, limits)
            statuses = {test.status for test in outcome.tests}
            caught = {
                "wrong_answer": "wrong_answer" in statuses,
                "timeout": "timeout" in statuses or outcome.verdict == "timeout",
                "error": "error" in statuses or outcome.verdict == "load_error",
            }[wrong.expect]
            if not caught:
                report.error(
                    f"problem {slug}: hidden tests do not catch '{wrong.mistake}' as "
                    f"{wrong.expect} (verdict {outcome.verdict}, statuses {sorted(statuses)})"
                )
    for exercise_id, exercise in corpus.exercises.items():
        exercise_def = exercise.definition
        if exercise_def.type not in ("debug", "code_fragment") or not exercise_def.problem:
            continue
        problem = corpus.problems[exercise_def.problem]
        starter = execute_tests(
            backend,
            spec_for(problem),
            exercise.starter_code or "",
            problem.visible_tests,
            problem.hidden_tests,
            SandboxLimits(per_test_timeout_s=problem.definition.per_test_timeout_s),
        )
        if starter.verdict == "passed":
            report.error(f"exercise {exercise_id}: starter code already passes every test")
    return report


def coverage(corpus: Corpus) -> dict[str, Any]:
    problems = [problem.definition for problem in corpus.problems.values()]
    capability_types = {cap.slug: cap.type for cap in corpus.taxonomy.capabilities}
    covered = Counter(
        capability_types[weight.slug] for problem in problems for weight in problem.capabilities
    )
    exercised = Counter(exercise.definition.type for exercise in corpus.exercises.values())
    by_topic_role: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for problem in problems:
        by_topic_role[problem.topic][problem.role] += 1
    uncovered = sorted(
        cap.slug
        for cap in corpus.taxonomy.capabilities
        if cap.topic != "interview"
        and not any(
            weight.slug == cap.slug for problem in problems for weight in problem.capabilities
        )
        and not any(
            exercise.definition.capability == cap.slug for exercise in corpus.exercises.values()
        )
    )
    groups: dict[str, list[str]] = defaultdict(list)
    for problem in problems:
        groups[problem.transfer_group].append(problem.slug)
    return {
        "problems": len(problems),
        "exercises": len(corpus.exercises),
        "by_topic": dict(Counter(problem.topic for problem in problems)),
        "by_difficulty": dict(Counter(problem.difficulty for problem in problems)),
        "by_status": dict(Counter(problem.status for problem in problems)),
        "by_topic_role": {topic: dict(roles) for topic, roles in by_topic_role.items()},
        "capability_type_weight_links": dict(covered),
        "exercise_types": dict(exercised),
        "transfer_groups": dict(groups),
        "uncovered_capabilities": uncovered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    corpus = load_corpus()
    report = lint(corpus)
    if args.execute and report.ok:
        executed = execute(corpus, only=set(args.only) if args.only else None)
        report.errors.extend(executed.errors)
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")
    if args.report:
        print(json.dumps(coverage(corpus), indent=2, sort_keys=True))
    print(
        f"{len(corpus.problems)} problems, {len(corpus.exercises)} exercises: "
        f"{'ok' if report.ok else f'{len(report.errors)} error(s)'}"
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
