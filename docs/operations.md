# Operations (local-first)

Reps runs on one machine for one owner. This document covers what exists to observe, control,
and recover it. Hosted operation needs the additional work listed at the end.

## Processes

| Process | Command | Notes |
| --- | --- | --- |
| Web | `pnpm dev:web` | Next.js on `:3000` |
| API | `pnpm --filter @reps/api dev:api-only` | FastAPI on `API_PORT` (default 8000); never runs learner code |
| Execution worker | `pnpm dev:worker` | Claims jobs, starts one Docker container per job |
| Both API + worker | `pnpm --filter @reps/api dev` | What `make dev` runs |
| PostgreSQL | `make services-up` | Docker Compose |

## Health and metrics

- `GET /health` liveness; `GET /ready` database readiness (503 when unavailable).
- `GET /v1/system/status` feature flags, execution backend, sandbox image presence, LLM provider.
- `GET /v1/system/metrics` content-free metrics: request p50/p95/error rate per route (last hour),
  execution jobs by status/verdict with p95 duration, LLM calls by task (error rate, p95, tokens,
  error codes), evaluation degraded/failure rates and dropped unsupported claims, task/drill counts,
  and SLO evaluation.
- `GET /v1/system/diagnostics` recent job and model-call states by id (no code or content) and
  worker liveness (`last_finished_at`).
- Logs are structured JSON with `request_id`. They never include code, transcripts, prompts,
  hidden tests, or keys.

## Service-level objectives (local targets)

| Journey | Objective |
| --- | --- |
| Session start/resume (`POST /v1/interviews`, `GET /v1/interviews/{id}`) | p95 < 1.5 s, errors < 1 % |
| Interview response (`POST …/messages`) | p95 < 8 s (LLM) , errors < 2 % |
| Code execution (queued → finished) | p95 < 10 s, infrastructure failures < 2 % |
| Evaluation availability | degraded < 10 %, failed < 1 % |
| Queue / drill generation | p95 < 1.5 s, errors < 1 % |

`/v1/system/metrics` reports `met: true/false` per objective. Local mode has no paging; hosted
mode must alert on these.

## Kill switches and feature flags (`.env`, restart to apply)

| Variable | Effect |
| --- | --- |
| `EXECUTION_ENABLED=false` | New executions rejected with 503; queued jobs expire |
| `LLM_PROVIDER=offline` | No data leaves the machine; deterministic interviewer/grader/evaluator |
| `FEATURE_INTERVIEWS`, `FEATURE_MOCK_MODE`, `FEATURE_DRILLS`, `FEATURE_SCHEDULING`, `FEATURE_SEMANTIC_EVALUATION`, `FEATURE_SOLUTION_VIEWING` | Disable each surface; APIs return 503 with an actionable message |
| `ALLOW_UNREVIEWED_CONTENT=false` | Only Gate-2-reviewed problems can be interviewed |

## Rate limits (per learner, in-process)

Executions 30/min and 10 in flight; interview messages 30/min; exports 10/min; resets 5/min.

## Runbooks

**AI provider outage or rate limiting.** Interviews continue: each failed call is retried
(`LLM_MAX_RETRIES`) and then falls back to the policy interviewer with an `llm_fallback` event.
Evaluations become `degraded` (rule-based) and can be retried from the report page. To stop
calling the provider entirely, set `LLM_PROVIDER=offline`.

**Sandbox outage** (`sandbox_ready: false`, jobs `failed` with "sandbox is unavailable"). Start
Docker Desktop, run `make sandbox-build`, and retry; no verdict is recorded for failed jobs.

**Stuck jobs.** Restart the worker; on start it marks `running` jobs as failed ("interrupted")
and queued jobs past `EXECUTION_JOB_TTL_S` expire. Check `/v1/system/diagnostics`.

**Migration rollback.** `scripts/backup-db.sh`, then `pnpm db:downgrade` (one revision). Every
migration is reversible; `20260924_0004` deletes problem-level review attempts on downgrade
because the old schema cannot hold them (documented in the migration).

**Backup and restore.** `scripts/backup-db.sh` writes `backups/reps-<UTC>.dump` (mode 600;
contains learner content). `scripts/verify-restore.sh` restores the newest backup into
`reps_restore_check` and compares per-table row counts (last rehearsal: 22 tables matched).
Restore over the live DB only with `scripts/restore-db.sh <dump> reps --yes` after stopping
`make dev`.

**Key rotation.** `OPENAI_API_KEY` lives only in `.env`, is sent only in the Authorization
header, and is never logged or stored. Rotate it at the provider, update `.env`, restart.

**Deletion propagation.** "Reset history" deletes every learner-owned table (enforced by a
test that fails when a new table with `user_id` is not registered). Logs and analytics carry no
content. Backups in `backups/` still contain history: delete them manually. Provider-side
retention for past OpenAI calls follows OpenAI's API data policy.

## Before hosted or shared use (not done)

Authentication and per-user authorization; hosted sandbox (gVisor/Firecracker or a provider) and
a new Gate 3; managed Postgres with automated encrypted backups and expiry; secrets manager;
central metrics/alerts/tracing; distributed rate limits; retention windows and consent flows;
support-access auditing; load and soak tests at beta concurrency.
