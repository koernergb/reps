import shutil
import subprocess
import time
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.config import get_settings
from app.deps import SessionDependency, UserDependency
from app.metrics import (
    evaluation_metrics,
    execution_metrics,
    llm_metrics,
    request_metrics,
    scheduling_metrics,
    slo_report,
)
from app.models import ExecutionJob, LLMCall

router = APIRouter(prefix="/v1/system", tags=["system"])
_sandbox_cache: dict[str, Any] = {"checked": 0.0, "ready": False}


def sandbox_ready() -> bool:
    settings = get_settings()
    if settings.execution_backend != "docker":
        return settings.environment == "test"
    now = time.monotonic()
    if now - _sandbox_cache["checked"] < 30:
        return bool(_sandbox_cache["ready"])
    docker = shutil.which("docker")
    ready = False
    if docker:
        try:
            ready = (
                subprocess.run(
                    [docker, "image", "inspect", settings.sandbox_image],
                    capture_output=True,
                    timeout=5,
                    check=False,
                ).returncode
                == 0
            )
        except (OSError, subprocess.TimeoutExpired):
            ready = False
    _sandbox_cache.update(checked=now, ready=ready)
    return ready


@router.get("/status")
def system_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "execution": {
            "enabled": settings.execution_enabled,
            "backend": settings.execution_backend,
            "sandbox_ready": sandbox_ready() if settings.execution_enabled else False,
        },
        "llm": {"provider": settings.llm_provider},
        "features": {
            "interviews": settings.feature_interviews,
            "semantic_evaluation": settings.feature_semantic_evaluation,
            "scheduling": settings.feature_scheduling,
            "drills": settings.feature_drills,
            "mock_mode": settings.feature_mock_mode,
            "solution_viewing": settings.feature_solution_viewing,
        },
        "content": {"allow_unreviewed": settings.allow_unreviewed_content},
    }


@router.get("/metrics")
def metrics(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    """Content-free operational metrics for the last hour (requests) / 24 hours (jobs)."""
    requests = request_metrics.snapshot()
    execution = execution_metrics(db)
    evaluation = evaluation_metrics(db)
    return {
        "requests": requests,
        "execution": execution,
        "llm": llm_metrics(db),
        "evaluation": evaluation,
        "scheduling": scheduling_metrics(db),
        "slo": slo_report(requests, execution, evaluation),
    }


@router.get("/diagnostics")
def diagnostics(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    """Support view: job and model-call states by id without learner content."""
    jobs = db.scalars(
        select(ExecutionJob)
        .where(ExecutionJob.user_id == user.id)
        .order_by(ExecutionJob.created_at.desc())
        .limit(20)
    ).all()
    calls = db.scalars(
        select(LLMCall)
        .where(LLMCall.user_id == user.id)
        .order_by(LLMCall.created_at.desc())
        .limit(20)
    ).all()
    last_finished = max((job.finished_at for job in jobs if job.finished_at), default=None)
    return {
        "worker": {
            "queued": sum(1 for job in jobs if job.status == "queued"),
            "running": sum(1 for job in jobs if job.status == "running"),
            "last_finished_at": last_finished.isoformat() if last_finished else None,
        },
        "recent_jobs": [
            {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "verdict": job.verdict,
                "backend": job.backend,
                "attempts": job.attempts,
                "created_at": job.created_at.isoformat(),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            }
            for job in jobs
        ],
        "recent_llm_calls": [
            {
                "id": call.id,
                "task": call.task,
                "status": call.status,
                "error_code": call.error_code,
                "model": call.model,
                "prompt_version": call.prompt_version,
                "latency_ms": call.latency_ms,
                "created_at": call.created_at.isoformat(),
            }
            for call in calls
        ],
    }
