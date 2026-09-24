"""Reps sandbox harness.

Runs inside the isolated execution container (or, for trusted corpus validation only, a
resource-limited subprocess). It never receives expected outputs: it returns the value each
test produced and the worker compares values outside the sandbox.

Protocol: a single JSON document on stdin, a single JSON document on stdout.

Input::

    {"code": str, "entrypoint": str, "kind": "function" | "class",
     "input_adapters": [str | null], "output_adapter": str | null,
     "tests": [{"id": str, "args": list}],
     "per_test_timeout_s": float, "max_stdout_bytes": int, "memory_limit_mb": int}

Learner code executes in a forked child with its own resource limits. The parent reads one
result line per test from a private pipe, enforces per-test deadlines, and is the only process
that writes to the real stdout.
"""

from __future__ import annotations

import io
import json
import os
import resource
import selectors
import signal
import sys
import time
import traceback
from typing import Any

MAX_VALUE_BYTES = 400_000
MAX_ERROR_CHARS = 600
HARD_STDOUT_BYTES = 256_000


class ListNode:
    def __init__(self, val: Any = 0, next: ListNode | None = None) -> None:  # noqa: A002
        self.val = val
        self.next = next

    def __repr__(self) -> str:
        return f"ListNode({self.val})"


class TreeNode:
    def __init__(
        self, val: Any = 0, left: TreeNode | None = None, right: TreeNode | None = None
    ) -> None:
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"TreeNode({self.val})"


class TestTimeout(BaseException):
    pass


class OutputLimitExceeded(BaseException):
    pass


class BoundedWriter(io.TextIOBase):
    def __init__(self, soft_limit: int) -> None:
        self.soft_limit = soft_limit
        self.parts: list[str] = []
        self.size = 0
        self.truncated = False

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self.size += len(text)
        if self.size > HARD_STDOUT_BYTES:
            raise OutputLimitExceeded()
        remaining = self.soft_limit - sum(len(part) for part in self.parts)
        if remaining > 0:
            self.parts.append(text[:remaining])
        if len(text) > remaining:
            self.truncated = True
        return len(text)

    def value(self) -> str:
        return "".join(self.parts)


def build_linked_list(values: list[Any] | None) -> ListNode | None:
    head: ListNode | None = None
    for value in reversed(values or []):
        head = ListNode(value, head)
    return head


def dump_linked_list(node: Any) -> list[Any] | None:
    values: list[Any] = []
    seen = 0
    while node is not None:
        values.append(node.val)
        node = node.next
        seen += 1
        if seen > 100_000:
            raise ValueError("returned list contains a cycle or is too long")
    return values


def build_tree(values: list[Any] | None) -> TreeNode | None:
    if not values or values[0] is None:
        return None
    root = TreeNode(values[0])
    queue = [root]
    index = 1
    head = 0
    while head < len(queue) and index < len(values):
        node = queue[head]
        head += 1
        if index < len(values) and values[index] is not None:
            node.left = TreeNode(values[index])
            queue.append(node.left)
        index += 1
        if index < len(values) and values[index] is not None:
            node.right = TreeNode(values[index])
            queue.append(node.right)
        index += 1
    return root


def dump_tree(root: Any) -> list[Any]:
    if root is None:
        return []
    values: list[Any] = []
    queue = [root]
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        if head > 200_000:
            raise ValueError("returned tree is too large")
        if node is None:
            values.append(None)
            continue
        values.append(node.val)
        queue.append(node.left)
        queue.append(node.right)
    while values and values[-1] is None:
        values.pop()
    return values


INPUT_ADAPTERS = {"linked_list": build_linked_list, "tree": build_tree}
OUTPUT_ADAPTERS = {"linked_list": dump_linked_list, "tree": dump_tree}


def to_jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 50:
        raise ValueError("returned value is nested too deeply")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return repr(value)
        return value
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item, depth + 1) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [to_jsonable(item, depth + 1) for item in value]
        try:
            return sorted(items)
        except TypeError:
            return items
    if isinstance(value, dict):
        return {str(key): to_jsonable(item, depth + 1) for key, item in value.items()}
    return {"__unserializable__": type(value).__name__}


