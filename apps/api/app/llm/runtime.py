"""Load and persist the AI provider selection made in Settings."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.llm.provider import ProviderChoice, set_runtime_choice
from app.models import LLMCredential, User

PROVIDERS = ("openai", "gemini")
CHOICES = ("env", "offline", *PROVIDERS)


def credentials(db: Session, user_id: str) -> dict[str, LLMCredential]:
    rows = db.scalars(select(LLMCredential).where(LLMCredential.user_id == user_id))
    return {row.provider: row for row in rows}


def active_choice(user: User) -> str:
    choice = (user.preferences or {}).get("llm_provider", "env")
    return choice if choice in CHOICES else "env"


def refresh(db: Session, user_id: str) -> ProviderChoice | None:
    """Recompute the in-process provider choice from the database."""
    try:
        user = db.get(User, user_id)
        if user is None:
            set_runtime_choice(None)
            return None
        choice = active_choice(user)
        stored = credentials(db, user_id).get(choice)
        selection = ProviderChoice(
            provider=choice,
            api_key=stored.api_key if stored else None,
            model=stored.model if stored else None,
        )
    except SQLAlchemyError:
        # Before migrations run there is nothing to load; `.env` stays in charge.
        db.rollback()
        selection = None
    set_runtime_choice(selection)
    return selection


def save_credential(
    db: Session,
    user_id: str,
    provider: str,
    *,
    api_key: str | None,
    model: str | None,
    clear_key: bool,
) -> LLMCredential:
    row = db.get(LLMCredential, (user_id, provider))
    if row is None:
        row = LLMCredential(user_id=user_id, provider=provider, updated_at=datetime.now(UTC))
        db.add(row)
    if clear_key:
        row.api_key = None
    elif api_key:
        row.api_key = api_key.strip()
    if model is not None:
        row.model = model.strip() or None
    row.updated_at = datetime.now(UTC)
    return row
