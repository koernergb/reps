from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import LLMCall


def record_call(
    session: Session,
    *,
    user_id: str,
    session_id: str | None,
    task: str,
    provider: str,
    model: str,
    prompt_version: str,
    schema_version: int,
    status: str,
    latency_ms: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    attempts: int = 1,
    error_code: str | None = None,
) -> None:
    session.add(
        LLMCall(
            user_id=user_id,
            session_id=session_id,
            task=task,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            schema_version=schema_version,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            attempts=attempts,
            error_code=error_code,
            created_at=datetime.now(UTC),
        )
    )
