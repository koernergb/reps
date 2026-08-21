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
