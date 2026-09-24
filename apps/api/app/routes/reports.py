from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.analytics import track
from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.evaluation.service import evaluate_session, latest_evaluation
from app.learning.evidence import recompute_many
from app.models import (
    Capability,
    CapabilityEvidence,
    DiagnosisFlag,
    InterviewEvaluation,
    InterviewEvent,
    InterviewSession,
)

router = APIRouter(prefix="/v1/interviews", tags=["reports"])


class FlagRequest(BaseModel):
    capability_slug: str | None = None
    reason: str = Field(min_length=3, max_length=2000)


def report_view(
    db: SessionDependency, interview: InterviewSession, evaluation: InterviewEvaluation
) -> dict[str, Any]:
    names = {
        slug: name for slug, name in db.execute(select(Capability.slug, Capability.name)).tuples()
    }
    events = {
        event.id: {
            "sequence": event.sequence,
            "type": event.event_type,
            "actor": event.actor,
            "excerpt": str(event.payload.get("content", ""))[:240],
        }
        for event in db.scalars(
            select(InterviewEvent).where(InterviewEvent.session_id == interview.id)
        )
    }
    flags = db.scalars(
        select(DiagnosisFlag).where(DiagnosisFlag.evaluation_id == evaluation.id)
    ).all()
    return {
        "evaluation_id": evaluation.id,
        "session_id": interview.id,
        "status": evaluation.status,
        "evaluator": evaluation.evaluator,
        "provider": evaluation.provider,
        "model": evaluation.model,
        "prompt_version": evaluation.prompt_version,
        "schema_version": evaluation.schema_version,
        "created_at": evaluation.created_at.isoformat(),
        "report": evaluation.report,
        "capability_names": names,
        "evidence": events,
        "flags": [
            {"capability_slug": flag.capability_slug, "reason": flag.reason, "status": flag.status}
            for flag in flags
        ],
    }


@router.get("/{session_id}/report")
def get_report(session_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    interview = db.get(InterviewSession, session_id)
    if interview is None or interview.user_id != user.id:
        raise ApiError(404, "session_not_found", "Interview session not found.")
    evaluation = latest_evaluation(db, session_id)
    if evaluation is None:
        raise ApiError(
            404, "report_not_ready", "The report is not ready. Finish the interview first."
        )
    return report_view(db, interview, evaluation)


@router.post("/{session_id}/report/retry")
def retry_report(session_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    interview = db.get(InterviewSession, session_id)
    if interview is None or interview.user_id != user.id:
        raise ApiError(404, "session_not_found", "Interview session not found.")
    if interview.state not in ("COMPLETE", "ABANDONED"):
        raise ApiError(409, "session_active", "Finish the interview before evaluating it.")
    evaluation = evaluate_session(db, interview)
    return report_view(db, interview, evaluation)


@router.post("/{session_id}/report/flags", status_code=201)
def flag_report(
    session_id: str, body: FlagRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    """Report an inaccurate diagnosis. The flagged capability's evidence from this interview is
    excluded from the learner model and aggregates are recomputed immediately."""
    interview = db.get(InterviewSession, session_id)
    if interview is None or interview.user_id != user.id:
        raise ApiError(404, "session_not_found", "Interview session not found.")
    evaluation = latest_evaluation(db, session_id)
    if evaluation is None:
        raise ApiError(404, "report_not_ready", "No report to flag yet.")
    db.add(
        DiagnosisFlag(
            user_id=user.id,
            evaluation_id=evaluation.id,
            capability_slug=body.capability_slug,
            reason=body.reason,
            status="accepted",
            created_at=datetime.now(UTC),
        )
    )
    query = select(CapabilityEvidence).where(
        CapabilityEvidence.user_id == user.id,
        CapabilityEvidence.source_type == "interview",
        CapabilityEvidence.source_id == interview.id,
    )
    if body.capability_slug:
        capability_id = db.scalar(
            select(Capability.id).where(Capability.slug == body.capability_slug)
        )
        query = query.where(CapabilityEvidence.capability_id == capability_id)
    touched = set()
    for row in db.scalars(query):
        row.excluded = True
        row.excluded_reason = f"learner flagged diagnosis: {body.reason[:200]}"
        touched.add(row.capability_id)
    recompute_many(db, user.id, touched)
    track(db, user.id, "diagnosis_flagged", {"has_capability": body.capability_slug is not None})
    db.commit()
    return report_view(db, interview, evaluation)
