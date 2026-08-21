from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.local_mode import get_local_user, get_session
from app.models import (
    HintLog,
    InterviewEvent,
    InterviewSession,
    LearnerCapabilityState,
    ReviewAttempt,
)
from app.schemas import LocalDataExport, LocalProfile, ResetResult

router = APIRouter(prefix="/v1/me", tags=["local data"])
SessionDependency = Annotated[Session, Depends(get_session)]


def row_dict(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        value = getattr(row, field)
        result[field] = value.isoformat() if isinstance(value, datetime) else value
    return result


@router.get("", response_model=LocalProfile)
def local_profile(session: SessionDependency) -> LocalProfile:
    user = get_local_user(session)
    return LocalProfile(
        id=user.id,
        display_name=user.display_name,
        mode=user.mode,
        warning="Local-only mode has no authentication. Do not expose this service to a network.",
    )


@router.get("/export", response_model=LocalDataExport)
def export_local_data(session: SessionDependency) -> LocalDataExport:
    user = get_local_user(session)
    sessions = session.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.started_at)
    ).all()
    session_ids = [item.id for item in sessions]
    events = (
        session.scalars(
            select(InterviewEvent)
            .where(InterviewEvent.session_id.in_(session_ids))
            .order_by(InterviewEvent.session_id, InterviewEvent.sequence)
        ).all()
        if session_ids
        else []
    )
    return LocalDataExport(
        exported_at=datetime.now().astimezone(),
        profile={
            "id": user.id,
            "display_name": user.display_name,
            "mode": user.mode,
            "created_at": user.created_at.isoformat(),
        },
        review_attempts=[
            row_dict(
                item,
                (
                    "id",
                    "exercise_id",
                    "started_at",
                    "completed_at",
                    "answer",
                    "correctness",
                    "confidence",
                    "hints_used",
                    "evaluation",
                ),
            )
            for item in session.scalars(
                select(ReviewAttempt)
                .where(ReviewAttempt.user_id == user.id)
                .order_by(ReviewAttempt.started_at)
            ).all()
        ],
        capability_states=[
            row_dict(
                item,
                (
                    "capability_id",
                    "mastery",
                    "stability",
                    "difficulty",
                    "last_reviewed_at",
                    "next_review_at",
                    "evidence_count",
                ),
            )
            for item in session.scalars(
                select(LearnerCapabilityState).where(LearnerCapabilityState.user_id == user.id)
            ).all()
        ],
        interview_sessions=[
            row_dict(
                item,
                (
                    "id",
                    "problem_id",
                    "mode",
                    "state",
                    "started_at",
                    "completed_at",
                    "result",
                    "evaluation",
                ),
            )
            for item in sessions
        ],
        interview_events=[
            row_dict(
                item,
                (
                    "id",
                    "session_id",
                    "sequence",
                    "event_type",
                    "occurred_at",
                    "schema_version",
                    "payload",
                ),
            )
            for item in events
        ],
        hint_logs=[
            row_dict(
                item,
                (
                    "id",
                    "session_id",
                    "exercise_id",
                    "hint_level",
                    "hint_text",
                    "occurred_at",
                ),
            )
            for item in session.scalars(
                select(HintLog).where(HintLog.user_id == user.id).order_by(HintLog.occurred_at)
            ).all()
        ],
    )


@router.delete("/history", response_model=ResetResult)
def reset_local_history(session: SessionDependency) -> ResetResult:
    user = get_local_user(session)
    session_ids = list(
        session.scalars(select(InterviewSession.id).where(InterviewSession.user_id == user.id))
    )
    deleted: dict[str, int] = {}

    event_ids = (
        list(
            session.scalars(
                select(InterviewEvent.id).where(InterviewEvent.session_id.in_(session_ids))
            )
        )
        if session_ids
        else []
    )
    if event_ids:
        session.execute(delete(InterviewEvent).where(InterviewEvent.id.in_(event_ids)))
    deleted["interview_events"] = len(event_ids)

    hint_ids = list(session.scalars(select(HintLog.id).where(HintLog.user_id == user.id)))
    attempt_ids = list(
        session.scalars(select(ReviewAttempt.id).where(ReviewAttempt.user_id == user.id))
    )
    state_ids = list(
        session.execute(
            select(
                LearnerCapabilityState.user_id,
                LearnerCapabilityState.capability_id,
            ).where(LearnerCapabilityState.user_id == user.id)
        )
    )
    if hint_ids:
        session.execute(delete(HintLog).where(HintLog.id.in_(hint_ids)))
    if attempt_ids:
        session.execute(delete(ReviewAttempt).where(ReviewAttempt.id.in_(attempt_ids)))
    if state_ids:
        session.execute(
            delete(LearnerCapabilityState).where(LearnerCapabilityState.user_id == user.id)
        )
    if session_ids:
        session.execute(delete(InterviewSession).where(InterviewSession.id.in_(session_ids)))
    deleted["hint_logs"] = len(hint_ids)
    deleted["review_attempts"] = len(attempt_ids)
    deleted["capability_states"] = len(state_ids)
    deleted["interview_sessions"] = len(session_ids)
    session.commit()
    return ResetResult(status="reset", deleted=deleted)
