from typing import Any, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings as get_app_settings
from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.llm import runtime
from app.llm.provider import LLMUnavailable, make_provider

router = APIRouter(prefix="/v1/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    daily_review_cap: int | None = Field(default=None, ge=1, le=50)
    mock_time_multiplier: float | None = Field(default=None, ge=1.0, le=2.0)
    reduce_timer_motion: bool | None = None


def view(user: Any) -> dict[str, Any]:
    preferences = user.preferences or {}
    return {
        "timezone": user.timezone,
        "daily_review_cap": user.daily_review_cap,
        "mock_time_multiplier": preferences.get("mock_time_multiplier", 1.0),
        "reduce_timer_motion": preferences.get("reduce_timer_motion", False),
    }


@router.get("")
def get_settings_view(user: UserDependency) -> dict[str, Any]:
    return view(user)


@router.patch("")
def update(body: SettingsUpdate, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    if body.timezone is not None:
        if body.timezone not in available_timezones():
            raise ApiError(422, "invalid_timezone", "Choose a valid IANA timezone.")
        user.timezone = body.timezone
    if body.daily_review_cap is not None:
        user.daily_review_cap = body.daily_review_cap
    preferences = dict(user.preferences or {})
    if body.mock_time_multiplier is not None:
        preferences["mock_time_multiplier"] = body.mock_time_multiplier
    if body.reduce_timer_motion is not None:
        preferences["reduce_timer_motion"] = body.reduce_timer_motion
    user.preferences = preferences
    db.commit()
    return view(user)


# --- AI provider ---------------------------------------------------------------------------

ProviderName = Literal["openai", "gemini"]
LABELS = {"openai": "an OpenAI", "gemini": "a Gemini"}


class CredentialUpdate(BaseModel):
    api_key: str | None = Field(default=None, max_length=500)
    clear_key: bool = False
    model: str | None = Field(default=None, max_length=120)


class LLMSettingsUpdate(BaseModel):
    active: Literal["env", "offline", "openai", "gemini"] | None = None
    openai: CredentialUpdate | None = None
    gemini: CredentialUpdate | None = None


class TestRequest(BaseModel):
    provider: ProviderName


class ConnectionCheck(BaseModel):
    ok: bool


def key_hint(key: str | None) -> str | None:
    return f"…{key[-4:]}" if key and len(key) >= 8 else ("set" if key else None)


def llm_view(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    settings = get_app_settings()
    stored = runtime.credentials(db, user.id)
    env_keys = {"openai": settings.openai_api_key, "gemini": settings.gemini_api_key}
    env_models = {"openai": settings.openai_model, "gemini": settings.gemini_model}
    active = runtime.active_choice(user)
    effective = settings.llm_provider if active == "env" else active
    providers = {}
    for name in runtime.PROVIDERS:
        row = stored.get(name)
        providers[name] = {
            "has_key": bool(row and row.api_key),
            "key_hint": key_hint(row.api_key if row else None),
            "model": (row.model if row else None) or env_models[name],
            "env_key_present": bool(env_keys[name]),
        }
    return {
        "active": active,
        "effective": effective,
        "env_provider": settings.llm_provider,
        "providers": providers,
        "storage_note": "Keys are stored in your local database, never shown again after "
        "saving, never logged, and excluded from exports.",
    }


@router.get("/llm")
def get_llm_settings(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    return llm_view(db, user)


@router.put("/llm")
def update_llm_settings(
    body: LLMSettingsUpdate, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    for name in runtime.PROVIDERS:
        update: CredentialUpdate | None = getattr(body, name)
        if update is not None:
            runtime.save_credential(
                db,
                user.id,
                name,
                api_key=update.api_key,
                model=update.model,
                clear_key=update.clear_key,
            )
    db.flush()
    if body.active is not None:
        if body.active in runtime.PROVIDERS:
            row = runtime.credentials(db, user.id).get(body.active)
            if not (row and row.api_key):
                db.rollback()
                raise ApiError(
                    422,
                    "api_key_required",
                    f"Add {LABELS[body.active]} API key before selecting it.",
                )
        user.preferences = {**(user.preferences or {}), "llm_provider": body.active}
    db.commit()
    runtime.refresh(db, user.id)
    return llm_view(db, user)


def saved_provider(db: SessionDependency, user_id: str, provider: str) -> Any:
    row = runtime.credentials(db, user_id).get(provider)
    if not (row and row.api_key):
        raise ApiError(422, "api_key_required", f"Save {LABELS[provider]} API key first.")
    return make_provider(provider, row.api_key, row.model)


@router.get("/llm/{provider}/models")
def list_llm_models(
    provider: ProviderName, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    client = saved_provider(db, user.id, provider)
    try:
        models = client.list_models()
    except LLMUnavailable as exc:
        raise ApiError(502, exc.code, f"Could not list models: {exc}") from exc
    if provider == "openai":
        models = [item for item in models if item.startswith(("gpt-", "o", "chatgpt"))]
    else:
        models = [item for item in models if item.startswith("gemini")]
    return {"provider": provider, "models": models}


@router.post("/llm/test")
def test_llm(body: TestRequest, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    """Send one tiny structured request with the saved key and model."""
    client = saved_provider(db, user.id, body.provider)
    try:
        result = client.generate(
            system="You are a connectivity check. Reply with JSON only.",
            user='Return {"ok": true}.',
            schema=ConnectionCheck,
        )
    except LLMUnavailable as exc:
        return {"ok": False, "model": client.model, "error_code": exc.code, "message": str(exc)}
    return {
        "ok": result.value.ok,
        "model": result.model,
        "latency_ms": result.latency_ms,
        "error_code": None,
        "message": "Structured output works with this provider and model.",
    }
