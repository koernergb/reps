# Human Gate 3 — Sandbox security review

- Status: **NOT PERFORMED — bypassed at the owner's explicit instruction (2026-09-24)**
- Scope of what exists: local single-user Docker sandbox (ADR 0005). Not approved for any
  network-exposed or multi-user deployment.

## Evidence packet

**Threat model:** `docs/threat-model.md` plus ADR 0005 residual risks.

**Limit values:** ADR 0005 table; configurable via `SANDBOX_MEMORY_MB`, `SANDBOX_CPUS`,
`SANDBOX_PIDS`, `EXECUTION_RATE_PER_MINUTE` (30), `EXECUTION_MAX_QUEUED_PER_USER` (10),
`EXECUTION_JOB_TTL_S` (90).

**Adversarial payload set** (`apps/api/tests/test_sandbox_docker.py`, `make sandbox-test`), all
passing on Docker Desktop 29.7 / macOS arm64:

| Payload | Result |
| --- | --- |
| TCP connect to 1.1.1.1, DNS lookup | blocked |
| Write to `/etc`, `/opt/reps/runner.py`, `/usr/local`; 64 MB to `/tmp` | denied / bounded |
| uid and effective capabilities | 65534, `CapEff=0` |
| Env vars containing SECRET/KEY/DATABASE; host paths, docker.sock | none visible |
| Open parent `/proc/<ppid>/fd/1`, `mem`, `environ` (result forging) | denied |
| Fork bomb | contained (pids limit), finishes < 30 s |
| 1 GB allocation | memory limit / error |
| CPU spin, swallowed timeout exceptions | per-test timeout, supervisor kill |
| Infinite print | output limit |
| Hidden expected value in payload bytes | absent |
| Four concurrent jobs sharing `/tmp` | isolated |

Harness unit tests (`tests/test_harness.py`) cover syntax errors, exceptions with learner-only
line numbers, missing entrypoints, forged stdout writes, unserializable returns, adapters,
class-design problems, and source-size limits.

**Load baseline** (`pnpm --filter @reps/api loadtest:sandbox`, pair-sum-indices submit, 7 tests):

| Concurrency | p50 | p95 | Throughput |
| --- | --- | --- | --- |
| 1 | 0.36 s | 0.93 s | 2.1 jobs/s |
| 4 | 0.86 s | 1.23 s | 4.4 jobs/s |
| 8 | 1.45 s | 1.62 s | 5.3 jobs/s |

**Logs:** execution logs record job id, kind, verdict, duration, backend. Source code, hidden
tests, and outputs are never logged.

**Kill switch:** set `EXECUTION_ENABLED=false` in `.env` and restart `make dev`. New jobs return
`503 execution_disabled`; queued jobs expire after `EXECUTION_JOB_TTL_S`. Stopping the worker
alone also halts execution (jobs expire).

## Required human validation (still outstanding)

A security-minded reviewer should inspect the container flags and harness, attempt escape,
exfiltration, DoS, hidden-test extraction, and cross-job access manually, and approve or reject.
Any isolation uncertainty blocks network exposure.
