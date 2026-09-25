# Human Gate 7 — Schedule and exercise quality validation

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**

## What exists

Deterministic chains per topic (`docs/learning-model.md`), DST-safe local due dates, a daily cap,
active-task dedupe, exercise and unseen-problem selection, Retrieve/Coach/Rebuild flows with
hints, misconception explanation, and a confirmation question; "why this is scheduled" on every
task; snooze/skip/report-broken.

## Automated evidence

`tests/test_scheduler.py` (DST, the brief's sliding-window scenario, dedupe, daily cap, long
absence, failed interview → due review → completed attempt → changed state) and
`tests/test_reviews_drills.py` (text, code, and rebuild flows; snooze/skip/report; user scoping).

## Known limitations

- All 62 exercises are `development` content (Gate 2 not performed).
- The offline grader uses keyword rubrics; paraphrases outside the rubric can be under-credited.
  The LLM grader (when enabled) interprets against the same rubric.
- Ten transfer groups have a single member; transfer selection falls back to related and
  same-topic problems.

## Required human validation

Learners and an educator complete sequences for at least five failure profiles; review ordering,
ambiguity, workload, hint usefulness, and whether transfer items are related but not duplicates.
