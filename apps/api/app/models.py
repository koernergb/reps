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
    common_mistakes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    follow_up_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluator_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
    source_id: Mapped[str | None] = mapped_column(String(100))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    problem: Mapped[Problem | None] = relationship(back_populates="exercises")
    attempts: Mapped[list[ReviewAttempt]] = relationship(back_populates="exercise")


class ReviewAttempt(TimestampMixin, Base):
    __tablename__ = "review_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    answer: Mapped[str | None] = mapped_column(Text)
    correctness: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[int | None] = mapped_column(Integer)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    user: Mapped[User] = relationship(back_populates="review_attempts")
    exercise: Mapped[Exercise] = relationship(back_populates="attempts")

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

    user: Mapped[User] = relationship(back_populates="capability_states")

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

    user: Mapped[User] = relationship(back_populates="interview_sessions")
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

    session: Mapped[InterviewSession] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_event_session_sequence"),
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

    session: Mapped[InterviewSession | None] = relationship(back_populates="hints")

    __table_args__ = (
        CheckConstraint("hint_level >= 1 AND hint_level <= 5", name="ck_hint_level"),
        CheckConstraint(
            "session_id IS NOT NULL OR exercise_id IS NOT NULL", name="ck_hint_context"
        ),
    )
