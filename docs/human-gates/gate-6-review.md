# Human Gate 6 — Learning-science and UX sanity check

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**
- Artifact: `gate-6-histories.md` (regenerate with `python -m app.learning.history_report`).
- Policy: `docs/learning-model.md`.

## Finding already fixed during preparation

The first version of this report showed the review interval growing from 2 to 60 days after
five daily repeats of the same problem. Interval growth is now scaled by elapsed time and capped
for repeat exposure (the report now shows 2 → 2.8 days). This is the kind of issue the gate is
for.

## Automated evidence

`tests/test_learner_model.py`: table-driven cases, property tests (bounds, determinism, single-step
cap, monotonicity), duplicate delivery, rebuild equality, assisted-transfer cap.

## Required human validation

A learning-science reviewer and the product owner walk through the five histories, judge whether
bands, wording, and next-review implications are defensible, and flag surprising jumps,
repeated-problem overconfidence, or transfer inflation.
