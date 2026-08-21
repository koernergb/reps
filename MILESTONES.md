# Implementation Milestones

This document turns the product brief into an implementation sequence for the MVP: an AI coding interview coach that observes how a learner struggles, diagnoses capability-level weaknesses, schedules targeted remediation, and verifies transfer on later problems.

It is written as instructions for an implementation agent. Complete milestones in order. Do not treat a milestone as complete because its UI exists; complete it only when its acceptance checks, automated tests, documentation, and human gate are satisfied.

The source of truth for product intent is [`ai_native_spaced_repetition_interview_coach_build_brief_v2.md`](./ai_native_spaced_repetition_interview_coach_build_brief_v2.md). If this plan and the brief conflict, stop and ask the product owner which behavior should win, then update both documents.

## Approved local-first scope overlay

Human Gate 0 was approved on 2026-08-20 for a single-user tool built for its repository owner:

- use OpenAI as the initial structured LLM backend;
- run the web app, API, and PostgreSQL locally;
- defer authentication, hosting, MAU planning, and production operations;
- seed one stable local user while retaining `user_id` ownership throughout the schema;
- never interpret local-only mode as authorization for shared or public access;
- keep submitted-code execution outside the API process and require the full sandbox security gate;
- reopen identity, privacy/retention, deployment, backup, support-access, budget, and observability decisions before another person can use the system or it becomes network-accessible.

Where a milestone or gate below assumes multiple accounts or hosted infrastructure, use the local adaptation in `docs/human-gates/` until this overlay is explicitly revoked. This overlay narrows implementation; it does not waive content, evaluator, sandbox, AI-behavior, learning-quality, or destructive-data validation gates.

## Working rules for every milestone

1. Read the current repository state, relevant documentation, and existing tests before changing code.
2. Keep the MVP focused on the closed loop: interview → diagnosis → remediation → delayed retrieval → transfer test. Do not add realtime voice, content ingestion, mobile apps, social features, leaderboards, or an unrestricted AI-generated problem corpus.
3. Prefer deterministic software for authentication, authorization, state transitions, scheduling, code execution, and test scoring. Use an LLM only for conversational interviewing, semantic evaluation, misconception detection, hint generation, and concise explanations.
4. Represent product-significant LLM outputs with versioned, validated schemas. Never parse prose to make a scheduling, scoring, or authorization decision.
5. Store meaningful interview actions as structured events. A chat transcript alone is insufficient.
6. Never run learner code in the web or API process. Treat all submitted code as hostile.
7. Add or update tests in the same change as behavior. Include failure paths, authorization boundaries, and retries where applicable.
8. Keep migrations reversible where practical. Backward-incompatible schema or API changes require a migration/rollout note.
9. Do not expose hidden tests, reference solutions, prompt secrets, model credentials, or another user's data to clients or model context.
10. At each human gate, stop implementation. Provide the requested artifact, exact reproduction steps, known limitations, and a clear pass/fail question. Resume only after explicit human approval. Record the decision in the milestone's decision log or a short ADR under `docs/decisions/`.

## Definition of done

Every milestone must meet these baseline conditions:

- lint, type checking, unit tests, and relevant integration/end-to-end tests pass in a clean checkout;
- setup and test commands are documented and reproducible;
- new environment variables are represented in an example environment file without secrets;
- logs are structured and exclude sensitive source, transcripts, credentials, and hidden test contents by default;
- errors shown to users are actionable without leaking internals;
- accessibility basics work for new UI: keyboard navigation, focus states, labels, contrast, and error announcements;
- product analytics introduced in the milestone have documented event names and properties;
- the milestone's acceptance criteria have evidence, not just an implementation claim;
- no unrelated feature work is bundled into the milestone.

## Milestone 0 — Resolve foundations and prove the local skeleton

### Outcome

A documented, reproducible monorepo skeleton with the core stack running locally and the high-impact product and infrastructure decisions resolved.

### Implement

- Create the recommended layout:
  - `apps/web`: Next.js, TypeScript, React, Tailwind, and shadcn/ui.
  - `apps/api`: FastAPI, Pydantic, SQLAlchemy, Alembic, and pytest.
  - `packages/shared-types`: generated or shared API contracts.
  - `packages/problem-corpus`: curated problem definitions and validators.
  - `packages/prompts`: versioned prompt templates and evaluation fixtures.
  - `infra/docker` and `infra/sandbox`: local infrastructure definitions.
  - `docs/decisions`: short architectural decision records.
