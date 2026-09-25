from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Local learner")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    daily_review_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    review_attempts: Mapped[list[ReviewAttempt]] = relationship(back_populates="user")
    capability_states: Mapped[list[LearnerCapabilityState]] = relationship(back_populates="user")
    interview_sessions: Mapped[list[InterviewSession]] = relationship(back_populates="user")

    __table_args__ = (CheckConstraint("mode IN ('local', 'authenticated')", name="ck_users_mode"),)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )

    parent: Mapped[Topic | None] = relationship(remote_side="Topic.id", back_populates="children")
    children: Mapped[list[Topic]] = relationship(back_populates="parent")
    capabilities: Mapped[list[Capability]] = relationship(back_populates="topic")


class Capability(TimestampMixin, Base):
    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    capability_type: Mapped[str] = mapped_column(String(32), nullable=False)

    topic: Mapped[Topic] = relationship(back_populates="capabilities")
    problem_links: Mapped[list[ProblemCapability]] = relationship(back_populates="capability")

    __table_args__ = (
        CheckConstraint(
            "capability_type IN ('recall', 'recognition', 'reasoning', 'implementation', "
            "'debugging', 'communication', 'complexity', 'independence', 'transfer')",
            name="ck_capabilities_type",
        ),
    )


class Problem(TimestampMixin, Base):
    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="canonical")
    transfer_group: Mapped[str | None] = mapped_column(String(100), index=True)
    patterns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    related_slugs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="python")
    time_complexity: Mapped[str] = mapped_column(String(80), nullable=False)
    space_complexity: Mapped[str] = mapped_column(String(80), nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    visible_tests: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="development")

    topic: Mapped[Topic | None] = relationship()
    capability_links: Mapped[list[ProblemCapability]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    evaluator: Mapped[ProblemEvaluator | None] = relationship(
        back_populates="problem", cascade="all, delete-orphan", uselist=False
    )
    exercises: Mapped[list[Exercise]] = relationship(back_populates="problem")

    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_problems_difficulty"),
        CheckConstraint(
            "status IN ('development', 'reviewed', 'retired')", name="ck_problems_status"
        ),
    )


class ProblemEvaluator(TimestampMixin, Base):
    """Server-only evaluator material. Never serialize this model to a public response."""

    __tablename__ = "problem_evaluators"

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    reference_solution: Mapped[str] = mapped_column(Text, nullable=False)
    hidden_tests: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    common_mistakes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluator_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    key_insight: Mapped[str] = mapped_column(Text, nullable=False, default="")
    clarifications: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)

    problem: Mapped[Problem] = relationship(back_populates="evaluator")


class ProblemCapability(Base):
    __tablename__ = "problem_capabilities"

    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    problem: Mapped[Problem] = relationship(back_populates="capability_links")
    capability: Mapped[Capability] = relationship(back_populates="problem_links")

    __table_args__ = (CheckConstraint("weight > 0 AND weight <= 1", name="ck_problem_cap_weight"),)


class Exercise(TimestampMixin, Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[str | None] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), index=True
    )
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="development")
    estimated_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=2)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    problem: Mapped[Problem | None] = relationship(back_populates="exercises")
    capability: Mapped[Capability] = relationship()
    attempts: Mapped[list[ReviewAttempt]] = relationship(back_populates="exercise")


class ReviewAttempt(TimestampMixin, Base):
    __tablename__ = "review_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )
    problem_id: Mapped[str | None] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="SET NULL"), index=True
    )
    drill_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("drill_sessions.id", ondelete="SET NULL"), index=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="retrieve")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer: Mapped[str | None] = mapped_column(Text)
    correctness: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[int | None] = mapped_column(Integer)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[User] = relationship(back_populates="review_attempts")
    exercise: Mapped[Exercise | None] = relationship(back_populates="attempts")

    __table_args__ = (
        CheckConstraint(
            "correctness IS NULL OR (correctness >= 0 AND correctness <= 1)",
            name="ck_attempt_correctness",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 1 AND confidence <= 5)",
            name="ck_attempt_confidence",
        ),
        CheckConstraint("hints_used >= 0", name="ck_attempt_hints"),
    )


class LearnerCapabilityState(TimestampMixin, Base):
    __tablename__ = "learner_capability_states"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"), primary_key=True
    )
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stability: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    band: Mapped[str] = mapped_column(String(20), nullable=False, default="Weak")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    user: Mapped[User] = relationship(back_populates="capability_states")
    capability: Mapped[Capability] = relationship()

    __table_args__ = (
        CheckConstraint("mastery >= 0 AND mastery <= 1", name="ck_state_mastery"),
        CheckConstraint("stability >= 0", name="ck_state_stability"),
        CheckConstraint("difficulty >= 0 AND difficulty <= 1", name="ck_state_difficulty"),
        CheckConstraint("evidence_count >= 0", name="ck_state_evidence_count"),
    )


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="INTRO")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(String(40))
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    problem_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_hint_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_code: Mapped[str | None] = mapped_column(Text)
    time_limit_s: Mapped[int | None] = mapped_column(Integer)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solution_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accommodations: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[User] = relationship(back_populates="interview_sessions")
    problem: Mapped[Problem] = relationship()
    events: Mapped[list[InterviewEvent]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    hints: Mapped[list[HintLog]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("mode IN ('practice', 'mock')", name="ck_sessions_mode"),
        Index("ix_sessions_user_started", "user_id", "started_at"),
    )


class InterviewEvent(Base):
    __tablename__ = "interview_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    client_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(80))

    session: Mapped[InterviewSession] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_event_session_sequence"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_event_idempotency"),
        Index("ix_events_session_occurred", "session_id", "occurred_at"),
    )


