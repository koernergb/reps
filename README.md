# Reps

Reps is an adaptive technical-interview coach. It interviews you on curated Python problems,
runs your code in an isolated sandbox, diagnoses capability-level weaknesses from what actually
happened (tests, hints, explanations), schedules targeted spaced remediation, and checks transfer
on unseen problems later.

The product brief is [`ai_native_spaced_repetition_interview_coach_build_brief_v2.md`](./ai_native_spaced_repetition_interview_coach_build_brief_v2.md);
the milestone plan with its human gates is [`MILESTONES.md`](./MILESTONES.md).

> [!WARNING]
> **Local, single-user tool.** There is no authentication. Keep the web app, API, and database on
> your machine; do not expose them through a tunnel, port forward, or shared host.

> [!IMPORTANT]
> Milestones 2–11 were implemented without their human gates, at the owner's instruction. All
> content is unreviewed, the sandbox has had no human security review, and the AI interviewer has
> never been run against a real model. See [`docs/human-gates/`](./docs/human-gates/) for what each
> gate still requires.

## Status

| Milestone | Built | Human gate |
| --- | --- | --- |
| 0 Foundations | ✅ | Approved (local-first scope) |
| 1 Local data, privacy controls | ✅ | Pending |
| 2 Corpus (32 problems, 62 exercises, 64 capabilities) | ✅ | Not performed |
| 3 Sandboxed execution + editor | ✅ | Not performed |
| 4 Interview state machine, events, interviewer | ✅ | Not performed (no LLM run yet) |
| 5 Evaluation and reports | ✅ | Not performed |
| 6 Learner model | ✅ | Not performed (histories generated) |
| 7 Remediation scheduler and reviews | ✅ | Not performed |
| 8 Adaptive drills | ✅ | Not performed |
| 9 Mock interviews | ✅ | Not performed |
| 10 Solution-viewing remediation | ✅ | Not performed |
| 11 Operability (local adaptation) | ✅ | Out of scope (no beta) |
| 12 Beta decision | — | Needs real usage data |

## Prerequisites

- Node.js 22+ and pnpm 11.20.0
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Docker Desktop (PostgreSQL and the code sandbox)

## Set up

```bash
cp .env.example .env
make setup
make services-up     # PostgreSQL in Docker
make sandbox-build   # learner code only ever runs in this image
make db-migrate
make db-seed         # syncs the curated corpus into the database
```

## Run

```bash
make dev
```

This starts the web app (http://localhost:3000), the API (http://127.0.0.1:8000, docs at
`/docs`), and the execution worker. If those ports are taken, set `API_PORT`, `WEB_ORIGIN`, and
`NEXT_PUBLIC_API_URL` in `.env` (for example `API_PORT=8100` and
`NEXT_PUBLIC_API_URL=http://127.0.0.1:8100`).

### AI provider

By default the interviewer, answer grader, and evaluator are deterministic built-in policies, and
nothing leaves your machine. To use a model, open **Settings → AI provider**, paste an OpenAI or
Google Gemini API key, pick a model (*Load models* lists what your key can use), press *Test
connection*, and select the provider. Keys are stored in the local database, never shown again,
never logged, and excluded from exports. You can instead configure `LLM_PROVIDER`,
`OPENAI_API_KEY`/`OPENAI_MODEL`, or `GEMINI_API_KEY`/`GEMINI_MODEL` in `.env`; a choice made in
Settings takes precedence. What is sent is listed on the `/privacy` page.

Gemini is called through Google's OpenAI-compatible endpoint with a simplified JSON schema; every
reply is still validated, and failures fall back to the built-in policies.

## Using Reps

1. **Dashboard** → *Start a 10-minute drill* (due reviews plus your weakest skills) or *Start mock
   interview*.
2. **Interview**: choose Practice (up to five graded hints, coaching, no timer) or Mock (45 minutes,
   one nudge, scorecard). Talk to the interviewer, move through phases, run and submit code. The
   pattern name is hidden so recognizing it is part of the exercise.
3. **Report**: exact facts (tests, hints, complexity), interpretation with linked evidence, and the
   reviews scheduled from it. Flag anything inaccurate; flagged evidence is excluded.
4. **Reviews**: recall, explanation, trace, debug, rebuild, transfer, and unseen re-interviews,
   each with a "why now". Missed items get a Rebuild step and come back tomorrow.
5. **Progress**: capability bands (Weak/Developing/Reliable/Strong) with plain-language
   explanations and an evidence trail.
6. **Problems**: free practice; *View solution* is consentful and schedules remediation instead
   of marking the problem solved.

## Verify

```bash
make check                                 # lint, types, unit tests (API + web)
pnpm build
pnpm corpus:validate                       # run every reference and known-wrong solution
pnpm --filter @reps/api personas           # 9 scripted interview personas
make sandbox-test                          # adversarial suite against the Docker sandbox
pnpm --filter @reps/web e2e                # Playwright against a running stack (make dev)
TEST_DATABASE_URL=postgresql+psycopg://reps:reps-local-only@127.0.0.1:5432/reps_test \
  pnpm --filter @reps/api test             # run the API suite on PostgreSQL
scripts/verify-restore.sh                  # backup → isolated restore → row-count comparison
```

## Data controls

Settings exports every learner-owned table as JSON (hidden tests and reference solutions are
never included), rebuilds skill estimates from evidence, and resets history. A test fails if a
new table holding learner data is not covered by export and reset. Backups written by
`scripts/backup-db.sh` contain learner content; keep them local.

## Repository layout

```text
apps/web                  Next.js app (workspace, interviews, reports, reviews, drills, progress)
apps/api                  FastAPI API, execution worker, Alembic migrations
  app/corpus              corpus schema, loader, validator
  app/execution           sandbox backends, job service, result normalization
  app/interview           state machine, events, policies, interviewer, guard, personas
  app/evaluation          facts, rules, report schema, evaluation service
  app/learning            evidence, learner model, pipeline, outcome metrics
  app/scheduling          remediation scheduler
  app/reviews, app/drills review flows and drill composer
  app/llm                 provider adapter, prompts, audit
packages/problem-corpus   taxonomy, problems, exercises (source of truth)
packages/prompts          versioned prompts and persona fixtures
infra/sandbox             sandbox image and harness
docs/                     ADRs, human-gate packets, operations, metrics, learning model
scripts/                  backup, restore, restore verification
```

## Documentation

- [`docs/operations.md`](./docs/operations.md): processes, metrics, SLOs, kill switches, runbooks
- [`docs/learning-model.md`](./docs/learning-model.md): learner model, scheduler, drill composer
- [`docs/metrics.md`](./docs/metrics.md): learning metrics and analytics event catalog
- [`docs/threat-model.md`](./docs/threat-model.md) and ADRs in [`docs/decisions/`](./docs/decisions/)
- [`packages/problem-corpus/CONTRIBUTING.md`](./packages/problem-corpus/CONTRIBUTING.md): authoring content

## Known limitations

- No authentication; not safe to expose beyond localhost.
- All corpus content is unreviewed; the offline grader uses keyword rubrics and can under-credit
  paraphrases.
- The offline interviewer is scripted; realistic conversation requires `LLM_PROVIDER=openai`,
  which has only been exercised against mocked responses.
- Docker Desktop is the isolation boundary; a hosted deployment needs a microVM/gVisor sandbox
  and a new security review.
