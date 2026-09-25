# Foundation threat model

## Assets

- account identity and sessions;
- interview text, submitted code, learning history, and capability state;
- problem reference solutions and hidden tests;
- database, LLM, auth, analytics, and execution credentials;
- service availability and evaluation integrity.

## Trust boundaries

```text
Browser (untrusted input)
  |
  | HTTPS + authenticated requests
  v
Web UI --------> API (authorization, state machine, schemas)
                    |          |             |
                    | TLS      | bounded     | immutable execution job
                    v          v             v
                PostgreSQL   LLM provider   Sandbox control plane
                                               |
                                               v
                                     Ephemeral hostile-code runtime
```

The browser, learner content, model output, and submitted code are untrusted. The API is the authorization and product-state boundary. The sandbox runtime is assumed compromised by each job and must contain that compromise.

## Primary threats and planned controls

| Threat | Foundation control | Required validation |
| --- | --- | --- |
| Cross-user data access | Central API authorization; ownership-scoped queries | Human Gate 1 direct API attempts |
| Session theft/replay | Managed identity, secure cookies/tokens, revocation | Milestone 1 auth tests |
| Prompt injection/data leakage | Bounded context, structured outputs, protected evaluator data | Human Gates 4–5 regression sets |
| False code verdict | Sandbox results are sole correctness source | Milestones 3 and 5 tests |
| Sandbox escape/exfiltration | Separate trust zone, no network/secrets/mounts, strict limits | Human Gate 3 adversarial review |
| Hidden-test extraction | Server-side protected harness, aggregate feedback | Corpus and sandbox security tests |
| Duplicate mastery updates | Idempotency keys and evidence replay | Milestones 4–7 invariants |
| Sensitive logs/analytics | Content denylist and contract tests | Milestone 11 verification |
| Destructive migration | Reviewed reversible migrations, backups, restore rehearsal | Human Gate 11 |
| Provider outage/cost abuse | Timeouts, budgets, rate limits, feature kill switches | Milestone 11 chaos/load tests |

## Open questions for Human Gate 0

- Which auth, API hosting, database, LLM, and execution providers are acceptable?
- Which regions and data residency requirements apply?
- What beta concurrency and monthly budget should limits assume?
- What are the exact retention and backup-expiry windows?
- Who may access learner content for support, and how is that access audited?

## Implemented controls (2026-09-24, local scope)

| Threat | Control in code | Evidence |
| --- | --- | --- |
| Sandbox escape / exfiltration | Ephemeral Docker per job: no network, read-only root, uid 65534, no capabilities, cgroup limits; non-dumpable supervisor; scrubbed env (ADR 0005) | `tests/test_sandbox_docker.py` |
| Hidden-test extraction | Expected outputs never enter the sandbox; submit returns aggregate counts only; guard blocks hidden inputs in interviewer text | `test_execution_service.py`, `test_guard.py` |
| Prompt injection / leakage | Fenced untrusted content, forbidden-behavior prompt, deterministic output guard (code dumps, reference overlap, prompt disclosure, key-insight reveal), policy fallback | `test_guard.py`, persona `adversarial_prompt_injection` |
| False code verdicts | Facts computed from sandbox results only; LLM claims contradicting execution are dropped | `test_evaluation.py` |
| Duplicate mastery/tasks | Evidence dedupe keys, idempotent execution keys, partial unique index on active tasks, optimistic concurrency | `test_learner_model.py`, `test_scheduler.py`, `test_interviews.py` |
| Sensitive analytics/logs | Allowlisted analytics contract; logs without content | `test_solutions_analytics.py` |
| Cross-user access (future) | Every query scoped by `user.id`; ownership tests with a second user | `test_interviews.py`, `test_reviews_drills.py`, `test_execution_service.py` |
| Vulnerable dependencies | CI `pnpm audit` / `pip-audit` / gitleaks; Next.js upgraded 16.3.1 → 16.3.6 for critical RCE advisories | `.github/workflows/ci.yml` |

Residual: no authentication (local only); Docker Desktop isolation is weaker than microVMs;
aggregate hidden-test counts are a low-bandwidth side channel.