- Add repository-level commands for install, development, lint, formatting, type checking, tests, database migration, and clean local startup.
- Add local PostgreSQL configuration and a health-checked web → API → database path.
- Add CI for formatting/linting, web and API types, unit tests, migration validation, and corpus validation.
- Add a minimal responsive shell with routes for sign-in, dashboard, problems, drills, interviews, history, settings, privacy/export, and account deletion. Placeholder pages are acceptable here.
- Add a typed API client and consistent error envelope with a request/correlation ID.
- Add configuration validation at application startup. Fail clearly if required variables are absent.
- Write ADRs for:
  - package manager and workspace tooling;
  - authentication provider/build-vs-buy decision;
  - initial deployment targets;
  - LLM provider/model abstraction and structured-output strategy;
  - isolated code-execution provider or architecture;
  - data retention defaults;
  - initial programming language (default recommendation: Python only).

### Automated verification

- A clean setup boots web, API, and PostgreSQL with one documented command or a short documented sequence.
- Health endpoints fail when their dependency is unavailable and recover when it returns.
- CI runs on a trivial branch and caches dependencies without caching secrets.
- Migration smoke test upgrades an empty database to head and downgrades one revision.
- Web/API contract smoke test detects an intentionally invalid response during test execution.

### Human gate 0 — Architecture and scope approval

**STOP IMPLEMENTATION.** Ask the product owner and a senior engineer to review the ADRs, repository commands, local boot path, page map, MVP exclusions, and proposed deployment topology.

Provide:

- a five-minute local setup walkthrough;
- estimated recurring cost for database, LLM calls, code execution, and hosting at 100, 1,000, and 10,000 monthly active users;
- a threat sketch showing browser, API, database, LLM provider, and sandbox trust boundaries;
- the unresolved decision list.

Do not begin authentication or domain-schema migrations until the product owner approves scope and engineering approves the trust boundaries.

### Acceptance

- A new contributor can boot and test the skeleton from the README.
- The team has explicitly selected auth, hosting, LLM, execution, retention, and initial-language approaches.
- The MVP exclusion list is acknowledged.

## Milestone 1 — Authentication, authorization, privacy controls, and domain schema

### Outcome

An authenticated user can access only their own records, manage their account, and view a seeded problem backed by the initial domain model.

### Implement

- Implement email/social authentication according to ADR 0002, including session expiry, logout, CSRF protections where applicable, and account-linking behavior.
- Define authorization centrally. All user-scoped database access must include the authenticated user ID; do not rely on client-supplied ownership fields.
- Implement initial tables and migrations for:
  - users;
  - topics and hierarchical topics;
  - capabilities and capability types;
  - problems and problem-capability weights;
  - exercises;
  - review attempts;
  - learner capability states;
  - interview sessions and interview events;
  - hint logs.
- Use UUIDs or another non-enumerable public identifier. Add timestamps, necessary uniqueness constraints, foreign keys, indexes, and explicit deletion behavior.
- Separate public problem content from protected evaluator content such as hidden tests and reference solutions.
- Seed a tiny development corpus (3–5 problems) solely to validate the model.
- Add settings flows to export account data and delete the account/interview history. A documented asynchronous stub is acceptable only if its limitations and completion milestone are explicit.
- Publish a plain-language draft privacy/retention policy in the product and document which data is sent to the LLM provider.

### Automated verification

- Authorization tests prove user A cannot list, fetch, edit, export, or delete user B's attempts, state, events, or sessions.
- Migration tests cover upgrade from empty, downgrade, constraints, seed idempotency, and deletion behavior.
- API serialization tests prove hidden tests, reference solutions, internal evaluations, and prompt metadata never appear in public problem responses.
- Auth integration tests cover expired sessions, revoked sessions, logout, and unsafe redirect rejection.
- Export/delete tests enumerate every user-owned table so future schema changes cannot silently omit data.

### Human gate 1 — Identity and privacy validation

**STOP IMPLEMENTATION.** Ask a human tester to create two accounts and attempt cross-account access using both the UI and direct API requests. Ask the product owner to approve the retention/export/delete behavior and all third-party data disclosures.