def learner_traceback(exc: BaseException) -> str:
    frames = [
        frame
        for frame in traceback.extract_tb(exc.__traceback__)
        if frame.filename == "solution.py"
    ]
    location = f" (line {frames[-1].lineno})" if frames else ""
    message = f"{type(exc).__name__}{location}: {exc}"
    return message[:MAX_ERROR_CHARS]


def apply_child_limits(memory_limit_mb: int) -> None:
    limit = memory_limit_mb * 1024 * 1024
    for name, value in (
        ("RLIMIT_AS", limit),
        ("RLIMIT_FSIZE", 1024 * 1024),
        ("RLIMIT_NOFILE", 32),
        ("RLIMIT_CORE", 0),
        ("RLIMIT_NPROC", 16),
    ):
        kind = getattr(resource, name, None)
        if kind is None:
            continue
        try:
            resource.setrlimit(kind, (value, value))
        except (ValueError, OSError):
            # macOS rejects some limits for trusted local validation; the container enforces
            # the authoritative limits with cgroups.
            pass


def run_child(job: dict[str, Any], result_fd: int) -> None:
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    os.closerange(3, result_fd)
    os.closerange(result_fd + 1, 1024)
    out = os.fdopen(result_fd, "w", buffering=1)

    def emit(message: dict[str, Any]) -> None:
        encoded = json.dumps(message)
        if len(encoded) > MAX_VALUE_BYTES:
            message = {**message, "value": None, "status": "error",
                       "error": "Returned value is too large to report."}
            encoded = json.dumps(message)
        out.write(encoded + "\n")
        out.flush()

    apply_child_limits(int(job.get("memory_limit_mb", 256)))
    timeout = float(job.get("per_test_timeout_s", 2.0))
    soft_stdout = int(job.get("max_stdout_bytes", 4000))

    def on_alarm(signum: int, frame: Any) -> None:
        raise TestTimeout()

    signal.signal(signal.SIGALRM, on_alarm)
    namespace: dict[str, Any] = {
        "__name__": "solution",
        "ListNode": ListNode,
        "TreeNode": TreeNode,
    }
    try:
        compiled = compile(job["code"], "solution.py", "exec")
    except SyntaxError as exc:
        emit({"type": "load", "status": "syntax_error",
              "error": f"SyntaxError (line {exc.lineno}): {exc.msg}"[:MAX_ERROR_CHARS]})
        return
    load_stdout = BoundedWriter(soft_stdout)
    sys.stdout = load_stdout
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout)
        exec(compiled, namespace)
        signal.setitimer(signal.ITIMER_REAL, 0)
    except TestTimeout:
        emit({"type": "load", "status": "timeout", "error": "Module load exceeded time limit."})
        return
    except BaseException as exc:  # learner code may raise anything
        signal.setitimer(signal.ITIMER_REAL, 0)
        emit({"type": "load", "status": "load_error", "error": learner_traceback(exc)})
        return
    target = namespace.get(job["entrypoint"])
    if target is None:
        emit({"type": "load", "status": "load_error",
              "error": f"Define `{job['entrypoint']}` in your solution."})
        return
    emit({"type": "load", "status": "ok"})

    input_adapters = job.get("input_adapters") or []
    output_adapter = OUTPUT_ADAPTERS.get(job.get("output_adapter") or "")
    for test in job["tests"]:
        writer = BoundedWriter(soft_stdout)
        sys.stdout = writer
        started = time.perf_counter()
        result: dict[str, Any] = {"type": "result", "id": test["id"]}
        try:
            signal.setitimer(signal.ITIMER_REAL, timeout)
            if job.get("kind") == "class":
                value = run_class_test(namespace, job["entrypoint"], test["args"])
            else:
                args = [
                    INPUT_ADAPTERS[input_adapters[index]](arg)
                    if index < len(input_adapters) and input_adapters[index]
                    else arg
                    for index, arg in enumerate(test["args"])
                ]
                value = target(*args)
                if output_adapter is not None:
                    value = output_adapter(value)
            signal.setitimer(signal.ITIMER_REAL, 0)
            result.update(status="ok", value=to_jsonable(value))
        except TestTimeout:
            result.update(status="timeout", error="Test exceeded its time limit.")
        except OutputLimitExceeded:
            signal.setitimer(signal.ITIMER_REAL, 0)
            result.update(status="output_limit", error="Printed output exceeded the limit.")
        except MemoryError:
            signal.setitimer(signal.ITIMER_REAL, 0)
            result.update(status="memory_limit", error="MemoryError: memory limit exceeded.")
        except RecursionError as exc:
            signal.setitimer(signal.ITIMER_REAL, 0)
            result.update(status="error", error=learner_traceback(exc))
        except BaseException as exc:
            signal.setitimer(signal.ITIMER_REAL, 0)
            result.update(status="error", error=learner_traceback(exc))
        sys.stdout = sys.__stdout__
        result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        result["stdout"] = writer.value()
        result["stdout_truncated"] = writer.truncated
        emit(result)


