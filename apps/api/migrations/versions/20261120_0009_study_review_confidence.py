"""Replace study review SM-2 ratings with 0–5 confidence.

Revision ID: 20261120_0009
Revises: 20261120_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261120_0009"
down_revision: str | None = "20261120_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("study_reviews") as batch:
        batch.add_column(sa.Column("confidence", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE study_reviews SET confidence = CASE rating
            WHEN 'again' THEN 0
            WHEN 'hard' THEN 2
            WHEN 'good' THEN 3
            WHEN 'easy' THEN 5
            ELSE 3
        END
        """
    )
    with op.batch_alter_table("study_reviews") as batch:
        batch.alter_column("confidence", existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint("ck_study_reviews_rating", type_="check")
        batch.drop_column("rating")
        batch.create_check_constraint(
            "ck_study_reviews_confidence",
            "confidence >= 0 AND confidence <= 5",
        )


def downgrade() -> None:
    with op.batch_alter_table("study_reviews") as batch:
        batch.add_column(sa.Column("rating", sa.String(10), nullable=True))
    op.execute(
        """
        UPDATE study_reviews SET rating = CASE
            WHEN confidence <= 1 THEN 'again'
            WHEN confidence = 2 THEN 'hard'
            WHEN confidence <= 4 THEN 'good'
            ELSE 'easy'
        END
        """
    )
    with op.batch_alter_table("study_reviews") as batch:
        batch.alter_column("rating", existing_type=sa.String(10), nullable=False)
        batch.drop_constraint("ck_study_reviews_confidence", type_="check")
        batch.drop_column("confidence")
        batch.create_check_constraint(
            "ck_study_reviews_rating",
            "rating IN ('again', 'hard', 'good', 'easy')",
        )