Provide a test script with expected status codes and screenshots. If any cross-account access, stale-session access, incomplete deletion, or secret evaluator-data exposure occurs, keep the gate failed and debug before continuing.

### Acceptance

- A user can sign in, sign out, open the dashboard, and view a seeded problem.
- Cross-user access is denied at the API and data-access layers.
- Export and deletion behavior is testable and documented.

## Milestone 2 — Curated corpus and capability taxonomy

### Outcome

A version-controlled, validated corpus of 25–50 high-quality Python interview problems covers the initial capability taxonomy and supports later diagnosis and transfer testing.

### Implement

- Define a schema for each problem containing statement, examples, constraints, difficulty, topics/patterns, prerequisites, capability weights, common mistakes, canonical complexity, visible tests, protected hidden tests, reference solution, interviewer clarifications, follow-up questions, related problems, and transfer group.
- Define capability types for recall, recognition, reasoning, implementation, debugging, communication, complexity analysis, interview independence, and transfer.
- Begin with arrays/hashing, two pointers, sliding window, stack, binary search, linked lists, trees, heaps, graphs, and 1-D dynamic programming. Use the brief's distribution as a target, not a popularity ranking.
- For every major pattern include recognition, canonical implementation, boundary-heavy, and transfer opportunities.
- Add corpus linting for schema validity, unique slugs, valid capability references, nonempty tests, deterministic reference outputs, complexity metadata, transfer links, and forbidden public exposure.
- Add a contribution guide describing how a problem is authored, tested, reviewed, versioned, and retired.
- Keep AI-generated full problems out of the accepted corpus during MVP.

### Automated verification

- Execute every reference solution against visible and hidden tests in an isolated test runner.
- Mutation or known-wrong-solution tests prove hidden tests catch common mistakes recorded in metadata.
- Coverage report shows problem counts by pattern, difficulty, capability type, and transfer group.
- Corpus build fails on circular prerequisites, dangling relations, duplicate tests, or unbounded execution settings.

### Human gate 2 — Content accuracy and fairness review

**STOP IMPLEMENTATION.** Have at least one experienced technical interviewer manually review every problem statement, clarification, reference solution, expected complexity, hidden tests, capability mapping, and transfer relationship. Have a second human solve a representative sample without seeing internal metadata.

Record corrections and sign-off per problem. Do not use an unreviewed problem in learner-facing evaluation. Debug ambiguous statements, flaky tests, or multiple-valid-answer mismatches before continuing.

### Acceptance

- At least 25 reviewed problems are available, with a path to 50 before private beta.
- Common wrong solutions are rejected for the intended reason.
- Capability and transfer coverage have no unexplained gaps in the selected patterns.

## Milestone 3 — Safe Python coding environment

### Outcome

An authenticated learner can edit Python in Monaco, run visible tests, and submit against hidden tests through an isolated, resource-limited execution service.

### Implement

- Add Monaco with Python syntax support, keyboard-accessible run/submit controls, persistent draft recovery, and resizable statement/editor/results panes.
- Define separate `run` and `submit` semantics. `run` returns visible-test detail; `submit` reports only safe aggregate hidden-test feedback.
- Build an execution API with queued/request-bounded jobs, immutable job IDs, explicit states, cancellation/expiry, and idempotency behavior.
- Execute in an ephemeral sandbox with no host mounts, no credentials, no privileged mode, no outbound network, a read-only base filesystem where practical, a disposable writable directory, process/user isolation, syscall controls, and strict CPU, wall-clock, memory, process, file, and output limits.
- Pin runtime and dependency versions. Start with Python standard library only unless a reviewed allowlist is needed.
- Normalize compile/runtime/timeout/output-limit results without returning infrastructure internals.
- Add rate limiting, concurrency limits, audit metadata, sandbox health checks, and emergency execution disablement.
- Never send arbitrary source code to logs or analytics by default.

### Automated verification

- Integration tests cover pass, assertion failure, syntax error, exception, timeout, memory pressure, fork/process bomb, oversized output, file probing, environment probing, network attempts, and concurrent submissions.
- Tests prove hidden test inputs, expected outputs, harness code, reference solutions, credentials, host paths, and neighboring jobs cannot be read.
- Retry/idempotency tests prevent duplicate scoring and inconsistent job state.
- Browser tests cover draft persistence, run/submit distinction, errors, keyboard use, and pane resizing.
- Load test establishes initial concurrency and latency baselines.

