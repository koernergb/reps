from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://reps:reps-local-only@localhost:5432/reps",
        min_length=1,
    )
    web_origin: str = "http://localhost:3000"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)

    # Code execution (Milestone 3). Learner code only ever runs in the Docker sandbox.
    execution_enabled: bool = True
    execution_backend: Literal["docker", "trusted-subprocess"] = "docker"
    sandbox_image: str = "reps-sandbox:dev"
    sandbox_memory_mb: int = Field(default=256, ge=64, le=2048)
    sandbox_cpus: float = Field(default=1.0, gt=0, le=4)
    sandbox_pids: int = Field(default=64, ge=8, le=512)
    execution_rate_per_minute: int = Field(default=30, ge=1, le=600)
    execution_max_queued_per_user: int = Field(default=10, ge=1, le=100)
    execution_job_ttl_s: int = Field(default=90, ge=10, le=3600)
    worker_concurrency: int = Field(default=2, ge=1, le=16)

    # Feature flags (Milestone 11). All default on for the local single-user tool.
    feature_interviews: bool = True
    feature_semantic_evaluation: bool = True
    feature_scheduling: bool = True
    feature_drills: bool = True
    feature_mock_mode: bool = True
    feature_solution_viewing: bool = True
    allow_unreviewed_content: bool = True

    # LLM provider (Milestone 4+). Without a key, deterministic offline policies are used.
    llm_provider: Literal["openai", "gemini", "offline"] = "offline"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_timeout_s: float = Field(default=30, gt=0, le=120)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    @model_validator(mode="after")
    def validate_combinations(self) -> "Settings":
        if self.execution_backend == "trusted-subprocess" and self.environment != "test":
            raise ValueError(
                "EXECUTION_BACKEND=trusted-subprocess is only permitted when ENVIRONMENT=test; "
                "learner code must run in the Docker sandbox."
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("LLM_PROVIDER=gemini requires GEMINI_API_KEY.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
