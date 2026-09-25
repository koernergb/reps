# Metrics and analytics definitions

## Learning outcomes (`GET /v1/learner/metrics`)

Descriptive per-learner numbers. They are not causal claims; do not optimize for them until the
definitions have been reviewed with real data (Milestone 11 rule).

| Metric | Definition | Denominator / notes |
| --- | --- | --- |
| `activated` | At least one interview has an evaluation | — |
| `week_2_retained` | Any analytics event in days 7–13 after the first event | Only meaningful ≥ 14 days after first activity |
| `sessions_per_week` | Interviews started + review attempts started, per ISO week | Calendar weeks in UTC |
| `hints_per_problem` | Mean `hints_used` over evaluated interviews | Evaluated interviews |
| `median_seconds_to_first_approach` | Interview start → first `approach_proposed`/`approach_changed` event | Interviews where an approach was stated |
| `failed_submissions_per_interview` | Submissions minus one if solved | Evaluated interviews |
| `retest_return_rate` | Completed / due remediation tasks (interview, solution-view, retry sources) | Tasks whose due time has passed |
| `transfer_success_after_remediation` | Completed transfer/re-interview tasks with correctness ≥ 0.8 and ≤ 1 hint | Completed transfer/re-interview tasks |

## Product analytics events (`analytics_events`)

Allowlisted in `apps/api/app/analytics.py`; unknown events or properties raise errors. String
properties must be short tokens; keys resembling code/transcript/answer/content/email/prompt/
hidden/secret/token/message/text are rejected.

| Event | Properties |
| --- | --- |
| `interview_started` | `mode`, `difficulty`, `from_task` |
| `interview_completed` | `mode`, `result`, `duration_s` |
| `interview_evaluated` | `mode`, `result`, `hints_used`, `weakness_count`, `evaluator`, `status` |
| `hint_given` | `level`, `mode`, `surface` |
| `execution_requested` | `kind`, `surface` |
| `remediation_scheduled` | `tasks`, `source` |
| `review_completed` | `task_type`, `score_band`, `hints_used`, `latency_s`, `recommended_action`, `from_drill` |
| `review_snoozed` / `review_skipped` / `exercise_reported` | `task_type` (`days` for snooze) |
| `drill_started` | `budget_minutes`, `items`, `planned_minutes` |
| `drill_completed` | `items`, `completed`, `planned_minutes`, `actual_minutes` |
| `drill_abandoned` | `items`, `completed`, `abandon_index` |
| `solution_viewed` | `surface` |
| `diagnosis_flagged` | `has_capability` |
| `state_rebuilt` | `capabilities` |

## Operational metrics

See `docs/operations.md` (`/v1/system/metrics`). LLM cost per completed interview can be computed
from `llm_calls` token totals × provider pricing; tokens are recorded per call.
