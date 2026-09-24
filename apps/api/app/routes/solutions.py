from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.analytics import track
from app.config import get_settings
from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.interview.service import append_event
from app.learning.pipeline import schedule_solution_view
from app.models import InterviewSession, Problem, SolutionView

router = APIRouter(prefix="/v1/problems", tags=["solutions"])


class ViewRequest(BaseModel):
    confirm: bool
    session_id: str | None = None


@router.post("/{slug}/solution")
def view_solution(
    slug: str, body: ViewRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    """Consentful solution viewing. Records assisted exposure and schedules comprehension,
    reconstruction, implementation, and transfer checks instead of granting mastery."""
    if not get_settings().feature_solution_viewing:
        raise ApiError(503, "solutions_disabled", "Solution viewing is currently disabled.")
    if not body.confirm:
        raise ApiError(
            428,
            "confirmation_required",
            "Viewing the solution changes your learning plan. Confirm to continue.",
        )
    problem = db.scalar(select(Problem).where(Problem.slug == slug, Problem.status != "retired"))
    if problem is None or problem.evaluator is None:
        raise ApiError(404, "problem_not_found", "Problem not found.")
    interview = None
    if body.session_id:
        interview = db.get(InterviewSession, body.session_id)
        if interview is None or interview.user_id != user.id or interview.problem_id != problem.id:
            raise ApiError(404, "session_not_found", "Interview session not found.")
    now = datetime.now(UTC)
    view = SolutionView(
        user_id=user.id,
        problem_id=problem.id,
        session_id=interview.id if interview else None,
        viewed_at=now,
        context="interview" if interview else "practice",
    )
    db.add(view)
    db.flush()
    if interview is not None and interview.solution_viewed_at is None:
        interview.solution_viewed_at = now
        if interview.state not in ("COMPLETE", "ABANDONED"):
            append_event(db, interview, "solution_viewed", {"problem_slug": slug}, actor="learner")
    already = db.scalar(
        select(SolutionView.id).where(
            SolutionView.user_id == user.id,
            SolutionView.problem_id == problem.id,
            SolutionView.id != view.id,
        )
    )
    tasks = [] if already else schedule_solution_view(db, user, problem, view.id)
    track(db, user.id, "solution_viewed", {"surface": view.context})
    db.commit()
    return {
        "problem_slug": slug,
        "reference_solution": problem.evaluator.reference_solution,
        "key_insight": problem.evaluator.key_insight,
        "time_complexity": problem.time_complexity,
        "space_complexity": problem.space_complexity,
        "scheduled": [
            {"task_type": task.task_type, "due_at": task.due_at.isoformat(), "reason": task.reason}
            for task in tasks
        ],
        "notice": "This problem now counts as assisted. Success on it later is not treated as "
        "independent transfer; related problems will test the technique.",
    }


@router.get("/{slug}/progress")
def problem_progress(slug: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    """Remediation progress as stages instead of a binary solved badge."""
    from app.models import ReviewTask

    problem = db.scalar(select(Problem).where(Problem.slug == slug))
    if problem is None:
        raise ApiError(404, "problem_not_found", "Problem not found.")
    views = db.scalars(
        select(SolutionView).where(
            SolutionView.user_id == user.id, SolutionView.problem_id == problem.id
        )
    ).all()
    view_ids = [view.id for view in views]
    tasks = (
        db.scalars(
            select(ReviewTask).where(
                ReviewTask.user_id == user.id,
                ReviewTask.source_type == "solution_view",
                ReviewTask.source_id.in_(view_ids),
            )
        ).all()
        if view_ids
        else []
    )
    stages = []
    for task_type, label in (
        ("key_insight", "Assisted comprehension"),
        ("pseudocode", "Reconstruction"),
        ("implementation", "Implementation from memory"),
        ("transfer", "Related problem"),
        ("reinterview", "Unseen transfer"),
    ):
        matching = [task for task in tasks if task.task_type == task_type]
        status = (
            "done"
            if any(task.status == "completed" for task in matching)
            else "scheduled"
            if any(task.status in ("pending", "snoozed") for task in matching)
            else "not_scheduled"
        )
        stages.append({"stage": task_type, "label": label, "status": status})
    return {"solution_viewed": bool(views), "stages": stages if views else []}
