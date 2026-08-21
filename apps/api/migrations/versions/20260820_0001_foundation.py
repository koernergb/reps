"""Create foundation migration marker.

Revision ID: 20260820_0001
Revises:
"""

from collections.abc import Sequence

revision: str = "20260820_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish the initial migration boundary before domain tables."""


def downgrade() -> None:
    """Remove the initial migration boundary."""
