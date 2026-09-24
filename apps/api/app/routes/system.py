import shutil
import subprocess
import time
from typing import Any

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/v1/system", tags=["system"])
_sandbox_cache: dict[str, Any] = {"checked": 0.0, "ready": False}


def sandbox_ready() -> bool:
    settings = get_settings()
    if settings.execution_backend != "docker":
        return settings.environment == "test"
    now = time.monotonic()
    if now - _sandbox_cache["checked"] < 30:
        return bool(_sandbox_cache["ready"])
    docker = shutil.which("docker")
    ready = False
    if docker:
        try:
            ready = (
                subprocess.run(
                    [docker, "image", "inspect", settings.sandbox_image],
                    capture_output=True,
                    timeout=5,
                    check=False,
                ).returncode
                == 0
            )
        except (OSError, subprocess.TimeoutExpired):
            ready = False
    _sandbox_cache.update(checked=now, ready=ready)
    return ready


@router.get("/status")
def system_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "execution": {
            "enabled": settings.execution_enabled,
            "backend": settings.execution_backend,
            "sandbox_ready": sandbox_ready() if settings.execution_enabled else False,
        },
        "llm": {"provider": settings.llm_provider},
        "features": {
            "interviews": settings.feature_interviews,
            "semantic_evaluation": settings.feature_semantic_evaluation,
            "scheduling": settings.feature_scheduling,
            "drills": settings.feature_drills,
            "mock_mode": settings.feature_mock_mode,
            "solution_viewing": settings.feature_solution_viewing,
        },
        "content": {"allow_unreviewed": settings.allow_unreviewed_content},
    }
