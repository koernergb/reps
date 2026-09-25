# Human Gate 5 — Evaluation calibration

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**

## What exists

Deterministic facts (result, hidden pass counts, runs/submits, hints, complexity check, solution
viewing) come only from sandbox results and events. Semantic interpretation comes from the LLM
(when configured) or rules, and every claim must cite event ids. Validation drops claims with
missing evidence, unknown capabilities, or contradictions with execution. Reports store
evaluator, model, prompt version (with content hash), schema version, event range, latency,
attempts, and fallback. Degraded mode keeps facts and rule-based interpretation and offers a retry.
Learners can flag inaccurate diagnoses; flagged evidence is excluded and aggregates recomputed.

## Automated evidence

`tests/test_evaluation.py`: deterministic result table, validation of unsupported and
contradictory claims, merge rules, metamorphic wording test, never contradicting passing
execution, LLM provenance, degraded mode, flagging. Personas check capability extraction.

## Metrics available

`/v1/system/metrics` → `evaluation.degraded_rate`, `failure_rate`, `unsupported_claims_dropped`,
`p95_ms`; `llm` → per-task error rate, latency, tokens (cost).

## Required human validation

Agree thresholds (capability precision/recall, severity agreement, false positives, unsupported
claims, usefulness), have two reviewers label a blinded set, adjudicate, and compare with model
output (LLM path) and rules output. The product owner approves learner-facing wording.
