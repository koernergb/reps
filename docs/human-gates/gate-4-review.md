# Human Gate 4 — Interview behavior validation

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**
- What was built: application-owned state machine, versioned events with replay, practice hint
  ladder, output guard, OpenAI adapter (strict structured outputs) with an offline policy
  interviewer as default and fallback.

## Automated evidence

- `pnpm --filter @reps/api personas` (also in CI): 9 scripted personas pass with the offline
  interviewer — perfect, needs hint, wrong complexity, memorized, boundary bug, silent then
  correct, bad reasoning/correct code, good reasoning/buggy code, and prompt injection. Checks:
  expected result and weaknesses, zero leaked messages, zero unsolicited hints.
- `tests/test_state_machine.py`: every valid transition, every invalid/terminal/no-op one.
- `tests/test_interviews.py`: stale version (409), duplicate requests (idempotent), invalid
  transitions without side effects, replay equals stored state, LLM timeout/malformed/rate-limit
  fallback, leaking LLM output blocked, invalid LLM transitions ignored, cross-user denial.
- `tests/test_guard.py`: code dumps, reference overlap, hidden inputs (format-insensitive), prompt
  disclosure, key-insight reveal.
- Playwright: full practice interview including a mid-interview reload.

## Not yet validated

- **No LLM-backed run has happened** (no API key configured). The OpenAI path is tested only
  against a mocked transport. Run `LLM_PROVIDER=openai OPENAI_API_KEY=… python -m
  app.interview.personas --report personas.json` and review the transcripts.
- The offline interviewer is intentionally simple; it probes and answers corpus clarifications
  but does not understand arbitrary reasoning.

## Required human validation

Run the 8 personas plus 3 live interviews with the LLM enabled; have experienced interviewers
score solution leakage, unnecessary hints, clarification quality, patience, state correctness,
communication assessment, and realism. Any leakage or broken transition is a blocker.
