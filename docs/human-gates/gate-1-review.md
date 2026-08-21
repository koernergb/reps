# Human Gate 1 — Local data integrity and privacy

Milestone 1 is adapted to the Human Gate 0 decision: Reps is a single-user local tool without authentication. This gate validates the singleton ownership boundary, evaluator secrecy, migrations, export, and destructive reset behavior. It does **not** approve hosted or shared use.

## Automated evidence

- Full schema upgrade → downgrade → upgrade passes on a clean database.
- Seed is idempotent: one local user, three topics, five capabilities, three problems, and three evaluator records.
- Public list/detail responses exclude reference solutions, hidden tests, common mistakes, and follow-up evaluator data.
- Local export includes learner-owned history and excludes evaluator material.
- History reset deletes attempts, learner state, interviews, events, and hints while preserving profile and corpus.
- Reset is idempotent.
- Lint, strict type checks, tests, coverage threshold, and production build pass.

## Required human validation

**STOP IMPLEMENTATION.** Run the application locally and perform these checks:

1. Open `/problems` and verify three development problems load from the API.
2. Open each problem and confirm the statement, examples, constraints, starter code, and capability tags are sensible.
3. Inspect the browser network response for `/v1/problems/{slug}`. Search it for `hidden_tests`, `reference_solution`, `common_mistakes`, and `follow_up_questions`; none may appear.
4. Open Settings and download an export. Verify the file is understandable and contains no evaluator secrets.
5. After creating fixture/history data through tests or later product use, choose Reset history. Confirm the destructive warning is clear and the resulting counts are plausible.
6. Reload Problems after reset and confirm corpus content remains.
7. Confirm the local-only warning is prominent and that no screen implies authentication protects the service.
8. Review the three seeded problems for correctness. They remain `development` content and are not Human Gate 2 corpus-approved.

## Approval record

- Product/data approver:
- Decision date:
- Status: Pending
- Problems found:
- Required changes:

Approval authorizes Milestone 2 corpus work. It does not authorize deployment, shared use, or code execution.
