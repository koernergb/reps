# Reps

Reps is an adaptive technical interview coach. It observes how a learner reasons, converts mistakes and hint usage into capability-level evidence, and schedules targeted practice until the learner can transfer the skill to an unseen problem.

The repository is currently at **Milestone 0: foundation**. The product brief is in [`ai_native_spaced_repetition_interview_coach_build_brief_v2.md`](./ai_native_spaced_repetition_interview_coach_build_brief_v2.md), and the implementation sequence with mandatory human gates is in [`MILESTONES.md`](./MILESTONES.md).

## Prerequisites

- Node.js 22 or newer (CI uses Node 24)
- pnpm 11.20.0
- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose for local PostgreSQL

Docker is needed for the normal development database but not for the current unit test suite.

## Set up

```bash
cp .env.example .env
make setup
make services-up
make db-migrate
```

Run both applications:

```bash
make dev
```

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health
- Database readiness: http://localhost:8000/ready

To run the applications separately:

```bash
pnpm dev:web
pnpm dev:api
```

## Verify

```bash
make check
pnpm build
```

The API unit tests use in-memory SQLite only to verify foundation behavior. PostgreSQL remains the product database and migration target.

## Repository layout

```text
apps/web                 Next.js web application
apps/api                 FastAPI service and Alembic migrations
packages/shared-types    Generated API contracts (future milestone)
packages/problem-corpus  Reviewed problem definitions (Milestone 2)
packages/prompts         Versioned AI prompts and fixtures (Milestone 4)
infra/docker             Container infrastructure notes
infra/sandbox            Isolated execution service boundary (Milestone 3)
docs/decisions           Architectural decision records
```

## Product constraints

- Schedule capabilities, not cards.
- Deterministic execution decides whether code works.
- The LLM handles conversation and semantic interpretation only through validated schemas.
- Submitted learner code never runs in the web or API process.
- Voice, course ingestion, social features, and unrestricted generated problems are post-MVP.
- Stop at every human gate in `MILESTONES.md`; do not code around required validation.

## Configuration

`.env.example` lists supported local variables. Startup configuration is validated by Pydantic. Do not commit `.env` or credentials.

The API returns an `X-Request-ID` response header and a matching `request_id` in error bodies. Use it when reporting failures.

## Contributing

Keep changes scoped to the active milestone. Add tests with behavior, preserve user data, and document new configuration or operational assumptions. Architecture decisions with lasting consequences belong in `docs/decisions/`.
