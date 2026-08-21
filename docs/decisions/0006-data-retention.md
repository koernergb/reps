# ADR 0006: Minimal, user-controlled learning data retention

- Status: Proposed
- Date: 2026-08-20

## Recommendation

Keep account data until account deletion; retain interview events, code snapshots, chat, execution results, evaluations, hints, and learner-state evidence while the account is active because they power the product's longitudinal loop. Let users delete individual interview history and export all account data. On account deletion, remove active-system data promptly and document bounded backup expiry.

Default application logs must not include raw submitted code, full transcripts, email addresses, prompts, hidden tests, or secrets. Analytics receives event names and minimal pseudonymous properties, not content.

## Required before implementation

At Human Gate 0/1, choose concrete retention windows, subprocessors, backup expiry, support-access policy, legal basis/consent language, and external-provider deletion behavior. The UI and policy must match actual system behavior before beta.
