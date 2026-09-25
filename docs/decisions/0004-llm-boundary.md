# ADR 0004: Provider-adapted LLM services with strict structured outputs

- Status: Accepted at Human Gate 0
- Date: 2026-08-20

## Decision

Create explicit backend services for interviewing, grading, misconception detection, hint generation, and post-interview evaluation. Define versioned Pydantic output schemas and prompt metadata. Keep a narrow provider adapter so model selection can change without changing product routes or stored domain events.

Use OpenAI as the initial backend provider. Select the exact model through the Milestone 4 evaluation harness, not by intuition. Store provider, model snapshot/alias, prompt version, schema version, latency, token use, and validation outcome for every material result.

## Guardrails

- Deterministic code tests remain the source of truth for correctness.
- Invalid or contradictory structured output fails closed into a recoverable state.
- User text, code, and problem content are untrusted prompt inputs.
- Send only the minimum bounded event context; never send hidden test bodies or credentials.
- Do not permit provider content training without explicit user permission and compatible vendor terms.

## Implementation note (2026-09-24)

- `LLM_PROVIDER=offline` is the default: a deterministic policy interviewer, rubric grader, and
  rule-based evaluator. The same code paths are the fallback when the provider fails, so the
  product works without a key and nothing leaves the machine by default.
- `LLM_PROVIDER=openai` uses Chat Completions with `response_format: json_schema` (`strict: true`)
  generated from Pydantic models (`app/llm/provider.py`), per-request auth, bounded retries with
  backoff for 429/5xx/timeouts, and schema-error feedback for malformed output. Exhausted retries
  raise `LLMUnavailable`; callers fall back and record `llm_fallback` events.
- The model is configurable (`OPENAI_MODEL`, default `gpt-4.1-mini` as a placeholder). **No model
  has been selected through the evaluation harness yet**; that remains a Gate 4/5 task.
- Every call is audited in `llm_calls` (task, provider, model, prompt id `<task>/<version>+<sha8>`,
  schema version, status, error code, latency, tokens, attempts), without content.
- Prompts live in `packages/prompts/`; untrusted content is fenced; hidden tests and reference
  solutions are never included. A deterministic guard filters every interviewer message.
