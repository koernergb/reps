from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "reps-api"
    version: str = "0.1.0"
    request_id: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CapabilitySummary(BaseModel):
    slug: str
    name: str
    capability_type: str
    weight: float


class ProblemSummary(BaseModel):
    id: str
    slug: str
    title: str
    difficulty: str
    language: str
    status: str
    capabilities: list[CapabilitySummary]


class ProblemDetail(ProblemSummary):
    statement: str
    examples: list[dict[str, Any]]
    constraints: list[str]
    starter_code: str
    visible_tests: list[dict[str, Any]]


class LocalProfile(BaseModel):
    id: str
    display_name: str
    mode: Literal["local"]
    warning: str


class LocalDataExport(BaseModel):
    schema_version: int = 1
    exported_at: datetime
    profile: dict[str, Any]
    review_attempts: list[dict[str, Any]]
    capability_states: list[dict[str, Any]]
    interview_sessions: list[dict[str, Any]]
    interview_events: list[dict[str, Any]]
    hint_logs: list[dict[str, Any]]


class ResetResult(BaseModel):
    status: Literal["reset"]
    deleted: dict[str, int]