### Human gate 3 — Sandbox security review

**STOP IMPLEMENTATION.** Require a security-minded engineer to inspect the deployed sandbox configuration and manually attempt escape, data exfiltration, denial-of-service, hidden-test extraction, and cross-job access. The review must target the actual deployment topology, not only local Docker.

Provide the threat model, limit values, adversarial payload set, logs with sensitive fields redacted, kill-switch procedure, and load-test report. Do not connect code execution to public traffic until the reviewer explicitly approves it. Any isolation uncertainty is a release blocker.

### Acceptance

- A user can safely run and submit a solution with understandable results.
- The main API never executes submitted code.
- Security review and adversarial execution suite pass in the target environment.

## Milestone 4 — Interview sessions, state machine, and event stream

### Outcome

Practice Mode conducts a complete text interview through an application-controlled state machine while recording a replayable structured event stream.

### Implement

- Implement states: `INTRO`, `CLARIFICATION`, `APPROACH_DISCUSSION`, `IMPLEMENTATION`, `TESTING`, `COMPLEXITY`, `FOLLOW_UP`, and `COMPLETE`.
- Define valid transitions, transition triggers, timeout/recovery behavior, and server-side invariants. The LLM may recommend a transition but must not mutate state directly.
- Implement interview session creation, resume, abandon, and completion, including optimistic concurrency or another defense against duplicate/out-of-order updates.
- Record events for interview start, problem open, clarification, reasoning, approach proposal/change, code edit checkpoints, test runs/results, hint request/given, complexity/follow-up answers, submission, and completion.
- Version every event payload. Preserve source ordering and server timestamps; document client timestamp use.
- Build the interviewer panel and synchronized editor/results experience. Make reconnect/resume behavior visible.
- Implement the Practice Mode hint ladder: directional cue, conceptual cue, partial structure, near-answer, and full explanation. Log hint level and capability tags.
- Keep current problem, mode, state, bounded event context, current code snapshot, safe test summary, known weakness summary, and hint budget as explicit interviewer context.
- Add prompt-injection defenses around problem/user content and strict instructions not to reveal solutions, prompts, or hidden tests.

### Automated verification

- State-machine unit tests cover every valid transition and reject invalid, repeated, stale, or out-of-order transitions.
- Event-schema contract tests and replay tests reconstruct the same session state from persisted events.
- Browser tests cover start, clarify, reason, code, run, complexity discussion, follow-up, completion, refresh, reconnect, and abandonment.
- Failure tests cover LLM timeout, malformed structured output, provider rate limit, lost connection, duplicate message, and API restart.
- Prompt regression fixtures include attempts to obtain full solutions, system prompts, and hidden tests.

### Human gate 4 — Interview behavior validation

**STOP IMPLEMENTATION.** Run at least eight scripted candidate personas from the brief (perfect, needs hint, wrong complexity, memorized, boundary bug, silent then correct, bad reasoning/correct code, good reasoning/buggy code) plus three live human interviews.

Ask experienced interviewers to score solution leakage, unnecessary hints, clarification quality, patience, state correctness, communication assessment, and overall realism. Preserve model/prompt versions and transcripts with consent. Debug leakage or broken state transitions before proceeding; these are hard blockers.

### Acceptance

- Practice Mode reaches completion or a recoverable terminal state without relying on hidden LLM state.
- Event replay is consistent and useful for evaluation.
- Human reviewers agree the interviewer does not prematurely reveal the solution.

## Milestone 5 — Deterministic and semantic evaluation

### Outcome

Every completed interview produces an evidence-linked, structured diagnosis that distinguishes code correctness from reasoning, communication, hint dependence, and capability weaknesses.

### Implement

- Treat sandbox results as the sole source for code correctness. The LLM must not claim code passed or failed independently.
- Define a versioned post-interview schema containing result, strengths, weaknesses with capability/severity/evidence, hints used, communication assessment, complexity assessment, confidence, and transfer confidence.
- Build explicit services for grading, misconception detection, hint generation, and post-interview evaluation rather than embedding prompts in routes.
- Store evaluator model, prompt version, schema version, input event range, output, validation result, latency, and retry/fallback outcome.
- Require evidence references to interview event IDs for material claims. Reject or flag unsupported diagnoses.
- Add bounded retries for malformed outputs and a degraded state that asks the learner to return later instead of fabricating a report.
- Display the report in plain language, distinguish facts from AI interpretation, and offer a way to report an inaccurate diagnosis.
- Define evaluation rubrics and confidence thresholds. Low-confidence diagnoses must not make large mastery changes later.

