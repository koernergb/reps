# Human Gate 0 review packet

Implementation must stop after the Milestone 0 checkpoint until this gate is approved.

## Review checklist

- [x] A new contributor can follow `README.md` to install, test, and run the system.
- [x] Product owner confirms a Python-first, single-user interview-prep prototype and accepts the parking-lot exclusions.
- [x] Engineering trust boundaries remain required even for local use; code execution stays outside the API process.
- [x] Authentication is deferred; an application-owned singleton user preserves the future ownership boundary.
- [x] Hosting and MAU architecture are deferred. Web, API, and PostgreSQL run locally.
- [x] OpenAI is approved as the initial structured LLM provider boundary.
- [x] Local data is retained until the owner uses export, history reset, or database reset controls.
- [x] Hosted-service budget and concurrency targets are not applicable to the current phase.
- [x] Product/engineering approval is recorded below.

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

- Authentication and multi-user authorization before any hosted or shared use.
- Hosting, managed PostgreSQL, regions, support access, backups, budget, and concurrency before deployment.
- Exact OpenAI model selection, which remains evaluation-driven in Milestones 4–5.
- The local isolated execution mechanism and its Milestone 3 adversarial review.

## Decision record

- Product approver: Repository owner
- Engineering approver: Repository owner, accepting the local-first prototype constraints
- Security/privacy approver: Not applicable until shared/hosted use; sandbox isolation remains a mandatory gate
- Decision date: 2026-08-20
- Status: Approved — local-first, single-user scope
- Required changes: Defer authentication, MAU planning, and deployment. Use OpenAI for structured LLM services. Preserve user ownership columns and execution isolation so the prototype can evolve safely.
