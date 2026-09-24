"""Harness behavior through the trusted subprocess backend (no Docker required)."""

import sys

import pytest

from app.corpus.loader import ConcreteTest
from app.execution.backends import SandboxLimits, TrustedSubprocessBackend
from app.execution.evaluate import ExecutionSpec, build_payload, execute_tests

BACKEND = TrustedSubprocessBackend()
LIMITS = SandboxLimits(per_test_timeout_s=1.0)
ADD = ExecutionSpec(entrypoint="add", per_test_timeout_s=1.0)
VISIBLE = [ConcreteTest("v1", [1, 2], 3), ConcreteTest("v2", [2, 2], 4)]
HIDDEN = [ConcreteTest("h1", [10, 5], 15)]


def run(code: str, spec: ExecutionSpec = ADD, visible=VISIBLE, hidden=HIDDEN):  # type: ignore[no-untyped-def]
    return execute_tests(BACKEND, spec, code, visible, hidden, LIMITS)


def test_payload_never_contains_expected_values() -> None:
    payload = build_payload(ADD, "x", [*VISIBLE, *HIDDEN], LIMITS)
    assert all(set(test) == {"id", "args"} for test in payload["tests"])
    assert "expected" not in str(payload)


def test_passing_solution() -> None:
    outcome = run("def add(a, b):\n    return a + b\n")
    assert outcome.verdict == "passed"
    assert outcome.hidden_passed == 1


def test_wrong_answer_reports_actual_value() -> None:
    outcome = run("def add(a, b):\n    return a - b\n")
    assert outcome.verdict == "failed"
    assert outcome.tests[0].status == "wrong_answer"
    assert outcome.tests[0].actual == -1


def test_syntax_error_is_normalized() -> None:
    outcome = run("def add(a, b)\n    return a + b\n")
    assert outcome.verdict == "syntax_error"
    assert "line 1" in outcome.message


def test_runtime_exception_reports_learner_line_only() -> None:
    outcome = run("def add(a, b):\n    x = 1\n    return {}[a]\n")
    assert outcome.verdict == "failed"
    error = outcome.tests[0].error or ""
    assert error.startswith("KeyError (line 3)")
    assert "runner.py" not in error and "/opt/" not in error


def test_missing_entrypoint() -> None:
    outcome = run("def other():\n    pass\n")
    assert outcome.verdict == "load_error"
    assert "Define `add`" in outcome.message


def test_module_level_exception() -> None:
    outcome = run("raise RuntimeError('boom')\n")
    assert outcome.verdict == "load_error"


def test_infinite_loop_times_out_per_test() -> None:
    outcome = run("def add(a, b):\n    while True:\n        pass\n")
    assert outcome.verdict == "timeout"
    assert {test.status for test in outcome.tests} <= {"timeout", "not_run"}


def test_swallowed_timeout_is_still_killed() -> None:
    code = (
        "def add(a, b):\n"
        "    while True:\n"
        "        try:\n"
        "            while True:\n"
        "                pass\n"
        "        except BaseException:\n"
        "            pass\n"
    )
    outcome = run(code)
    assert outcome.verdict == "timeout"
    assert outcome.tests[-1].status == "not_run"


def test_output_is_captured_and_truncated() -> None:
    outcome = run("def add(a, b):\n    print('x' * 10000)\n    return a + b\n")
    assert outcome.verdict == "passed"
    assert len(outcome.tests[0].stdout or "") == LIMITS.max_stdout_bytes


def test_runaway_output_hits_limit() -> None:
    outcome = run("def add(a, b):\n    while True:\n        print('spam' * 1000)\n")
    assert outcome.tests[0].status == "output_limit"


def test_writing_directly_to_stdout_cannot_forge_results() -> None:
    code = (
        "import os\n"
        "def add(a, b):\n"
        '    os.write(1, b\'{"status": "ok", "results": []}\')\n'
        "    return 0\n"
    )
    outcome = run(code)
    assert outcome.verdict == "failed"


def test_unserializable_return_value_fails_cleanly() -> None:
    outcome = run("def add(a, b):\n    return object()\n")
    assert outcome.tests[0].status == "wrong_answer"


def test_linked_list_and_tree_adapters() -> None:
    reverse = ExecutionSpec(
        entrypoint="rev", input_adapters=("linked_list",), output_adapter="linked_list"
    )
    code = (
        "def rev(head):\n    prev = None\n    while head:\n"
        "        head.next, prev, head = prev, head, head.next\n    return prev\n"
    )
    outcome = run(code, reverse, [ConcreteTest("v1", [[1, 2, 3]], [3, 2, 1])], [])
    assert outcome.verdict == "passed"
    mirror = ExecutionSpec(entrypoint="mirror", input_adapters=("tree",), output_adapter="tree")
    code = (
        "def mirror(root):\n    if root:\n"
        "        root.left, root.right = mirror(root.right), mirror(root.left)\n"
        "    return root\n"
    )
    outcome = run(code, mirror, [ConcreteTest("v1", [[1, 2, None, 3]], [1, None, 2, None, 3])], [])
    assert outcome.verdict == "passed"


def test_class_design_operations() -> None:
    spec = ExecutionSpec(entrypoint="Counter", kind="class")
    code = (
        "class Counter:\n    def __init__(self):\n        self.n = 0\n"
        "    def inc(self):\n        self.n += 1\n    def get(self):\n        return self.n\n"
    )
    test = ConcreteTest(
        "v1", [["Counter", "inc", "inc", "get"], [[], [], [], []]], [None] * 3 + [2]
    )
    assert run(code, spec, [test], []).verdict == "passed"
    private = ConcreteTest("v2", [["Counter", "__init__"], [[], []]], [None, None])
    assert run(code, spec, [private], []).tests[0].status == "error"


def test_source_size_limit() -> None:
    outcome = run("#" * 60_000)
    assert outcome.verdict == "load_error"


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is not enforced on macOS")
def test_memory_bomb_is_contained() -> None:
    outcome = run("def add(a, b):\n    return len(bytearray(2 * 1024 ** 3))\n")
    assert outcome.tests[0].status in ("memory_limit", "error", "crashed")
