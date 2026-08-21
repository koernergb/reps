# ADR 0003: Local-first topology with preserved execution isolation

- Status: Accepted at Human Gate 0
- Date: 2026-08-20

## Decision

- Web: local Next.js development/production server.
- API: local FastAPI process.
- PostgreSQL: local PostgreSQL through Compose.
- Code execution: a separately isolated local sandbox introduced in Milestone 3. It must not run in the FastAPI process or receive application/database/OpenAI credentials.

Bind local services to loopback by default. Do not expose the application through port forwarding, tunnels, or a public host under this ADR.

## Why

The immediate goal is a useful tool for its owner, not a hosted multi-user service. Local operation removes premature auth, MAU, and infrastructure work, but it does not make submitted code safe to execute in the API process.

## Reopen trigger

Reopen before shared use, remote access, or deployment. At that point select hosting, managed PostgreSQL, identity, regions, backups, budget controls, observability, and support-access policy.
