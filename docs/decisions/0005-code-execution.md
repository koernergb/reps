# ADR 0005: Externally isolated Python execution

- Status: Accepted for local-first scope (2026-09-24); hosted topology still requires Human Gate 3
- Date: 2026-08-20, updated 2026-09-24

## Decision (local scope)

Learner code runs only in an ephemeral Docker container per job, started by a separate
execution worker process (`app.worker`). The API records immutable jobs in PostgreSQL and
never executes learner code. The browser never talks to the sandbox.

Per-job container flags (see `apps/api/app/execution/backends.py`):

| Control | Value |
| --- | --- |
| Network | `--network none` |
| Filesystem | `--read-only`; `/tmp` tmpfs 16 MB, `noexec,nosuid,nodev` |
| Identity | `--user 65534:65534`, `--cap-drop ALL`, `--security-opt no-new-privileges` |
| Memory | 256 MB hard (`--memory` = `--memory-swap`); child `RLIMIT_AS` 208 MB |
| CPU | `--cpus 1` |
| Processes | `--pids-limit 64`; child `RLIMIT_NPROC` 16 |
| Files | `--ulimit nofile=64`, `fsize=1 MB`; no host mounts |
| Time | per-test timer (default 2 s, max 5 s) + supervisor deadline + container wall timeout |
| Output | per-test stdout 4 KB returned; 256 KB hard stop; 4 MB total harness output |
| Other | `--ipc none`, `--log-driver none`, image env scrubbed in the learner child |

Harness design (`infra/sandbox/harness/runner.py`): a non-dumpable supervisor forks the learner
child, which redirects fds 0–2 to `/dev/null`, clears its environment, and streams one result
per test over a private pipe. **Expected outputs never enter the sandbox**; the worker compares
returned values outside it. Hidden-test inputs necessarily enter; hidden results are reported to
the learner only as aggregate counts by failure category.

Image: `python:3.12.11-slim-bookworm`, standard library only, pip removed. Build with
`make sandbox-build`.

## Residual risks (accepted for single-user local use)

- Docker Desktop's VM and default seccomp profile are the kernel boundary; this is weaker than
  gVisor/Firecracker microVMs and is **not** approved for untrusted multi-user traffic.
- Pass/fail counts over hidden tests are a low-bandwidth side channel for probing hidden inputs.
- Timing is shared-host dependent; performance tests keep at least a 5x margin.

## Before any hosted or shared use

Re-run Human Gate 3 on the actual target topology. Compare E2B, Modal sandboxes, and a
self-managed gVisor/Firecracker worker plane for isolation evidence, regions, cold start,
limits, observability, deletion, and cost.
