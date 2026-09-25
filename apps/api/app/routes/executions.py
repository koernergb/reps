from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.execution.service import ExecutionRejected, cancel_job, submit_job
from app.models import ExecutionJob, InterviewSession, Problem

router = APIRouter(prefix="/v1/executions", tags=["executions"])


class ExecutionRequest(BaseModel):
    problem_slug: str = Field(min_length=1, max_length=160)
    code: str = Field(max_length=50_000)
    kind: Literal["run", "submit"]
    idempotency_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str | None = None


class ExecutionView(BaseModel):
    id: str
    kind: str
    status: str
    problem_slug: str
    verdict: str | None
    result: dict[str, Any] | None
    created_at: str
    finished_at: str | None


def to_view(job: ExecutionJob, slug: str) -> ExecutionView:
    terminal = job.status in ("completed", "failed", "cancelled", "expired")
    return ExecutionView(
        id=job.id,
        kind=job.kind,
        status=job.status,
        problem_slug=slug,
        verdict=job.verdict,
        result=job.result_public if terminal else None,
        created_at=job.created_at.isoformat(),
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


def owned_job(session: SessionDependency, user_id: str, job_id: str) -> tuple[ExecutionJob, str]:
    row = session.execute(
        select(ExecutionJob, Problem.slug)
        .join(Problem, Problem.id == ExecutionJob.problem_id)
        .where(ExecutionJob.id == job_id, ExecutionJob.user_id == user_id)
    ).first()
    if row is None:
        raise ApiError(404, "execution_not_found", "Execution not found.")
    return row[0], row[1]


@router.post("", response_model=ExecutionView, status_code=202)
def create_execution(
    body: ExecutionRequest, session: SessionDependency, user: UserDependency
) -> ExecutionView:
    if body.session_id is not None:
        interview = session.get(InterviewSession, body.session_id)
        if interview is None or interview.user_id != user.id:
            raise ApiError(404, "session_not_found", "Interview session not found.")
    try:
        job, _ = submit_job(
            session,
            user_id=user.id,
            problem_slug=body.problem_slug,
            code=body.code,
            kind=body.kind,
            idempotency_key=body.idempotency_key,
            session_id=body.session_id,
        )
    except ExecutionRejected as exc:
        raise ApiError(exc.status_code, exc.code, exc.message) from exc
    return to_view(job, body.problem_slug)


@router.get("/{job_id}", response_model=ExecutionView)
def get_execution(job_id: str, session: SessionDependency, user: UserDependency) -> ExecutionView:
    job, slug = owned_job(session, user.id, job_id)
    return to_view(job, slug)


@router.post("/{job_id}/cancel", response_model=ExecutionView)
def cancel_execution(
    job_id: str, session: SessionDependency, user: UserDependency
) -> ExecutionView:
    job, slug = owned_job(session, user.id, job_id)
    cancel_job(session, job)
    return to_view(job, slug)
