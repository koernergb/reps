"""Execution backends.

`DockerSandboxBackend` is the only backend permitted for learner code. It starts an ephemeral
container per job with no network, a read-only root filesystem, a small tmpfs, an unprivileged
user, all capabilities dropped, `no-new-privileges`, and cgroup CPU/memory/PID limits.

`TrustedSubprocessBackend` exists solely to validate trusted, reviewed corpus content (reference
and known-wrong solutions) and to unit-test the harness. It applies rlimits but is not an
isolation boundary; configuration refuses to use it for learner jobs outside tests.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

HARNESS_PATH = Path(__file__).resolve().parents[4] / "infra" / "sandbox" / "harness" / "runner.py"
MAX_HARNESS_OUTPUT_BYTES = 4_000_000
STARTUP_ALLOWANCE_S = 8.0


class SandboxUnavailable(RuntimeError):
    """The sandbox could not run the job; no verdict about the learner's code exists."""


@dataclass(frozen=True)
class SandboxLimits:
    memory_mb: int = 256
    cpus: float = 1.0
    pids: int = 64
    tmpfs_mb: int = 16
    per_test_timeout_s: float = 2.0
    max_stdout_bytes: int = 4000


class ExecutionBackend(Protocol):
    name: str
    trusted_only: bool

    def execute(self, payload: dict[str, Any], limits: SandboxLimits) -> dict[str, Any]: ...


def wall_timeout(payload: dict[str, Any], limits: SandboxLimits) -> float:
    tests = len(payload.get("tests", []))
    per_test = float(payload.get("per_test_timeout_s", limits.per_test_timeout_s))
    return STARTUP_ALLOWANCE_S + per_test * (tests + 1) + 1.0 * (tests + 1)


def _bounded_communicate(
    process: subprocess.Popen[bytes], data: bytes, timeout: float
) -> tuple[bytes, bool]:
    """Write stdin and read at most MAX_HARNESS_OUTPUT_BYTES of stdout."""
    chunks: list[bytes] = []
    overflow = threading.Event()

    def reader() -> None:
        assert process.stdout is not None
        size = 0
        while True:
            chunk = process.stdout.read(65536)
            if not chunk:
                return
            size += len(chunk)
            if size > MAX_HARNESS_OUTPUT_BYTES:
                overflow.set()
                process.kill()
                return
            chunks.append(chunk)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    assert process.stdin is not None
    try:
        process.stdin.write(data)
        process.stdin.close()
    except BrokenPipeError:
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        thread.join(timeout=2)
        raise
    thread.join(timeout=2)
    return b"".join(chunks), overflow.is_set()


def _parse_output(raw: bytes, returncode: int) -> dict[str, Any]:
    if returncode in (137, -9) and not raw:
        return {"status": "memory_limit", "error": "The sandbox was killed (memory limit)."}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SandboxUnavailable("sandbox returned an unreadable result") from exc
    if not isinstance(parsed, dict) or "status" not in parsed:
        raise SandboxUnavailable("sandbox returned an unexpected result")
    if parsed["status"] == "harness_error":
        raise SandboxUnavailable("sandbox rejected the job")
    return parsed


class DockerSandboxBackend:
    name = "docker"
    trusted_only = False

    def __init__(self, image: str, docker_binary: str | None = None) -> None:
        self.image = image
        self.docker = docker_binary or shutil.which("docker") or "docker"

    def command(self, limits: SandboxLimits) -> list[str]:
        return [
            self.docker,
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={limits.tmpfs_mb}m,mode=1777",
            "--memory",
            f"{limits.memory_mb}m",
            "--memory-swap",
            f"{limits.memory_mb}m",
            "--cpus",
            str(limits.cpus),
            "--pids-limit",
            str(limits.pids),
            "--ulimit",
            "nofile=64:64",
            "--ulimit",
            "fsize=1048576:1048576",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--ipc",
            "none",
            "--log-driver",
            "none",
            "--env",
            "PYTHONHASHSEED=0",
            self.image,
        ]

    def execute(self, payload: dict[str, Any], limits: SandboxLimits) -> dict[str, Any]:
        payload = {**payload, "memory_limit_mb": max(32, limits.memory_mb - 48)}
        try:
            process = subprocess.Popen(
                self.command(limits),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SandboxUnavailable("docker is not available") from exc
        try:
            raw, overflow = _bounded_communicate(
                process, json.dumps(payload).encode(), wall_timeout(payload, limits)
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Execution exceeded the overall time limit."}
        if overflow:
            return {"status": "output_limit", "error": "Execution produced too much output."}
        if process.returncode == 125:
            raise SandboxUnavailable("docker could not start the sandbox container")
        return _parse_output(raw, process.returncode)


class TrustedSubprocessBackend:
    """Runs the harness in a local subprocess. Trusted corpus content and tests only."""

    name = "trusted-subprocess"
    trusted_only = True

    def execute(self, payload: dict[str, Any], limits: SandboxLimits) -> dict[str, Any]:
        payload = {**payload, "memory_limit_mb": limits.memory_mb}
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(HARNESS_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PYTHONHASHSEED": "0", "PATH": "/usr/bin:/bin"},
            cwd="/tmp",
        )
        try:
            raw, overflow = _bounded_communicate(
                process, json.dumps(payload).encode(), wall_timeout(payload, limits)
            )
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": "Execution exceeded the overall time limit."}
        if overflow:
            return {"status": "output_limit", "error": "Execution produced too much output."}
        return _parse_output(raw, process.returncode)