### Automated verification

- Golden fixtures cover all scripted candidates and assert schema validity, deterministic-code alignment, capability extraction, evidence linkage, and forbidden claims.
- Metamorphic tests vary names or irrelevant wording and check for materially consistent evaluation.
- Tests cover correct code/bad reasoning, buggy code/good reasoning, multiple correct approaches, hint use, incomplete sessions, model timeout, malformed output, and contradictory output.
- Track evaluation agreement, unsupported-claim rate, leakage rate, parse failure rate, latency, and cost per completed interview.

### Human gate 5 — Evaluation calibration

**STOP IMPLEMENTATION.** Have two human reviewers independently score a blinded evaluation set, adjudicate disagreements, then compare the model's diagnosis with the adjudicated labels.

Agree in advance on minimum thresholds for capability precision/recall, severity agreement, false-positive rate, unsupported claims, and report usefulness. The product owner must approve learner-facing wording. If thresholds fail, revise the rubric, prompts, schemas, or capability mapping and rerun the exact set plus a held-out set.

### Acceptance

- Reports are reproducible enough for the same evidence and never override deterministic test facts.
- Diagnoses cite the learner behavior that supports them.
- Calibration thresholds and results are documented.

## Milestone 6 — Learner model and explainable mastery updates

### Outcome

The system updates capability-level learner state from review and interview evidence and can explain each change without presenting fake precision.

### Implement

- Define a simple, documented MVP update policy for mastery, interval/stability, last reviewed time, next review time, evidence confidence, and attempt history.
- Use signals available in the brief: correctness, latency, hint count/strength, exercise difficulty/type, time since exposure, transfer distance, and interview independence. Keep weights explicit and testable.
- Make updates idempotent and append evidence before updating aggregate state. Support recomputing aggregate state from attempts/events.
- Bound single-attempt changes and reduce impact for low-confidence or incomplete evidence.
- Keep memory/recognition, conceptual reasoning, implementation/debugging, communication, independence, and transfer distinct where the taxonomy supports it.
- Expose user-friendly bands (`Weak`, `Developing`, `Reliable`, `Strong`) and an explanation such as “two recent boundary errors with a level-2 hint.” Do not display unsupported decimal precision.
- Build weak-capability dashboard and history views with filters by topic, evidence type, and time.
- Add correction/appeal tooling so reported bad diagnoses can be excluded and aggregates recomputed.

### Automated verification

- Table-driven unit tests cover success/failure, hints, stale evidence, repeated same-problem success, transfer success, low confidence, and duplicate delivery.
- Property tests verify bounds, idempotency, monotonic expectations for comparable evidence, and deterministic replay.
- Rebuild test deletes aggregate state, replays evidence, and obtains the same result.
- Authorization tests cover all learner-state and history endpoints.

### Human gate 6 — Learning-science and UX sanity check

**STOP IMPLEMENTATION.** Walk a learning-science reviewer and product owner through at least five synthetic multi-week learner histories, including contradictory evidence and solution viewing. Ask whether the resulting state, wording, and next-review implications are defensible and understandable.

Provide a spreadsheet or fixture report showing every input, weight, intermediate calculation, output band, and explanation. Debug surprising jumps, repeated-problem overconfidence, or transfer inflation before continuing.

### Acceptance

- Persistent weaknesses emerge across problems and remain traceable to evidence.
- Replaying evidence reproduces learner state.
- Human-facing labels are understandable and avoid false precision.

## Milestone 7 — Scheduled remediation and review exercises

### Outcome

A failed interview automatically creates a safe, explainable sequence of targeted reviews and re-tests rather than marking the problem complete.

### Implement

