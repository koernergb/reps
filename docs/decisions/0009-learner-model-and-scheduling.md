# ADR 0009: Conservative, explainable learner model and scheduler

- Status: Accepted for MVP (implemented 2026-09-24; Human Gates 6 and 7 pending)

## Decision

Use an explicit, bounded exponential-update model per capability with separate evidence types
(recall through transfer), hint/assisted/repeat/transfer weighting, and interval growth scaled by
elapsed time. Store evidence append-only and recompute aggregates from it. Show only bands and
plain-language explanations. Schedule remediation from severity templates with local-calendar due
dates, a daily cap, and database-enforced dedupe. No FSRS/BKT/IRT until Milestone 12 authorizes
it. Details and constants: `docs/learning-model.md`.

## Consequences

Every number is reproducible from evidence and can be audited (`gate-6-histories.md`). The model
is deliberately simple and needs calibration against real learner data before it is trusted for
anything beyond ordering practice.
