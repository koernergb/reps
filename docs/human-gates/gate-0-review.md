# Human Gate 0 review packet

Implementation must stop after the Milestone 0 checkpoint until this gate is approved.

## Review checklist

- [ ] A new contributor can follow `README.md` to install, test, and run the system.
- [ ] Product owner confirms the MVP is Python-first interview prep and accepts the parking-lot exclusions.
- [ ] Engineering approves the web/API/database/sandbox trust boundaries in `docs/threat-model.md`.
- [ ] Team chooses or revises ADR 0002 authentication.
- [ ] Team chooses API/database/execution providers in ADRs 0003 and 0005.
- [ ] Team approves the structured LLM boundary in ADR 0004.
- [ ] Product/privacy owners approve concrete retention, backup expiry, support access, and processor disclosures for ADR 0006.
- [ ] A monthly beta budget and initial concurrency target are supplied.
- [ ] Named approvers and decision date are recorded below.

## Five-minute walkthrough

1. Copy `.env.example` to `.env`.
2. Run `make setup`, then `make check`.
3. With Docker installed, run `make services-up` and `make db-migrate`.
4. Run `make dev`; open the landing page, dashboard shell, API `/health`, and API `/ready`.
5. Stop PostgreSQL and confirm `/health` remains live while `/ready` returns a request-linked `503`.
6. Review CI, the seven ADRs, and the trust-boundary table.

## Cost-envelope inputs needed

The initial provider estimate is in [`docs/cost-envelope.md`](../cost-envelope.md). Provider prices change, so recheck its official sources during review. The estimate uses these scenarios:

| Scenario | MAU | Interviews/user/month | Code runs/interview | Drill attempts/user/month |
| --- | ---: | ---: | ---: | ---: |
| Alpha | 100 | 4 | 10 | 30 |
| Private beta | 1,000 | 4 | 10 | 30 |
| Early scale | 10,000 | 4 | 10 | 30 |

Include fixed and usage-based web/API/database/auth, LLM input/output, execution CPU/runtime, logs, backups, and data-transfer costs. Show low/base/high LLM token assumptions and a cost-per-completed-interview estimate.

## Unresolved decisions

- Authentication: Clerk recommendation versus self-hosted alternative.
- API hosting: benchmark Render, Fly.io, and Cloud Run.
- PostgreSQL: approve Neon or select another managed service.
- Execution: benchmark E2B, Modal, and hardened self-managed microVMs.
- Exact LLM model(s): decided by the Milestone 4 evaluation harness; approve OpenAI as initial provider boundary.
- Retention windows, backup expiry, data region, support access, beta budget, and beta concurrency.

## Decision record

- Product approver:
- Engineering approver:
- Security/privacy approver:
- Decision date:
- Status: Pending
- Required changes:
