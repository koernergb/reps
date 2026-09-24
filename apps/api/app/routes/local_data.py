from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from sqlalchemy import Select, inspect, select
from sqlalchemy.orm import Session

from app.deps import SessionDependency, UserDependency
from app.local_mode import get_local_user
from app.models import Base, InterviewSession
from app.schemas import LocalDataExport, LocalProfile, ResetResult

router = APIRouter(prefix="/v1/me", tags=["local data"])


@dataclass(frozen=True)
class OwnedTable:
    """A table holding learner-owned rows, exported and deleted with the learner's history."""

    name: str
    # Columns never exported (server-only evaluator detail such as hidden-test results).
    private_columns: frozenset[str] = field(default_factory=frozenset)
    # Tables without a user_id column are owned through their interview session.
    via_session: bool = False


# Order matters for deletion: children before parents.
OWNED_TABLES: tuple[OwnedTable, ...] = (
    OwnedTable("diagnosis_flags"),
    OwnedTable("interview_evaluations"),
    OwnedTable("llm_calls"),
    OwnedTable("solution_views"),
    OwnedTable("interview_events", via_session=True),
    OwnedTable("hint_logs"),
    OwnedTable("execution_jobs", private_columns=frozenset({"result_private"})),
    OwnedTable("capability_evidence"),
    OwnedTable("analytics_events"),
    OwnedTable("review_attempts"),
    OwnedTable("review_tasks"),
    OwnedTable("drill_sessions"),
    OwnedTable("learner_capability_states"),
    OwnedTable("interview_sessions"),
)
EXPORT_KEYS = {
    "review_attempts": "review_attempts",
    "learner_capability_states": "capability_states",
    "interview_sessions": "interview_sessions",
    "interview_events": "interview_events",
    "hint_logs": "hint_logs",
}


def model_for(table_name: str) -> Any:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == table_name:  # type: ignore[attr-defined]
            return mapper.class_
    raise KeyError(table_name)


def owned_query(table: OwnedTable, user_id: str) -> Select[Any]:
    model = model_for(table.name)
    if table.via_session:
        session_ids = select(InterviewSession.id).where(InterviewSession.user_id == user_id)
        return select(model).where(model.session_id.in_(session_ids))
    return select(model).where(model.user_id == user_id)


def serialize_row(row: Any, private: frozenset[str] = frozenset()) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column in inspect(row).mapper.column_attrs:
        if column.key in private or column.key == "user_id":
            continue
        value = getattr(row, column.key)
        result[column.key] = value.isoformat() if isinstance(value, datetime) else value
    return result


def export_user_data(session: Session, user_id: str) -> dict[str, list[dict[str, Any]]]:
    exported: dict[str, list[dict[str, Any]]] = {}
    for table in OWNED_TABLES:
        rows = session.scalars(owned_query(table, user_id)).all()
        exported[table.name] = [serialize_row(row, table.private_columns) for row in rows]
    return exported


def delete_user_history(session: Session, user_id: str) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for table in OWNED_TABLES:
        rows = session.scalars(owned_query(table, user_id)).all()
        for row in rows:
            session.delete(row)
        session.flush()
        deleted[table.name] = len(rows)
    session.commit()
    return deleted


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
def export_local_data(session: SessionDependency, user: UserDependency) -> LocalDataExport:
    tables = export_user_data(session, user.id)
    legacy = {key: tables.pop(name) for name, key in EXPORT_KEYS.items()}
    return LocalDataExport(
        schema_version=2,
        exported_at=datetime.now().astimezone(),
        profile={
            "id": user.id,
            "display_name": user.display_name,
            "mode": user.mode,
            "created_at": user.created_at.isoformat(),
        },
        additional=tables,
        **legacy,
    )


@router.delete("/history", response_model=ResetResult)
def reset_local_history(session: SessionDependency, user: UserDependency) -> ResetResult:
    deleted = delete_user_history(session, user.id)
    renamed = {EXPORT_KEYS.get(name, name): count for name, count in deleted.items()}
    return ResetResult(status="reset", deleted=renamed)
