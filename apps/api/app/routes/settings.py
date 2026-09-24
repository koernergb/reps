from typing import Any
from zoneinfo import available_timezones

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.deps import SessionDependency, UserDependency
from app.errors import ApiError

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
