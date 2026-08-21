# ADR 0002: Managed authentication with application-owned user records

- Status: Proposed
- Date: 2026-08-20

## Recommendation

Use Clerk for the MVP identity boundary, with email magic link and one mainstream social provider. Keep an application-owned `users` record keyed to the provider subject and enforce authorization in the API/data-access layer. Verify provider tokens server-side; never authorize using client-provided user IDs.

## Alternatives considered

- Auth.js/Better Auth: more control and lower direct provider dependency, but more security-sensitive session and account-linking work for a small team.
- Supabase Auth: attractive if the team also chooses Supabase-hosted PostgreSQL, but couples identity and database vendor decisions.

## Required before implementation

Confirm pricing and terms, supported login methods, account linking, data residency, export/deletion APIs, webhook replay protection, session revocation, and how provider deletion interacts with Reps deletion. If vendor minimization matters more than speed, select Better Auth and revise this ADR at Human Gate 0.