class HintLog(Base):
    __tablename__ = "hint_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )
    hint_level: Mapped[int] = mapped_column(Integer, nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capability_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    review_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_attempts.id", ondelete="CASCADE"), index=True
    )

    session: Mapped[InterviewSession | None] = relationship(back_populates="hints")

    __table_args__ = (
        CheckConstraint("hint_level >= 1 AND hint_level <= 5", name="ck_hint_level"),
        CheckConstraint(
            "session_id IS NOT NULL OR exercise_id IS NOT NULL", name="ck_hint_context"
        ),
    )


class ExecutionJob(Base):
    """An immutable request to run learner code in the sandbox.

    `code` is learner content; it is exported and deleted with the learner's history and is
    never written to logs. `result_private` includes hidden-test detail and must never be
    returned to a client.
    """

    __tablename__ = "execution_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    review_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("review_attempts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str | None] = mapped_column(String(30))
    result_public: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_private: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    backend: Mapped[str | None] = mapped_column(String(40))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_execution_idempotency"),
        CheckConstraint("kind IN ('run', 'submit')", name="ck_execution_kind"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'expired')",
            name="ck_execution_status",
        ),
        Index("ix_execution_status_created", "status", "created_at"),
    )


class InterviewEvaluation(Base):
    """A structured post-interview diagnosis with full provenance."""

    __tablename__ = "interview_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluator: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_seq_from: Mapped[int] = mapped_column(Integer, nullable=False)
    event_seq_to: Mapped[int] = mapped_column(Integer, nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fallback_used: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'degraded', 'failed')", name="ck_evaluation_status"
        ),
    )


class DiagnosisFlag(Base):
    """A learner report that a diagnosis is inaccurate. Accepted flags exclude evidence."""

    __tablename__ = "diagnosis_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("interview_evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_slug: Mapped[str | None] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="accepted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CapabilityEvidence(Base):
    """Append-only learner evidence. Aggregate state is always recomputable from these rows."""

    __tablename__ = "capability_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    problem_id: Mapped[str | None] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    hint_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False)
    assisted: Mapped[bool] = mapped_column(nullable=False, default=False)
    transfer: Mapped[bool] = mapped_column(nullable=False, default=False)
    repeat_exposure: Mapped[bool] = mapped_column(nullable=False, default=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    excluded: Mapped[bool] = mapped_column(nullable=False, default=False)
    excluded_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_evidence_dedupe"),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_evidence_score"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_evidence_confidence"),
        Index("ix_evidence_user_capability_time", "user_id", "capability_id", "occurred_at"),
    )


class ReviewTask(Base):
    """A scheduled remediation item. At most one active task per (user, dedupe_key)."""

    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_id: Mapped[str] = mapped_column(
        ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), index=True
    )
    problem_id: Mapped[str | None] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chain_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    capability: Mapped[Capability] = relationship()
    exercise: Mapped[Exercise | None] = relationship()
    problem: Mapped[Problem | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'snoozed', 'skipped', 'completed', 'invalidated', 'superseded')",
            name="ck_task_status",
        ),
        Index("ix_tasks_user_status_due", "user_id", "status", "due_at"),
        Index(
            "uq_tasks_active_dedupe",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'snoozed')"),
            sqlite_where=text("status IN ('pending', 'snoozed')"),
        ),
    )


class DrillSession(Base):
    __tablename__ = "drill_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    budget_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'completed', 'abandoned')", name="ck_drill_status"
        ),
    )


class SolutionView(Base):
    __tablename__ = "solution_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[str] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context: Mapped[str] = mapped_column(String(30), nullable=False)


class AnalyticsEvent(Base):
    """Product analytics. Properties are allowlisted; content never appears here."""

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LLMCall(Base):
    """Audit of every model call: provenance, latency, tokens, and outcome. No content."""

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    task: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(60))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LLMCredential(Base):
    """A learner's AI provider key and model choice.

    The key is stored in the local database (plaintext; the database never leaves this machine),
    is never returned by the API beyond a 4-character hint, never logged, excluded from exports,
    and kept when learning history is reset.
    """

    __tablename__ = "llm_credentials"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    api_key: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('openai', 'gemini')", name="ck_llm_credentials_provider"),
    )