- Implement a conservative, deterministic MVP scheduler; do not introduce novel FSRS/Bayesian complexity yet.
- Generate or select remediation in a progression: recall/recognition → explain/trace → debug/code fragment → full reconstruction → related transfer → re-interview.
- Use severity, confidence, hint dependence, exercise type, recent load, and past performance to set due dates. Establish explicit timezone and daylight-saving behavior.
- Prefer reviewed, templated exercises from the corpus. If the LLM creates a micro-variation, validate its structured form, execute its reference answer/tests, mark provenance, and keep it out of the permanent corpus until human review.
- Implement queue semantics for due, snoozed, skipped, completed, invalidated, and superseded items. Prevent duplicates and cap daily workload.
- Implement Retrieve, Coach, and Rebuild flows, including the five-level hint ladder and misconception confirmation question.
- Capture natural answers, confidence, latency, hints, deterministic checks where applicable, semantic evaluation, and resulting mastery update.
- Show “why this is scheduled” and permit a user to report a broken exercise.

### Automated verification

- Use a fake clock to test due dates across timezones, DST, long absence, day boundaries, and rescheduling.
- Scenario tests reproduce the brief's sliding-window sequence: next-day concept, day-3 debugging, day-7 implementation, day-14 transfer, and later unseen problem.
- Invariant tests prevent duplicate active tasks, negative intervals, runaway queues, unreviewed corpus promotion, and scheduling from invalid evidence.
- End-to-end test goes from failed interview to due review to completed attempt to changed learner state and next exercise.

### Human gate 7 — Schedule and exercise quality validation

**STOP IMPLEMENTATION.** Ask representative learners and an educator/interviewer to complete generated remediation sequences for at least five failure profiles. Review difficulty ordering, ambiguity, workload, hint usefulness, and whether transfer items are genuinely related but not memorized duplicates.

Provide the exact evidence-to-schedule trace and all generated content. Any unsolvable, ambiguous, incorrectly tested, or answer-leaking exercise is a blocker. Tune caps and intervals only after recording the rationale.

### Acceptance

- A failed interview creates targeted future work with no manual database action.
- Learners can understand why an item is due and complete it safely.
- Scheduler invariants and representative human sequences pass.

## Milestone 8 — Adaptive 10-minute drills

### Outcome

The dashboard's primary action creates a useful 5–15 minute session from current weaknesses, due work, and progression needs.

### Implement

- Build a deterministic session composer that selects items under a time budget and documents its priorities/tie-breakers.
- Balance due urgency, weak capabilities, exercise diversity, recent repetition, difficulty, transfer distance, and estimated duration.
- Avoid multiple items that test the same superficial recall unless Rebuild mode requires it.
- Support session start, item progress, pause/resume, safe early exit, completion summary, and atomic attempt recording.
- Display estimated time and explain the session mix without revealing answers.
- Track planned versus actual duration, completion, abandonment point, item outcomes, and subsequent transfer performance.

### Automated verification

- Property tests ensure budgets, diversity constraints, due-item priorities, no duplicates, and stable tie-breaking.
- Scenario tests cover new users, no due items, many overdue items, one dominant weakness, sparse corpus, and interrupted sessions.
- Browser test completes a mixed drill and verifies all evidence and next dates exactly once.

### Human gate 8 — Daily-use usability test

**STOP IMPLEMENTATION.** Run moderated sessions with at least five target users. Ask them to start without coaching, think aloud, finish a drill, interpret the summary, and state why each exercise appeared.

Review keyboard accessibility, cognitive load, pacing, error recovery, perceived repetition, and whether the session fits its stated budget. Debug severe usability issues and rerun affected tasks before continuing.

### Acceptance

- A learner history produces a diverse, relevant, time-bounded drill.
- Attempt data updates the learner model and future queue exactly once.
- Target users can complete and understand the flow without facilitator help.

## Milestone 9 — Mock Interview Mode

### Outcome

Mock Mode provides a materially stricter, timed interview while reusing the same event, execution, evaluation, and learner-model foundations.

### Implement

- Define a separate server-side policy for clarifications, silence, allowed nudges, hint budget, time limits, extensions, and terminal behavior.
- Make mode and constraints unambiguous before starting. Do not silently change modes mid-session.
- Add timer behavior resilient to refresh, reconnect, client clock manipulation, and temporary provider failure.
- Add a scorecard for correctness, reasoning, communication, complexity, and independence. Keep scoring rubric versioned and explainable.
- Do not use known weaknesses to lead the learner toward the answer; use them only for unbiased follow-up selection or later diagnosis.
- Add accommodations such as disabling visible countdown animation while preserving the time contract.

