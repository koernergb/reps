"""Provider adapter for structured LLM outputs.

Product logic never parses prose: every call names a Pydantic schema, the provider requests a
strict JSON-schema response, and the result is validated before use. Invalid output is retried
with the validation error; exhausted retries raise `LLMUnavailable` so callers fail closed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    def __init__(self, code: str, message: str, attempts: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.attempts = attempts


@dataclass(frozen=True)
class LLMResult[R: BaseModel]:
    value: R
    provider: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    attempts: int


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, *, system: str, user: str, schema: type[T]) -> LLMResult[T]: ...


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Convert a Pydantic schema to the subset accepted by strict structured outputs."""

    def visit(node: Any) -> Any:
        if isinstance(node, dict):
            node = {
                key: visit(value)
                for key, value in node.items()
                if key
                not in {
                    "default",
                    "title",
                    "examples",
                    "format",
                    "minLength",
                    "maxLength",
                    "minimum",
                    "maximum",
                    "minItems",
                    "maxItems",
                    "pattern",
                }
            }
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            return node
        if isinstance(node, list):
            return [visit(item) for item in node]
        return node

    return visit(model.model_json_schema())  # type: ignore[no-any-return]


class OpenAIProvider:
    name = "openai"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.openai_api_key:
            raise ValueError("OpenAI provider requires OPENAI_API_KEY")
        self.model = settings.openai_model
        self.max_retries = settings.llm_max_retries
        self._headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        self._client = client or httpx.Client(
            base_url=settings.openai_base_url, timeout=settings.llm_timeout_s
        )

    def generate(self, *, system: str, user: str, schema: type[T]) -> LLMResult[T]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        started = time.perf_counter()
        input_tokens = output_tokens = 0
        last_code = "unknown"
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self._client.post(
                    "/chat/completions",
                    headers=self._headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.2,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema.__name__,
                                "schema": strict_json_schema(schema),
                                "strict": True,
                            },
                        },
                    },
                )
            except httpx.TimeoutException:
                last_code = "timeout"
                continue
            except httpx.HTTPError:
                last_code = "network_error"
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_code = "rate_limited" if response.status_code == 429 else "provider_error"
                time.sleep(min(2.0, 0.25 * 2**attempt))
                continue
            if response.status_code >= 400:
                raise LLMUnavailable(
                    "provider_rejected", "The model provider rejected the request."
                )
            body = response.json()
            usage = body.get("usage") or {}
            input_tokens += int(usage.get("prompt_tokens", 0))
            output_tokens += int(usage.get("completion_tokens", 0))
            message = body["choices"][0]["message"]
            if message.get("refusal"):
                last_code = "refusal"
                continue
            try:
                value = schema.model_validate(json.loads(message.get("content") or ""))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_code = "malformed_output"
                messages = [
                    *messages[:2],
                    {"role": "assistant", "content": str(message.get("content"))[:4000]},
                    {
                        "role": "user",
                        "content": "That response did not match the required schema: "
                        f"{str(exc)[:800]}. Return only corrected JSON.",
                    },
                ]
                continue
            return LLMResult(
                value=value,
                provider=self.name,
                model=str(body.get("model", self.model)),
                latency_ms=round((time.perf_counter() - started) * 1000),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                attempts=attempt,
            )
        raise LLMUnavailable(
            last_code, "The model did not return a usable response.", attempts=self.max_retries + 1
        )


def build_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the configured provider, or None for deterministic offline policies."""
    settings = settings or get_settings()
    if settings.llm_provider == "openai":
        return OpenAIProvider(settings)
    return None