def run_class_test(namespace: dict[str, Any], entrypoint: str, args: list[Any]) -> list[Any]:
    operations, arguments = args
    cls = namespace[entrypoint]
    instance = cls(*arguments[0])
    outputs: list[Any] = [None]
    for operation, operation_args in zip(operations[1:], arguments[1:], strict=True):
        if operation.startswith("_"):
            raise AttributeError("private operations are not callable")
        outputs.append(getattr(instance, operation)(*operation_args))
    return outputs


def supervise(job: dict[str, Any]) -> dict[str, Any]:
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        os.close(read_fd)
        try:
            run_child(job, write_fd)
        finally:
            os._exit(0)
    os.close(write_fd)
    per_test = float(job.get("per_test_timeout_s", 2.0))
    grace = 0.75
    tests: list[dict[str, Any]] = job["tests"]
    results: dict[str, dict[str, Any]] = {}
    load: dict[str, Any] | None = None
    buffer = b""
    selector = selectors.DefaultSelector()
    selector.register(read_fd, selectors.EVENT_READ)
    deadline = time.monotonic() + per_test + grace
    killed_reason: str | None = None
    closed = False
    while not closed:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            killed_reason = "timeout"
            break
        if not selector.select(timeout=remaining):
            continue
        chunk = os.read(read_fd, 65536)
        if not chunk:
            closed = True
        buffer += chunk
        if len(buffer) > MAX_VALUE_BYTES * (len(tests) + 2):
            killed_reason = "output_limit"
            break
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "load":
                load = message
            elif message.get("type") == "result":
                results[str(message["id"])] = message
            deadline = time.monotonic() + per_test + grace
        if load is not None and load.get("status") != "ok":
            break
        if len(results) == len(tests):
            break
    if killed_reason is not None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    _, wait_status = os.waitpid(pid, 0)
    signaled = os.WIFSIGNALED(wait_status)
    selector.close()
    os.close(read_fd)

    if load is None:
        if killed_reason == "timeout":
            return {"status": "timeout", "error": "Solution did not finish loading in time."}
        if signaled and os.WTERMSIG(wait_status) == signal.SIGKILL:
            return {"status": "memory_limit", "error": "The process was killed (memory limit)."}
        return {"status": "crashed", "error": "The solution process exited unexpectedly."}
    if load["status"] != "ok":
        return {"status": load["status"], "error": load.get("error")}

    ordered: list[dict[str, Any]] = []
    missing_status = "not_run"
    for test in tests:
        found = results.get(str(test["id"]))
        if found is not None:
            found.pop("type", None)
            ordered.append(found)
            continue
        if missing_status == "not_run" and killed_reason is not None:
            ordered.append({"id": test["id"], "status": killed_reason,
                            "error": "Test exceeded its time limit."
                            if killed_reason == "timeout" else "Output limit exceeded."})
            missing_status = "not_run"
            killed_reason = None
            continue
        if missing_status == "not_run" and signaled:
            ordered.append({"id": test["id"], "status": "crashed",
                            "error": "The process was killed while running this test."})
            signaled = False
            continue
        ordered.append({"id": test["id"], "status": "not_run",
                        "error": "Not run because an earlier test stopped execution."})
    return {"status": "ok", "results": ordered}


def main() -> None:
    raw = sys.stdin.buffer.read(4_000_000)
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.write(json.dumps({"status": "harness_error", "error": "invalid job"}))
        return
    output = supervise(job)
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
