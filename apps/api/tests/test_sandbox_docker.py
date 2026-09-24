"""Adversarial suite against the real Docker sandbox.

Skipped automatically when Docker or the sandbox image is unavailable. Build the image with
`make sandbox-build`. Human Gate 3 requires re-running this suite (plus manual attempts) on
the actual target topology.
"""

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.corpus.loader import ConcreteTest
from app.execution.backends import DockerSandboxBackend, SandboxLimits
from app.execution.evaluate import ExecutionOutcome, ExecutionSpec, execute_tests

IMAGE = os.environ.get("SANDBOX_IMAGE", "reps-sandbox:dev")


def image_available() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    result = subprocess.run(
        [docker, "image", "inspect", IMAGE], capture_output=True, timeout=10, check=False
    )
    return result.returncode == 0


pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(not image_available(), reason="Docker sandbox image not available"),
]

BACKEND = DockerSandboxBackend(IMAGE)
LIMITS = SandboxLimits(memory_mb=256, per_test_timeout_s=2.0)
SPEC = ExecutionSpec(entrypoint="probe", per_test_timeout_s=2.0)
SECRET_HIDDEN_EXPECTED = "hidden-expected-7f3a"


def probe(body: str, expected: object = True) -> ExecutionOutcome:
    code = "def probe():\n" + "\n".join(f"    {line}" for line in body.strip().splitlines())
    return execute_tests(BACKEND, SPEC, code, [ConcreteTest("v1", [], expected)], [], LIMITS)


def value(outcome: ExecutionOutcome) -> object:
    return outcome.tests[0].actual if outcome.tests else outcome.message


def test_correct_code_passes() -> None:
    assert probe("return True").verdict == "passed"


def test_network_is_unavailable() -> None:
    outcome = probe(
        """
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=1)
    return "connected"
except OSError as exc:
    return type(exc).__name__
"""
    )
    assert value(outcome) != "connected"


def test_dns_is_unavailable() -> None:
    outcome = probe(
        """
import socket
try:
    socket.gethostbyname("example.com")
    return "resolved"
except OSError:
    return "blocked"
"""
    )
    assert value(outcome) == "blocked"


def test_root_filesystem_is_read_only_and_tmp_is_bounded() -> None:
    outcome = probe(
        """
results = []
for path in ("/etc/reps-owned", "/opt/reps/runner.py", "/usr/local/evil"):
    try:
        open(path, "w").write("x")
        results.append("wrote " + path)
    except OSError:
        results.append("denied")
try:
    with open("/tmp/big", "wb") as handle:
        handle.write(b"x" * (64 * 1024 * 1024))
    results.append("tmp unbounded")
except OSError:
    results.append("tmp bounded")
return results
"""
    )
    assert value(outcome) == ["denied", "denied", "denied", "tmp bounded"]


def test_runs_unprivileged_without_capabilities() -> None:
    outcome = probe(
        """
import os
status = open("/proc/self/status").read()
cap = [line for line in status.splitlines() if line.startswith("CapEff")][0]
return [os.getuid(), cap.split()[1]]
"""
    )
    assert value(outcome) == [65534, "0000000000000000"]


def test_environment_and_host_paths_are_not_exposed() -> None:
    os.environ["REPS_TEST_SECRET"] = "should-not-leak"
    outcome = probe(
        """
import os
visible = dict(os.environ)
paths = [p for p in ("/Users", "/home", "/root/.ssh", "/var/run/docker.sock", "/workspace")
         if os.path.exists(p) and os.listdir(p) if os.path.isdir(p)]
return [sorted(k for k in visible if "SECRET" in k or "KEY" in k or "DATABASE" in k), paths]
"""
    )
    assert value(outcome) == [[], []]


def test_parent_harness_memory_and_fds_are_protected() -> None:
    outcome = probe(
        """
import os
results = []
ppid = os.getppid()
for path in (f"/proc/{ppid}/fd/1", f"/proc/{ppid}/mem", f"/proc/{ppid}/environ"):
    try:
        with open(path, "rb" if "mem" in path or "environ" in path else "w") as handle:
            results.append("opened")
    except OSError:
        results.append("denied")
return results
"""
    )
    assert value(outcome) == ["denied", "denied", "denied"]


def test_fork_bomb_is_contained() -> None:
    started = time.monotonic()
    outcome = probe(
        """
import os
count = 0
try:
    while True:
        if os.fork() == 0:
            while True:
                pass
        count += 1
except OSError:
    return "limited"
"""
    )
    assert value(outcome) == "limited" or outcome.verdict in ("timeout", "crashed")
    assert time.monotonic() - started < 30


def test_memory_bomb_is_contained() -> None:
    outcome = probe("return len(bytearray(1024 ** 3))")
    assert outcome.verdict != "passed"
    assert outcome.tests[0].status in ("memory_limit", "error", "crashed") or (
        outcome.verdict == "memory_limit"
    )


def test_cpu_spin_times_out() -> None:
    outcome = probe("while True:\n    pass")
    assert outcome.verdict == "timeout"


def test_huge_output_is_bounded() -> None:
    outcome = probe("while True:\n    print('x' * 100000)")
    assert outcome.tests[0].status == "output_limit"


def test_hidden_expected_values_never_enter_the_sandbox() -> None:
    sent: list[bytes] = []

    class RecordingBackend(DockerSandboxBackend):
        def execute(self, payload: dict[str, object], limits: SandboxLimits) -> dict[str, object]:
            sent.append(json.dumps(payload).encode())
            return super().execute(payload, limits)

    outcome = execute_tests(
        RecordingBackend(IMAGE),
        ExecutionSpec(entrypoint="probe"),
        "def probe():\n    return 'guess'\n",
        [],
        [ConcreteTest("h1", [], SECRET_HIDDEN_EXPECTED)],
        LIMITS,
    )
    assert outcome.tests[0].status == "wrong_answer"
    assert sent and all(SECRET_HIDDEN_EXPECTED.encode() not in payload for payload in sent)
    assert all(b'"expected"' not in payload for payload in sent)


def test_concurrent_jobs_are_isolated() -> None:
    writer = "open('/tmp/shared', 'w').write('from-a')\nreturn True"
    reader = "import os\nreturn os.path.exists('/tmp/shared')"

    def run(body: str, expected: object) -> ExecutionOutcome:
        return probe(body, expected)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(run, writer, True),
            *(pool.submit(run, reader, False) for _ in range(3)),
        ]
        outcomes = [future.result() for future in futures]
    assert outcomes[0].verdict == "passed"
    assert all(outcome.tests[0].actual is False for outcome in outcomes[1:])