### Automated verification

- Policy tests prove Practice and Mock produce different allowed interventions for identical events.
- Timer tests use a server-authoritative clock and cover reconnect, background tabs, expiry races, and abandoned sessions.
- Regression tests measure unsolicited hints, full-solution leakage, and inconsistent scoring.

### Human gate 9 — Realism and bias review

**STOP IMPLEMENTATION.** Have experienced interviewers conduct side-by-side Practice and Mock sessions using identical candidate scripts, then run live mocks with representative users.

Ask reviewers whether Mock is meaningfully stricter without becoming hostile, whether silence and clarification feel realistic, and whether scores over-penalize communication style or accessibility needs. Debug policy leakage, timer unfairness, or unexplained scoring before beta.

### Acceptance

- Users and reviewers can reliably distinguish Practice from Mock behavior.
- Mock sessions remain recoverable and evidence-linked.
- The scorecard does not contradict deterministic execution facts.

## Milestone 10 — Solution-viewing remediation

### Outcome

Viewing a solution is recorded as assisted exposure and triggers comprehension, reconstruction, implementation, and transfer checks instead of granting mastery.

### Implement

- Add an explicit, consentful “view solution” action with a warning that it changes the learning plan.
- Record solution-viewed provenance and timing without overwriting the failed attempt.
- Immediately request a key-insight explanation without the solution visible.
- Schedule pseudocode reconstruction for the next day, implementation in 3–4 days, a related problem in 1–2 weeks, and a later unseen transfer problem; allow the normal scheduler to adjust within documented bounds.
- Prevent same-problem success immediately after viewing from being interpreted as independent transfer.
- Display progress as assisted comprehension, reconstruction, implementation, and transfer—not a binary solved badge.

### Automated verification

- Scenario test covers failure → solution viewed → immediate check → delayed reconstruction → implementation → transfer.
- Learner-model tests prove solution exposure reduces independence weight and cannot directly produce `Strong` transfer.
- UI tests prove protected solutions are inaccessible until the action is confirmed and never leak into normal problem payloads.

### Human gate 10 — Remediation validity check

**STOP IMPLEMENTATION.** Ask learners who recently failed a problem to use the flow, then test delayed reconstruction and a transfer item at the intended intervals. The product owner must review all mastery/status language for accidental “solved” incentives.

This gate necessarily takes multiple days. Do not compress delayed validation into one session and claim the learning loop is proven. Record qualitative results and any schedule deviations.

### Acceptance

- Solution viewing remains distinct from independent performance in data and UI.
- The full delayed remediation chain is created and survives normal rescheduling.
- At least one multi-day human pilot validates that the workflow is understandable.

## Milestone 11 — Observability, reliability, safety, and beta readiness

### Outcome

The end-to-end MVP is operable in a private beta with measurable reliability, cost, privacy, and learning outcomes.

### Implement

- Add structured metrics and traces for request latency/errors, LLM latency/errors/schema failures/cost, sandbox queue/runtime/termination reasons, event ingestion, evaluation completion, scheduler jobs, and drill completion.
- Define service-level objectives and alerts for sign-in, session start/resume, code execution, interview response, evaluation availability, and queue generation.
- Add rate limits and abuse controls for auth, LLM messages, execution, exports, and deletions.
- Add backup/restore procedures, migration rollout/rollback, key rotation, provider outage playbooks, and sandbox/LLM kill switches.
- Complete export and deletion jobs if they were previously asynchronous stubs. Verify deletion propagation to analytics, logs, backups, and external providers according to policy.
- Add consent and retention controls for transcripts/code. Minimize model context and define redaction behavior.
- Build an admin/support surface with least privilege for diagnosing request IDs and job states without casually exposing learner content.
- Add feature flags for interview, execution, semantic evaluation, scheduling, drills, Mock Mode, and solution viewing.
- Instrument MVP metrics: activation, week-2 retention, sessions/week, return for re-test, hints/problem, pattern-identification time, implementation errors, and transfer success after remediation.
- Do not optimize for the success targets until event definitions, denominators, and data quality checks are documented.

### Automated verification

