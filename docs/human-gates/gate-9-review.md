# Human Gate 9 — Realism and bias review (Mock mode)

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**

What exists: a separate snapshotted mock policy (45-minute server-enforced limit, one level-1
nudge, minimal clarifications, no teaching or unsolicited nudges, 10-minute idle threshold); lazy
server-side expiry; a clock offset from `server_now` in the UI; accommodations (1.25–2× time,
calm timer); a versioned scorecard (`scorecard/v1`) whose correctness and independence dimensions
come from facts.

Evidence: `tests/test_state_machine.py` (identical context → different allowed interventions),
`tests/test_interviews.py` (mock hint budget, accommodation, timer expiry → timed-out report with
scorecard), Playwright mock test.

Bias note: the rule-based communication rating counts explanation messages, which could penalize
concise communicators; the LLM prompt instructs judging clarity rather than verbosity or style.
Both need review.

Required: side-by-side Practice/Mock sessions with identical scripts, live mocks, and a review of
strictness, fairness, and accessibility.
