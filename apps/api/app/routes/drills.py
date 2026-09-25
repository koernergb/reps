from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import SessionDependency, UserDependency
from app.drills import service
from app.models import DrillSession

router = APIRouter(prefix="/v1/drills", tags=["drills"])


class CreateRequest(BaseModel):
    budget_minutes: int = Field(default=10, ge=5, le=30)


class ActionRequest(BaseModel):
    action: Literal["pause", "resume", "complete", "abandon"]


@router.post("", status_code=201)
def create(body: CreateRequest, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return service.drill_view(db, service.create_drill(db, user, body.budget_minutes))


@router.get("/active")
def active(db: SessionDependency, user: UserDependency) -> dict[str, Any] | None:
    drill = db.scalar(
        select(DrillSession).where(
            DrillSession.user_id == user.id, DrillSession.status.in_(("active", "paused"))
        )
    )
    return service.drill_view(db, drill) if drill else None


@router.get("/{drill_id}")
def get(drill_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return service.drill_view(db, service.owned_drill(db, user, drill_id))


@router.post("/{drill_id}/actions")
def act(
    drill_id: str, body: ActionRequest, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    drill = service.owned_drill(db, user, drill_id)
    return service.drill_view(db, service.set_status(db, user, drill, body.action))
