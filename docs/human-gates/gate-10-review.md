# Human Gate 10 — Remediation validity check (solution viewing)

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**

What exists: a consent dialog before any reveal (API requires `confirm: true`), `solution_views`
provenance without altering the failed attempt, an immediate key-insight check, pseudocode +1 day,
implementation +3, related problem +10, unseen transfer +21; later same-problem success is
`repeat_exposure`/`assisted` evidence and cannot yield Strong transfer; progress shown as stages
instead of a "solved" badge.

Evidence: `tests/test_solutions_analytics.py`, `tests/test_learner_model.py`
(`test_assisted_evidence_cannot_establish_transfer`), and the solution-viewer history in
`gate-6-histories.md`.

Required (multi-day by design): learners who recently failed use the flow, then complete the
delayed reconstruction and transfer at the intended intervals; the product owner reviews all
status language for "solved" incentives.
