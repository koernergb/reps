from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.analytics import track
from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.execution.service import rate_limiter
from app.interview import service
from app.interview.state_machine import State

MESSAGES_PER_MINUTE = 30

router = APIRouter(prefix="/v1/interviews", tags=["interviews"])
Key = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class StartRequest(BaseModel):
    problem_slug: str
    mode: Literal["practice", "mock"] = "practice"
    time_multiplier: float = Field(default=1.0, ge=1.0, le=2.0)
    reduce_motion: bool = False


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    expected_version: int
    idempotency_key: str = Key
    client_timestamp: datetime | None = None


class CodeRequest(BaseModel):
    code: str = Field(max_length=50_000)
    idempotency_key: str = Key


class AdvanceRequest(BaseModel):
    target: State
    expected_version: int
    idempotency_key: str = Key


class VersionedRequest(BaseModel):
    expected_version: int
    idempotency_key: str = Key


class IdleRequest(BaseModel):
    expected_version: int
    idle_seconds: float = Field(ge=0, le=86400)


@router.post("", status_code=201)
def start(body: StartRequest, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    interview = service.start_session(
        db, user, body.problem_slug, body.mode, body.time_multiplier, body.reduce_motion
    )
    track(db, user.id, "interview_started", {"mode": body.mode, "from_task": False})
    db.commit()
    return service.session_view(db, interview)


@router.get("")
def list_sessions(db: SessionDependency, user: UserDependency) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.evaluation.service import latest_evaluation
    from app.models import InterviewSession, Problem

    rows = db.execute(
        select(InterviewSession, Problem.slug, Problem.title)
        .join(Problem, Problem.id == InterviewSession.problem_id)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.started_at.desc())
        .limit(100)
    ).all()
    result = []
    for interview, slug, title in rows:
        evaluation = latest_evaluation(db, interview.id)
        facts = (evaluation.report or {}).get("facts", {}) if evaluation else {}
        result.append(
            {
                "id": interview.id,
                "problem_slug": slug,
                "problem_title": title,
                "mode": interview.mode,
                "state": interview.state,
                "result": facts.get("result") or interview.result,
                "started_at": interview.started_at.isoformat(),
                "completed_at": interview.completed_at.isoformat()
                if interview.completed_at
                else None,
                "hints_used": interview.hints_used,
                "evaluation_id": evaluation.id if evaluation else None,
            }
        )
    return result


@router.get("/{session_id}")
def get_session(session_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    service.expire_if_needed(db, interview)
    return service.session_view(db, interview)


@router.post("/{session_id}/messages")
def post_message(
    session_id: str, body: MessageRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    if not rate_limiter.allow(f"messages:{user.id}", MESSAGES_PER_MINUTE):
        raise ApiError(429, "rate_limited", "You're sending messages quickly. Wait a moment.")
    service.post_message(
        db,
        user,
        interview,
        body.content,
        body.expected_version,
        body.idempotency_key,
        body.client_timestamp,
    )
    return service.session_view(db, interview)


@router.put("/{session_id}/code")
def save_code(
    session_id: str, body: CodeRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    service.save_code(db, interview, body.code, body.idempotency_key, "checkpoint")
    return {"version": interview.version, "saved": True}


@router.post("/{session_id}/advance")
def advance(
    session_id: str, body: AdvanceRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    service.advance(db, user, interview, body.target, body.expected_version, body.idempotency_key)
    return service.session_view(db, interview)


@router.post("/{session_id}/hints")
def hint(
    session_id: str, body: VersionedRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    service.request_hint(db, user, interview, body.expected_version, body.idempotency_key)
    track(
        db,
        user.id,
        "hint_given",
        {"level": interview.max_hint_level, "mode": interview.mode, "surface": "interview"},
    )
    db.commit()
    return service.session_view(db, interview)


@router.post("/{session_id}/idle")
def idle(
    session_id: str, body: IdleRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    interview = service.get_owned(db, user.id, session_id)
    service.idle_checkin(db, user, interview, body.expected_version, body.idle_seconds)
    return service.session_view(db, interview)
