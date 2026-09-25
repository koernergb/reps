from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.deps import SessionDependency, UserDependency
from app.models import ReviewTask
from app.reviews import service

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


class StartRequest(BaseModel):
    drill_session_id: str | None = None


class AnswerRequest(BaseModel):
    answer: str | None = Field(default=None, max_length=8000)
    job_id: str | None = None
    confidence: int | None = Field(default=None, ge=1, le=5)


class ConfirmRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=4000)


class SnoozeRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=7)


class ReportRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/queue")
def queue(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return service.queue(db, user)


@router.get("/history")
def history(db: SessionDependency, user: UserDependency) -> list[dict[str, Any]]:
    return service.history(db, user)


@router.post("/tasks/{task_id}/start")
def start(
    task_id: str, body: StartRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    return service.start(db, user, task_id, body.drill_session_id)


@router.post("/tasks/{task_id}/snooze")
def snooze(
    task_id: str, body: SnoozeRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    return service.snooze(db, user, task_id, body.days)


@router.post("/tasks/{task_id}/skip")
def skip(task_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return service.close(db, user, task_id, "skipped")


@router.post("/tasks/{task_id}/report")
def report(
    task_id: str, body: ReportRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    return service.close(db, user, task_id, "invalidated", body.reason)


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    attempt = service.owned_attempt(db, user, attempt_id)
    task = db.get(ReviewTask, attempt.task_id) if attempt.task_id else None
    return service.item_view(db, attempt, task)


@router.post("/attempts/{attempt_id}/hint")
def hint(attempt_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return service.request_hint(db, user, attempt_id)


@router.post("/attempts/{attempt_id}/answer")
def answer(
    attempt_id: str, body: AnswerRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    return service.answer(
        db, user, attempt_id, text=body.answer, job_id=body.job_id, confidence=body.confidence
    )


@router.post("/attempts/{attempt_id}/confirm")
def confirm(
    attempt_id: str, body: ConfirmRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    return service.confirm(db, user, attempt_id, body.answer)
