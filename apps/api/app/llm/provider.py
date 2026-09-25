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


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace `$ref` pointers with their definitions (for providers without `$defs` support)."""
    definitions = schema.get("$defs", {})

    def visit(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return visit(definitions[node["$ref"].rsplit("/", 1)[-1]])
            return {key: visit(value) for key, value in node.items() if key != "$defs"}
        if isinstance(node, list):
            return [visit(item) for item in node]
        return node

    return visit(schema)  # type: ignore[no-any-return]


def gemini_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Gemini's OpenAI-compatible endpoint accepts a narrower schema dialect: no `$defs`, and
    `additionalProperties` is not supported. Responses are still validated with Pydantic."""

    def strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {
                key: strip(value) for key, value in node.items() if key != "additionalProperties"
            }
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    return strip(inline_refs(strict_json_schema(model)))  # type: ignore[no-any-return]


def _parse_json(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def _provider_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        detail = body[0] if isinstance(body, list) else body
        message = (detail.get("error") or {}).get("message") or ""
    except (ValueError, AttributeError, IndexError):
        message = ""
    return f"{response.status_code}: {message[:300]}" if message else str(response.status_code)


class OpenAICompatibleProvider:
    """Chat Completions with JSON-schema structured output (OpenAI and compatible APIs)."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float = 30,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError(f"{self.name} provider requires an API key")
        self.model = model
        self.max_retries = max_retries
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_s)

    def response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": strict_json_schema(schema),
                "strict": True,
            },
        }

    def list_models(self) -> list[str]:
        try:
            response = self._client.get("/models", headers=self._headers)
        except httpx.HTTPError as exc:
            raise LLMUnavailable("network_error", "Could not reach the provider.") from exc
        if response.status_code >= 400:
            raise LLMUnavailable("provider_rejected", _provider_error(response))
        ids = [str(item.get("id", "")) for item in response.json().get("data", [])]
        return sorted({item.removeprefix("models/") for item in ids if item})

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
                        "response_format": self.response_format(schema),
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
                raise LLMUnavailable("provider_rejected", _provider_error(response))
            body = response.json()
            usage = body.get("usage") or {}
            input_tokens += int(usage.get("prompt_tokens", 0))
            output_tokens += int(usage.get("completion_tokens", 0))
            message = body["choices"][0]["message"]
            if message.get("refusal"):
                last_code = "refusal"
                continue
            try:
                value = schema.model_validate(_parse_json(message.get("content") or ""))
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


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini through its OpenAI-compatible endpoint."""

    name = "gemini"

    def response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "schema": gemini_json_schema(schema)},
        }


@dataclass(frozen=True)
class ProviderChoice:
    """Selection made in Settings. `provider="env"` defers to `.env` configuration."""

    provider: str
    api_key: str | None = None
    model: str | None = None


# Set at API startup and whenever Settings change (see app.llm.runtime).
_runtime_choice: ProviderChoice | None = None


def set_runtime_choice(choice: ProviderChoice | None) -> None:
    global _runtime_choice
    _runtime_choice = choice


def make_provider(
    provider: str, api_key: str, model: str | None, settings: Settings | None = None
) -> OpenAICompatibleProvider:
    settings = settings or get_settings()
    common = {"timeout_s": settings.llm_timeout_s, "max_retries": settings.llm_max_retries}
    if provider == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=model or settings.openai_model,
            base_url=settings.openai_base_url,
            **common,  # type: ignore[arg-type]
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=api_key,
            model=model or settings.gemini_model,
            base_url=settings.gemini_base_url,
            **common,  # type: ignore[arg-type]
        )
    raise ValueError(f"unknown provider {provider}")


def build_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the active provider, or None for deterministic offline policies.

    A choice saved in Settings wins; otherwise `.env` (`LLM_PROVIDER`) decides.
    """
    choice = _runtime_choice
    if choice is not None and choice.provider != "env":
        if choice.provider == "offline" or not choice.api_key:
            return None
        return make_provider(choice.provider, choice.api_key, choice.model, settings)
    settings = settings or get_settings()
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return make_provider("openai", settings.openai_api_key, settings.openai_model, settings)
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return make_provider("gemini", settings.gemini_api_key, settings.gemini_model, settings)
    return None
