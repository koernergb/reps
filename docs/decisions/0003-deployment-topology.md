# ADR 0003: Separate web, API, database, and execution trust zones

- Status: Proposed
- Date: 2026-08-20

## Recommendation

- Web: Vercel.
- API: a container service such as Render, Fly.io, or Google Cloud Run, selected after latency and cost comparison.
- PostgreSQL: managed PostgreSQL (recommended: Neon for preview branching and scale-to-zero during private beta).
- Code execution: a purpose-built isolated execution provider or a separately administered sandbox service. It must not share credentials, runtime, filesystem, or a network trust zone with the API.

Deploy web and API in compatible regions. Use separate service identities, least-privilege database roles, encrypted connections, and independent kill switches for LLM and execution features.

## Why

The trust boundary matters more than reducing the number of deployables. Learner code is hostile and must not enter the API process. The private-beta load does not justify self-managing PostgreSQL.

## Open decision

Benchmark the shortlisted API and execution providers before committing. Human Gate 0 must approve the actual topology and recurring cost envelope.
