# Human Gate 2 — Content accuracy and fairness review

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**
- Consequence: every problem and exercise remains `status: development`. The app labels this
  content "Unreviewed" and the owner accepts using it for personal practice only.

## Automated evidence available

- `pnpm corpus:validate` — schema, lint, and execution of every reference solution against
  visible, hidden, and example tests (run twice for determinism); every known-wrong solution
  is rejected by hidden tests for its declared reason.
- `pnpm corpus:report` — 32 problems, 62 exercises, all 64 capabilities covered.
- Known gap: ten transfer groups have a single member; transfer selection falls back to
  `related` problems and same-topic transfer-role problems.

## Required human validation (still outstanding)

1. An experienced interviewer reviews, per problem: statement clarity, clarification answers,
   reference solution, stated complexity, hidden tests, capability weights, transfer links,
   and hint ladder (levels 1–2 must not give the approach away).
2. A second person solves a representative sample (at least one per pattern) without seeing
   internal metadata; record ambiguity and multiple-valid-answer issues.
3. Record per-problem corrections and sign-off below, then flip `status` to `reviewed`.

| Problem | Reviewer | Corrections | Status |
| --- | --- | --- | --- |
| (all 32) | — | — | development |
