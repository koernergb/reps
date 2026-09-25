"""corpus metadata and execution jobs

Revision ID: 20260924_0003
Revises: d9bbc4a646f9
Create Date: 2026-09-24 17:39:43.256864

Rollout note: new NOT NULL columns carry server defaults so existing development rows remain
valid; `pnpm db:seed` then synchronizes problem and exercise rows from the corpus files.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0003"
down_revision: str | None = "d9bbc4a646f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("review_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=30), nullable=True),
        sa.Column("result_public", sa.JSON(), nullable=False),
        sa.Column("result_private", sa.JSON(), nullable=False),
        sa.Column("backend", sa.String(length=40), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('run', 'submit')", name="ck_execution_kind"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'expired')",
            name="ck_execution_status",
        ),
        sa.ForeignKeyConstraint(["problem_id"], ["problems.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_attempt_id"], ["review_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_execution_idempotency"),
    )
    with op.batch_alter_table("execution_jobs") as batch_op:
        batch_op.create_index("ix_execution_jobs_problem_id", ["problem_id"])
        batch_op.create_index("ix_execution_jobs_review_attempt_id", ["review_attempt_id"])
        batch_op.create_index("ix_execution_jobs_session_id", ["session_id"])
        batch_op.create_index("ix_execution_jobs_user_id", ["user_id"])
        batch_op.create_index("ix_execution_status_created", ["status", "created_at"])

    with op.batch_alter_table("exercises") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="development")
        )
        batch_op.add_column(
            sa.Column("estimated_minutes", sa.Float(), nullable=False, server_default="2")
        )
        batch_op.add_column(
            sa.Column("content_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_unique_constraint("uq_exercises_source_id", ["source_id"])

    with op.batch_alter_table("problem_evaluators") as batch_op:
        batch_op.add_column(sa.Column("hints", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("key_insight", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("clarifications", sa.JSON(), nullable=False, server_default="[]")
        )

    with op.batch_alter_table("problems") as batch_op:
        batch_op.add_column(sa.Column("topic_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("content_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("role", sa.String(length=20), nullable=False, server_default="canonical")
        )
        batch_op.add_column(sa.Column("transfer_group", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("patterns", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(
            sa.Column("related_slugs", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.create_index("ix_problems_topic_id", ["topic_id"])
        batch_op.create_index("ix_problems_transfer_group", ["transfer_group"])
        batch_op.create_foreign_key(
            "fk_problems_topic_id", "topics", ["topic_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("problems") as batch_op:
        batch_op.drop_constraint("fk_problems_topic_id", type_="foreignkey")
        batch_op.drop_index("ix_problems_transfer_group")
        batch_op.drop_index("ix_problems_topic_id")
        for column in (
            "related_slugs",
            "patterns",
            "transfer_group",
            "role",
            "content_version",
            "topic_id",
        ):
            batch_op.drop_column(column)

    with op.batch_alter_table("problem_evaluators") as batch_op:
        for column in ("clarifications", "key_insight", "hints"):
            batch_op.drop_column(column)

    with op.batch_alter_table("exercises") as batch_op:
        batch_op.drop_constraint("uq_exercises_source_id", type_="unique")
        for column in ("content_version", "estimated_minutes", "status"):
            batch_op.drop_column(column)

    op.drop_table("execution_jobs")