- End-to-end test covers sign-up → interview → code execution → report → remediation → drill → transfer state.
- Load and soak tests cover expected beta concurrency and provider slowdown.
- Chaos tests exercise LLM outage, sandbox outage, database retry, worker restart, duplicate delivery, and partial evaluation.
- Backup restoration is tested into an isolated environment; migration rollback is rehearsed.
- Analytics contract tests reject accidental code, transcript, email, hidden-test, or secret fields.
- Dependency, container, and secret scans run in CI with documented triage rules.

### Human gate 11 — Private-beta release review

**STOP IMPLEMENTATION.** Conduct a release review with product, engineering, security/privacy, and support owners.

Provide:

- end-to-end demo using a fresh account;
- threat model and sandbox review result;
- evaluation calibration report;
- corpus review coverage;
- accessibility and usability findings;
- load/soak results and cost envelope;
- backup/restore evidence;
- data-flow/retention/deletion verification;
- dashboards, alerts, runbooks, known issues, and rollback plan;
- feature-flag rollout sequence and beta cohort size.

Release only after named owners approve. Start with a small allowlisted cohort, review incidents and data quality daily, and retain an immediate rollback/disable path.

### Acceptance

- Critical user journeys meet agreed SLOs and failure modes are recoverable.
- Security, privacy, evaluation, content, and operational gates are signed off.
- Metrics needed to test the product thesis are trustworthy enough for beta decisions.

## Milestone 12 — Validate the core loop and decide what comes next

### Outcome

The team determines with real evidence whether interview diagnosis and spaced remediation improve independent transfer, then chooses to iterate, expand, or stop.

### Implement

- Run a time-bounded private beta long enough to observe delayed reconstruction and transfer; define cohort, activation, and exclusion criteria before analyzing results.
- Measure the primary learning sequence: initial failure → delayed reconstruction → delayed implementation → unseen transfer.
- Analyze hints per problem, time to identify a pattern, time to first viable approach, implementation errors, re-test return, sessions/week, and week-2 retention.
- Review inaccurate-diagnosis reports, broken exercises, corpus gaps, abandonment, model costs, and operational incidents.
- Segment carefully by prior skill and activity; do not claim causality from raw before/after data.
- Convert findings into a ranked iteration list tied to the core loop.

### Human gate 12 — Product decision

**STOP IMPLEMENTATION.** Present the beta evidence and ask the product owner to make one explicit decision:

1. iterate on diagnosis/remediation quality;
2. broaden the curated corpus;
3. invest in retention and daily drills;
4. proceed to a post-MVP capability; or
5. stop/pivot because the core loop is not validated.

Do not begin voice, PDF/course ingestion, rich learner models, mobile apps, or unrestricted generation without this decision. If expansion is approved, write a new milestone plan with its own security, quality, human-validation, and rollout gates.

### Acceptance

- Transfer success after remediation is reported with cohort definitions and limitations.
- The team can explain whether the product remembered and corrected meaningful weaknesses—not merely whether users solved more familiar problems.
- The next investment decision and rationale are recorded.

## Release-blocking conditions

Stop and escalate immediately at any milestone if:

- learner code can affect the API/host, access a network or secret, escape limits, inspect hidden tests, or influence another job;
- one user can access another user's sessions, code, evaluations, learner state, export, or deletion controls;
- the interviewer reveals full solutions, system prompts, hidden tests, or claims false execution results;
- structured evaluation materially contradicts deterministic evidence or produces unsupported high-severity diagnoses;
- migrations risk unrecoverable data loss without an approved backup and rollback path;
- generated or curated exercises are ambiguous, unsolvable, incorrectly tested, or silently promoted without review;
- retries create duplicate attempts, events, mastery updates, or scheduled tasks;
- privacy disclosures, retention, export, or deletion behavior differ from actual system behavior;
- a human gate has not been explicitly approved.

## Post-MVP parking lot

Keep these out of implementation until Milestone 12 authorizes a new plan:

- push-to-talk and realtime voice;
- PDF, slide, note, and course ingestion;
- candidate inbox for generated learning material;
- AI-generated full problem corpus;
- FSRS, Bayesian Knowledge Tracing, Item Response Theory, or Deep Knowledge Tracing;
- multiple programming languages beyond the first supported language;
- mobile apps, social features, leaderboards, browser extensions, IDE plugins, and human interview matching.

The default next step after beta should be improving the weakest measured part of the interview → diagnosis → remediation → transfer loop, not adding a new surface.
