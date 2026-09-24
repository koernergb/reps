"""Execution job lifecycle: submit, claim, run, and publish safe results.

State machine: queued -> running -> completed | failed; queued -> cancelled | expired.
A job's verdict is written once; retries of the same idempotency key return the same job.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.corpus.loader import ConcreteTest, Corpus, get_corpus
from app.corpus.validate import spec_for
from app.execution.backends import (
    DockerSandboxBackend,
    ExecutionBackend,
    SandboxLimits,
    SandboxUnavailable,
    TrustedSubprocessBackend,
)
from app.execution.evaluate import ExecutionOutcome, execute_tests
from app.models import ExecutionJob, Problem

logger = structlog.get_logger()

MAX_SOURCE_CHARS = 50_000
ACTIVE_STATUSES = ("queued", "running")


class ExecutionRejected(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class RateLimiter:
    """In-memory sliding window. Adequate for the single-process local API."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] > window_s:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = RateLimiter()

# Hooks run in the worker after a job reaches a terminal state (e.g. interview events).
CompletionHook = Callable[[Session, ExecutionJob], None]
completion_hooks: list[CompletionHook] = []


def build_backend(settings: Settings | None = None) -> ExecutionBackend:
    settings = settings or get_settings()
    if settings.execution_backend == "trusted-subprocess":
        return TrustedSubprocessBackend()
    return DockerSandboxBackend(settings.sandbox_image)


def limits_for(settings: Settings, per_test_timeout_s: float) -> SandboxLimits:
    return SandboxLimits(
        memory_mb=settings.sandbox_memory_mb,
        cpus=settings.sandbox_cpus,
        pids=settings.sandbox_pids,
        per_test_timeout_s=per_test_timeout_s,
    )


def submit_job(
    session: Session,
    *,
    user_id: str,
    problem_slug: str,
    code: str,
    kind: str,
    idempotency_key: str,
    session_id: str | None = None,
    review_attempt_id: str | None = None,
    settings: Settings | None = None,
) -> tuple[ExecutionJob, bool]:
    """Create (or return the existing) job. Returns (job, created)."""
    settings = settings or get_settings()
    existing = session.scalar(
        select(ExecutionJob).where(
            ExecutionJob.user_id == user_id, ExecutionJob.idempotency_key == idempotency_key
        )
    )
    code_sha = hashlib.sha256(code.encode()).hexdigest()
    if existing is not None:
        if existing.code_sha256 != code_sha or existing.kind != kind:
            raise ExecutionRejected(
                "idempotency_conflict",
                "This request key was already used for different code.",
                409,
            )
        return existing, False
    if not settings.execution_enabled:
        raise ExecutionRejected(
            "execution_disabled", "Code execution is temporarily disabled.", 503
        )
    if kind not in ("run", "submit"):
        raise ExecutionRejected("invalid_kind", "Kind must be run or submit.", 422)
    if len(code) > MAX_SOURCE_CHARS:
        raise ExecutionRejected("source_too_large", "Source code exceeds 50,000 characters.", 413)
    problem = session.scalar(
        select(Problem).where(Problem.slug == problem_slug, Problem.status != "retired")
    )
    if problem is None:
        raise ExecutionRejected("problem_not_found", "Problem not found.", 404)
    queued = session.scalar(
        select(func.count())
        .select_from(ExecutionJob)
        .where(ExecutionJob.user_id == user_id, ExecutionJob.status.in_(ACTIVE_STATUSES))
    )
    if (queued or 0) >= settings.execution_max_queued_per_user:
        raise ExecutionRejected(
            "queue_full", "Too many executions are in progress. Wait for one to finish.", 429
        )
    if not rate_limiter.allow(f"exec:{user_id}", settings.execution_rate_per_minute):
        raise ExecutionRejected(
            "rate_limited", "Too many executions this minute. Try again shortly.", 429
        )
    now = utcnow()
    job = ExecutionJob(
        user_id=user_id,
        problem_id=problem.id,
        session_id=session_id,
        review_attempt_id=review_attempt_id,
        kind=kind,
        status="queued",
        idempotency_key=idempotency_key,
        code=code,
        code_sha256=code_sha,
        content_version=problem.content_version,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.execution_job_ttl_s),
    )
    session.add(job)
    session.commit()
    logger.info("execution_job_queued", job_id=job.id, kind=kind, problem=problem_slug)
    return job, True


