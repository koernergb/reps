"""Allow Groq as an LLM credential provider.

Revision ID: 20261120_0008
Revises: 20261113_0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261120_0008"
down_revision: str | None = "20261113_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_llm_credentials_provider", "llm_credentials", type_="check")
    op.create_check_constraint(
        "ck_llm_credentials_provider",
        "llm_credentials",
        "provider IN ('openai', 'gemini', 'groq')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM llm_credentials WHERE provider = 'groq'")
    op.drop_constraint("ck_llm_credentials_provider", "llm_credentials", type_="check")
    op.create_check_constraint(
        "ck_llm_credentials_provider",
        "llm_credentials",
        "provider IN ('openai', 'gemini')",
    )
