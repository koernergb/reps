# Human Gate 11 — Private-beta release review

- Status: **NOT PERFORMED; also out of scope.** Local-first scope (Gate 0) defers hosting, auth,
  and multi-user operation. Nothing here authorizes a beta.

Packet (local equivalents):

| Item | Where |
| --- | --- |
| End-to-end demo | Playwright suite (`pnpm --filter @reps/web e2e`), `make dev` |
| Threat model and sandbox review | `docs/threat-model.md`, ADR 0005, `gate-3-review.md` |
| Evaluation calibration | `gate-5-review.md` (not performed) |
| Corpus review coverage | `gate-2-review.md` (0 of 32 reviewed) |
| Accessibility and usability | `gate-8-review.md` (not performed) |
| Load baseline and cost | `gate-3-review.md` (sandbox), `docs/cost-envelope.md`, `llm_calls` tokens |
| Backup/restore evidence | `scripts/verify-restore.sh` (22 tables matched on 2026-09-24) |
| Data flow, retention, deletion | `/privacy`, ADR 0006, ownership test in `tests/test_local_data.py` |
| Dashboards, alerts, runbooks | `docs/operations.md` (`/v1/system/metrics`, no alerting locally) |
| Feature flags and rollback | `docs/operations.md`, reversible migrations |

Blocking gaps before any beta: authentication/authorization, hosted sandbox + new Gate 3, human
Gates 2 and 4–10, load/soak/chaos testing at beta concurrency, alerting, retention and consent
decisions.