def cancel_job(session: Session, job: ExecutionJob) -> bool:
    result = session.execute(
        update(ExecutionJob)
        .where(ExecutionJob.id == job.id, ExecutionJob.status == "queued")
        .values(status="cancelled", finished_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    session.commit()
    session.refresh(job)
    return bool(result.rowcount)  # type: ignore[attr-defined]


def claim_next_job(session: Session) -> ExecutionJob | None:
    """Atomically move the oldest queued job to running. Safe across concurrent workers."""
    now = utcnow()
    session.execute(
        update(ExecutionJob)
        .where(ExecutionJob.status == "queued", ExecutionJob.expires_at < now)
        .values(status="expired", finished_at=now)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    candidates = session.scalars(
        select(ExecutionJob.id)
        .where(ExecutionJob.status == "queued")
        .order_by(ExecutionJob.created_at)
        .limit(5)
    ).all()
    for job_id in candidates:
        claimed = session.execute(
            update(ExecutionJob)
            .where(ExecutionJob.id == job_id, ExecutionJob.status == "queued")
            .values(status="running", started_at=now, attempts=ExecutionJob.attempts + 1)
            .execution_options(synchronize_session=False)
        )
        session.commit()
        if claimed.rowcount:  # type: ignore[attr-defined]
            job = session.get(ExecutionJob, job_id)
            if job is not None:
                session.refresh(job)
            return job
    return None


def public_result(job_kind: str, outcome: ExecutionOutcome) -> dict[str, Any]:
    visible = [
        {
            "id": test.id,
            "args": test.args,
            "expected": test.expected,
            "actual": test.actual,
            "status": test.status,
            "error": test.error,
            "stdout": test.stdout,
            "duration_ms": test.duration_ms,
        }
        for test in outcome.tests
        if test.visible
    ]
    result: dict[str, Any] = {
        "verdict": outcome.verdict,
        "message": outcome.message,
        "visible": visible,
        "visible_passed": outcome.visible_passed,
        "visible_total": outcome.visible_total,
    }
    if job_kind == "submit":
        result["hidden"] = {
            "passed": outcome.hidden_passed,
            "total": outcome.hidden_total,
            "failures": outcome.hidden_failure_categories(),
        }
        if outcome.verdict not in ("passed", "failed", "timeout", "memory_limit"):
            # Load failures (syntax/import errors) are safe to show in full.
            result["hidden"]["failures"] = {}
    return result


def run_job(
    session: Session,
    job: ExecutionJob,
    backend: ExecutionBackend,
    corpus: Corpus | None = None,
    settings: Settings | None = None,
) -> ExecutionJob:
    settings = settings or get_settings()
    corpus = corpus or get_corpus()
    problem = session.get(Problem, job.problem_id)
    assert problem is not None
    loaded = corpus.problem(problem.slug)
    spec = spec_for(loaded)
    visible: list[ConcreteTest] = list(loaded.visible_tests)
    hidden = list(loaded.hidden_tests) if job.kind == "submit" else []
    started = time.perf_counter()
    try:
        if backend.trusted_only and settings.environment != "test":
            raise SandboxUnavailable("trusted backend refused for learner code")
        outcome = execute_tests(
            backend,
            spec,
            job.code,
            visible,
            hidden,
            limits_for(settings, loaded.definition.per_test_timeout_s),
        )
    except SandboxUnavailable as exc:
        job.status = "failed"
        job.verdict = None
        job.result_public = {
            "verdict": None,
            "message": "The code sandbox is unavailable, so no result was recorded. "
            "Check that Docker is running and the sandbox image is built "
            "(make sandbox-build), then try again.",
        }
        job.result_private = {"error": str(exc)}
        job.finished_at = utcnow()
        job.backend = backend.name
        session.commit()
        logger.warning("execution_job_failed", job_id=job.id, reason=type(exc).__name__)
        _run_hooks(session, job)
        return job
    job.status = "completed"
    job.verdict = outcome.verdict
    job.result_public = public_result(job.kind, outcome)
    job.result_private = outcome.to_private_dict()
    job.finished_at = utcnow()
    job.backend = backend.name
    session.commit()
    logger.info(
        "execution_job_completed",
        job_id=job.id,
        kind=job.kind,
        verdict=outcome.verdict,
        duration_ms=round((time.perf_counter() - started) * 1000),
        backend=backend.name,
    )
    _run_hooks(session, job)
    return job


def _run_hooks(session: Session, job: ExecutionJob) -> None:
    for hook in completion_hooks:
        try:
            hook(session, job)
        except Exception:
            session.rollback()
            logger.exception("execution_hook_failed", job_id=job.id, hook=hook.__name__)


def process_available_jobs(
    session_factory: sessionmaker[Session],
    backend: ExecutionBackend,
    limit: int = 50,
) -> int:
    processed = 0
    while processed < limit:
        with session_factory() as session:
            job = claim_next_job(session)
            if job is None:
                return processed
            run_job(session, job, backend)
            processed += 1
    return processed


def recover_stale_running_jobs(session: Session, older_than_s: float = 300) -> int:
    cutoff = utcnow() - timedelta(seconds=older_than_s)
    result = session.execute(
        update(ExecutionJob)
        .where(ExecutionJob.status == "running", ExecutionJob.started_at < cutoff)
        .values(
            status="failed",
            finished_at=utcnow(),
            result_public={
                "verdict": None,
                "message": "Execution was interrupted. Please run it again.",
            },
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return int(result.rowcount)  # type: ignore[attr-defined]
