"""Add the generic study system.

Revision ID: 20261113_0007
Revises: 20261027_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261113_0007"
down_revision: str | None = "20261027_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("color", sa.String(20), nullable=False, server_default="#166534"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_study_courses_status"),
    )
    op.create_index("ix_study_courses_user_id", "study_courses", ["user_id"])
    op.create_table(
        "study_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("study_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_study_units_user_id", "study_units", ["user_id"])
    op.create_index("ix_study_units_course_id", "study_units", ["course_id"])
    op.create_table(
        "study_concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("study_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("study_units.id", ondelete="SET NULL")),
        sa.Column("capability_id", sa.String(36), sa.ForeignKey("capabilities.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_study_concepts_user_id", "study_concepts", ["user_id"])
    op.create_index("ix_study_concepts_course_id", "study_concepts", ["course_id"])
    op.create_index("ix_study_concepts_unit_id", "study_concepts", ["unit_id"])
    op.create_table(
        "study_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("study_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="notes"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_study_sources_user_id", "study_sources", ["user_id"])
    op.create_index("ix_study_sources_course_id", "study_sources", ["course_id"])
    op.create_table(
        "study_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("study_courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("study_units.id", ondelete="SET NULL")),
        sa.Column("concept_id", sa.String(36), sa.ForeignKey("study_concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("study_sources.id", ondelete="SET NULL")),
        sa.Column("card_type", sa.String(24), nullable=False, server_default="basic"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("accepted_answers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("stability_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("next_review_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("card_type IN ('basic', 'reversed', 'cloze', 'typed', 'explain', 'compare')", name="ck_study_cards_type"),
        sa.CheckConstraint("status IN ('draft', 'active', 'suspended', 'archived')", name="ck_study_cards_status"),
    )
    for column in ("user_id", "course_id", "unit_id", "concept_id", "source_id", "next_review_at"):
        op.create_index(f"ix_study_cards_{column}", "study_cards", [column])
    with op.batch_alter_table("review_tasks") as batch:
        batch.add_column(sa.Column("study_card_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_review_tasks_study_card",
            "study_cards",
            ["study_card_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_index("ix_review_tasks_study_card_id", ["study_card_id"])
    op.create_table(
        "study_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("study_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("review_tasks.id", ondelete="SET NULL")),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("correctness", sa.Float(), nullable=False),
        sa.Column("interval_days", sa.Float(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating IN ('again', 'hard', 'good', 'easy')", name="ck_study_reviews_rating"),
    )
    for column in ("user_id", "card_id", "task_id"):
        op.create_index(f"ix_study_reviews_{column}", "study_reviews", [column])


def downgrade() -> None:
    op.drop_table("study_reviews")
    with op.batch_alter_table("review_tasks") as batch:
        batch.drop_index("ix_review_tasks_study_card_id")
        batch.drop_constraint("fk_review_tasks_study_card", type_="foreignkey")
        batch.drop_column("study_card_id")
    op.drop_table("study_cards")
    op.drop_table("study_sources")
    op.drop_table("study_concepts")
    op.drop_table("study_units")
    op.drop_table("study_courses")
