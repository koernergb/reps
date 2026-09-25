"""Build harness payloads and turn raw harness output into normalized verdicts.

Expected values never enter the sandbox: the harness returns actual values and this module
compares them with the (possibly hidden) expected values on the trusted side.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.corpus.loader import ConcreteTest
from app.execution.backends import ExecutionBackend, SandboxLimits
from app.execution.comparison import values_match

TestStatus = Literal[
    "passed",
    "wrong_answer",
    "error",
    "timeout",
    "memory_limit",
    "output_limit",
    "crashed",
    "not_run",
]
Verdict = Literal[
    "passed",
    "failed",
    "syntax_error",
    "load_error",
    "timeout",
    "memory_limit",
    "output_limit",
    "crashed",
]
MAX_SOURCE_BYTES = 50_000


@dataclass(frozen=True)
class ExecutionSpec:
    entrypoint: str
    kind: str = "function"
    input_adapters: tuple[str | None, ...] = ()
    output_adapter: str | None = None
    comparison: str = "exact"
    per_test_timeout_s: float = 2.0


@dataclass
class TestResult:
    id: str
    visible: bool
    status: TestStatus
    args: list[Any] | None = None
    expected: Any = None
    actual: Any = None
    error: str | None = None
    stdout: str | None = None
    duration_ms: float | None = None


@dataclass
class ExecutionOutcome:
    verdict: Verdict
    message: str
    tests: list[TestResult] = field(default_factory=list)

    @property
    def visible_passed(self) -> int:
        return sum(1 for test in self.tests if test.visible and test.status == "passed")

    @property
    def visible_total(self) -> int:
        return sum(1 for test in self.tests if test.visible)

    @property
    def hidden_passed(self) -> int:
        return sum(1 for test in self.tests if not test.visible and test.status == "passed")

    @property
    def hidden_total(self) -> int:
        return sum(1 for test in self.tests if not test.visible)

    def hidden_failure_categories(self) -> dict[str, int]:
        return dict(
            Counter(
                test.status for test in self.tests if not test.visible and test.status != "passed"
            )
        )

    def to_private_dict(self) -> dict[str, Any]:
        """Full detail for trusted server-side storage only."""
        return {
            "verdict": self.verdict,
            "message": self.message,
            "tests": [asdict(test) for test in self.tests],
        }


def build_payload(
    spec: ExecutionSpec, code: str, tests: list[ConcreteTest], limits: SandboxLimits
) -> dict[str, Any]:
    return {
        "code": code,
        "entrypoint": spec.entrypoint,
        "kind": spec.kind,
        "input_adapters": list(spec.input_adapters),
        "output_adapter": spec.output_adapter,
        "tests": [{"id": test.id, "args": test.args} for test in tests],
        "per_test_timeout_s": min(spec.per_test_timeout_s, 5.0),
        "max_stdout_bytes": limits.max_stdout_bytes,
    }


LOAD_FAILURES: dict[str, tuple[Verdict, str]] = {
    "syntax_error": ("syntax_error", "Your code has a syntax error."),
    "load_error": ("load_error", "Your code raised an error before any test ran."),
    "timeout": ("timeout", "Execution exceeded the time limit."),
    "memory_limit": ("memory_limit", "Execution exceeded the memory limit."),
    "output_limit": ("output_limit", "Execution produced too much output."),
    "crashed": ("crashed", "The solution process exited unexpectedly."),
}


def execute_tests(
    backend: ExecutionBackend,
    spec: ExecutionSpec,
    code: str,
    visible: list[ConcreteTest],
    hidden: list[ConcreteTest],
    limits: SandboxLimits,
) -> ExecutionOutcome:
    if len(code.encode()) > MAX_SOURCE_BYTES:
        return ExecutionOutcome("load_error", "Source code exceeds the 50 KB limit.")
    tests = [*visible, *hidden]
    raw = backend.execute(build_payload(spec, code, tests, limits), limits)
    status = raw.get("status")
    if status != "ok":
        verdict, message = LOAD_FAILURES.get(
            str(status), ("crashed", "The solution process exited unexpectedly.")
        )
        detail = raw.get("error")
        return ExecutionOutcome(verdict, f"{message} {detail}" if detail else message)
    visible_ids = {test.id for test in visible}
    by_id = {test.id: test for test in tests}
    results: list[TestResult] = []
    for item in raw.get("results", []):
        test = by_id.get(str(item.get("id")))
        if test is None:
            continue
        is_visible = test.id in visible_ids
        harness_status = item.get("status")
        if harness_status == "ok":
            passed = values_match(item.get("value"), test.expected, spec.comparison)
            result_status: TestStatus = "passed" if passed else "wrong_answer"
        elif harness_status in (
            "error",
            "timeout",
            "memory_limit",
            "output_limit",
            "crashed",
            "not_run",
        ):
            result_status = harness_status
        else:
            result_status = "crashed"
        results.append(
            TestResult(
                id=test.id,
                visible=is_visible,
                status=result_status,
                args=test.args,
                expected=test.expected,
                actual=item.get("value"),
                error=item.get("error"),
                stdout=item.get("stdout"),
                duration_ms=item.get("duration_ms"),
            )
        )
    if len(results) != len(tests):
        return ExecutionOutcome("crashed", "The sandbox returned incomplete results.")
    failed = [result for result in results if result.status != "passed"]
    if not failed:
        return ExecutionOutcome("passed", "All tests passed.", results)
    statuses = {result.status for result in failed}
    if statuses <= {"timeout", "not_run"} and "timeout" in statuses:
        return ExecutionOutcome("timeout", "At least one test exceeded the time limit.", results)
    if "memory_limit" in statuses:
        return ExecutionOutcome(
            "memory_limit", "At least one test exceeded the memory limit.", results
        )
    return ExecutionOutcome(
        "failed", f"{len(results) - len(failed)} of {len(results)} tests passed.", results
    )
