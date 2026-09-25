# ADR 0002: Defer authentication for the single-user local prototype

- Status: Accepted at Human Gate 0
- Date: 2026-08-20

## Decision

Do not add an identity provider while Reps is used locally by its owner. Seed one application-owned local user with a stable identifier. All learner-owned tables still require `user_id`, and server-side data access resolves the singleton user rather than accepting a client-supplied owner.

This is not an authorization design for shared or hosted use. Before the app is reachable by another person or an untrusted network, reopen this ADR and implement authenticated sessions, centralized authorization, revocation, account linking, export, and deletion behavior.

## Deferred alternatives

- Auth.js/Better Auth: more control and lower direct provider dependency, but more security-sensitive session and account-linking work for a small team.
- Supabase Auth: attractive if the team also chooses Supabase-hosted PostgreSQL, but couples identity and database vendor decisions.

## Consequences

- No sign-in wall or provider account exists in the local phase.
- The UI must clearly identify local-only mode and must not imply network-safe multi-user isolation.
- Export, history reset, and full local database reset remain available because local data still deserves explicit control.
- Authentication becomes a release blocker before deployment or shared use.
