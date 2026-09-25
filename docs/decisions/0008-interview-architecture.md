# ADR 0008: Application-owned interview state with an event stream

- Status: Accepted (implemented 2026-09-24; Human Gate 4 pending)

## Decision

Interview state lives in `interview_sessions` and changes only through
`state_machine.validate_transition`. The model may recommend a transition; the server applies it
only when it is valid for the current state and trigger. Every meaningful action is a versioned
event (`app/interview/events.py`) with a database-allocated sequence number
(`UPDATE … RETURNING event_count`), server timestamp, actor, optional client timestamp
(informational only), and optional idempotency key (unique per session).

Learner mutations carry `expected_version`; a conditional `UPDATE … WHERE version = :expected`
rejects stale or out-of-order requests with 409, and a repeated idempotency key returns the
current view without side effects. Execution results arrive via a worker hook, which appends
events and may apply the deterministic transition "passing submission → complexity".

Mock sessions snapshot their policy and deadline at creation; expiry is enforced lazily on the next
request and triggers evaluation.

## Consequences

- `app/interview/replay.py` reconstructs state, hints, code, and result from events alone
  (tested). Transcripts are derived views, not the source of truth.
- The LLM call happens inside the request transaction; acceptable for one local user, but a hosted
  version should move model calls outside the row lock or to a job.
