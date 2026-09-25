"""Operational metrics and SLO evaluation (local, content-free).

Request metrics are kept in memory (rolling window) by middleware; execution, LLM, evaluation,
scheduler, and drill metrics are derived from the database. Nothing here contains learner
content. SLO targets are documented in docs/operations.md.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from statistics import quantiles
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DrillSession,
    ExecutionJob,
    InterviewEvaluation,
    LLMCall,
    ReviewTask,
)

WINDOW_S = 3600
SLO_TARGETS: dict[str, dict[str, float]] = {
    "session_start": {"p95_ms": 1500, "error_rate": 0.01},
    "interview_response": {"p95_ms": 8000, "error_rate": 0.02},
    "code_execution": {"p95_ms": 10000, "failure_rate": 0.02},
    "evaluation_availability": {"degraded_rate": 0.10, "failure_rate": 0.01},
    "queue_generation": {"p95_ms": 1500, "error_rate": 0.01},
}
ROUTE_SLOS = {
    ("POST", "/v1/interviews"): "session_start",
    ("GET", "/v1/interviews/{session_id}"): "session_start",
    ("POST", "/v1/interviews/{session_id}/messages"): "interview_response",
    ("GET", "/v1/reviews/queue"): "queue_generation",
    ("POST", "/v1/drills"): "queue_generation",
}


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples: dict[tuple[str, str], deque[tuple[float, float, int]]] = defaultdict(deque)

    def record(self, method: str, route: str, duration_ms: float, status: int) -> None:
        now = time.time()
        with self._lock:
            samples = self._samples[(method, route)]
            samples.append((now, duration_ms, status))
            while samples and now - samples[0][0] > WINDOW_S:
                samples.popleft()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        result: dict[str, dict[str, Any]] = {}
        with self._lock:
            for (method, route), samples in self._samples.items():
                recent = [sample for sample in samples if now - sample[0] <= WINDOW_S]
                if not recent:
                    continue
                durations = sorted(sample[1] for sample in recent)
                errors = sum(1 for sample in recent if sample[2] >= 500)
                result[f"{method} {route}"] = {
                    "count": len(recent),
                    "error_rate": round(errors / len(recent), 4),
                    "p50_ms": round(percentile(durations, 50), 1),
                    "p95_ms": round(percentile(durations, 95), 1),
                }
        return result

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()


request_metrics = RequestMetrics()


def percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[pct - 1]


def _since(hours: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def execution_metrics(db: Session, hours: int = 24) -> dict[str, Any]:
    jobs = db.execute(
        select(
            ExecutionJob.status,
            ExecutionJob.verdict,
            ExecutionJob.started_at,
            ExecutionJob.finished_at,
        ).where(ExecutionJob.created_at >= _since(hours))
    ).all()
    durations = sorted(
        (finished - started).total_seconds() * 1000
        for _, _, started, finished in jobs
        if started is not None and finished is not None
    )
    by_status: dict[str, int] = defaultdict(int)
    by_verdict: dict[str, int] = defaultdict(int)
    for status, verdict, _, _ in jobs:
        by_status[status] += 1
        if verdict:
            by_verdict[verdict] += 1
    finished = sum(
        count for status, count in by_status.items() if status in ("completed", "failed")
    )
    return {
        "jobs": len(jobs),
        "by_status": dict(by_status),
        "by_verdict": dict(by_verdict),
        "queued_now": int(
            db.scalar(
                select(func.count())
                .select_from(ExecutionJob)
                .where(ExecutionJob.status == "queued")
            )
            or 0
        ),
        "p95_ms": round(percentile(durations, 95), 1),
        "infrastructure_failure_rate": round(by_status.get("failed", 0) / finished, 4)
        if finished
        else 0.0,
    }


def llm_metrics(db: Session, hours: int = 24) -> dict[str, Any]:
    rows = db.execute(
        select(
            LLMCall.task,
            LLMCall.status,
            LLMCall.latency_ms,
            LLMCall.input_tokens,
            LLMCall.output_tokens,
            LLMCall.error_code,
        ).where(LLMCall.created_at >= _since(hours))
    ).all()
    tasks: dict[str, dict[str, Any]] = {}
    for task, status, latency, input_tokens, output_tokens, error in rows:
        entry = tasks.setdefault(
            task,
            {
                "calls": 0,
                "errors": 0,
                "latencies": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "error_codes": defaultdict(int),
            },
        )
        entry["calls"] += 1
        entry["latencies"].append(latency)
        entry["input_tokens"] += input_tokens
        entry["output_tokens"] += output_tokens
        if status != "ok":
            entry["errors"] += 1
            entry["error_codes"][error or "unknown"] += 1
    return {
        task: {
            "calls": entry["calls"],
            "error_rate": round(entry["errors"] / entry["calls"], 4),
            "p95_ms": round(percentile(sorted(entry["latencies"]), 95), 1),
            "input_tokens": entry["input_tokens"],
            "output_tokens": entry["output_tokens"],
            "error_codes": dict(entry["error_codes"]),
        }
        for task, entry in tasks.items()
    }


def evaluation_metrics(db: Session, hours: int = 24) -> dict[str, Any]:
    rows = db.execute(
        select(
            InterviewEvaluation.status,
            InterviewEvaluation.latency_ms,
            InterviewEvaluation.validation,
        ).where(InterviewEvaluation.created_at >= _since(hours))
    ).all()
    total = len(rows)
    degraded = sum(1 for status, _, _ in rows if status == "degraded")
    failed = sum(1 for status, _, _ in rows if status == "failed")
    dropped = sum(int((validation or {}).get("dropped", 0)) for _, _, validation in rows)
    return {
        "evaluations": total,
        "degraded_rate": round(degraded / total, 4) if total else 0.0,
        "failure_rate": round(failed / total, 4) if total else 0.0,
        "unsupported_claims_dropped": dropped,
        "p95_ms": round(percentile(sorted(latency for _, latency, _ in rows), 95), 1),
    }


def scheduling_metrics(db: Session) -> dict[str, Any]:
    rows = db.execute(select(ReviewTask.status, func.count()).group_by(ReviewTask.status)).all()
    drills = db.execute(
        select(DrillSession.status, func.count()).group_by(DrillSession.status)
    ).all()
    return {
        "tasks_by_status": {status: count for status, count in rows},
        "drills_by_status": {status: count for status, count in drills},
    }


def slo_report(
    snapshot: dict[str, dict[str, Any]], execution: dict[str, Any], evaluation: dict[str, Any]
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for (method, route), slo in ROUTE_SLOS.items():
        observed = snapshot.get(f"{method} {route}")
        if observed is None:
            continue
        target = SLO_TARGETS[slo]
        entry = report.setdefault(slo, {"target": target, "observed": [], "met": True})
        entry["observed"].append({"route": f"{method} {route}", **observed})
        if observed["p95_ms"] > target["p95_ms"] or observed["error_rate"] > target["error_rate"]:
            entry["met"] = False
    if execution["jobs"]:
        target = SLO_TARGETS["code_execution"]
        report["code_execution"] = {
            "target": target,
            "observed": {
                "p95_ms": execution["p95_ms"],
                "failure_rate": execution["infrastructure_failure_rate"],
            },
            "met": execution["p95_ms"] <= target["p95_ms"]
            and execution["infrastructure_failure_rate"] <= target["failure_rate"],
        }
    if evaluation["evaluations"]:
        target = SLO_TARGETS["evaluation_availability"]
        report["evaluation_availability"] = {
            "target": target,
            "observed": {
                "degraded_rate": evaluation["degraded_rate"],
                "failure_rate": evaluation["failure_rate"],
            },
            "met": evaluation["degraded_rate"] <= target["degraded_rate"]
            and evaluation["failure_rate"] <= target["failure_rate"],
        }
    return report
