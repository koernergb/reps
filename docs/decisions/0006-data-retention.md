# ADR 0006: Minimal, user-controlled learning data retention

- Status: Accepted for local-first scope at Human Gate 0
- Date: 2026-08-20

## Local-phase decision

Keep interview events, code snapshots, chat, execution results, evaluations, hints, and learner-state evidence in local PostgreSQL until the owner exports or resets it. Provide a complete JSON learning-data export and a history reset that preserves corpus content. Local database volume removal remains the full reset mechanism.

Default application logs must not include raw submitted code, full transcripts, email addresses, prompts, hidden tests, or secrets. Analytics receives event names and minimal pseudonymous properties, not content.

## Reopen trigger

Before any shared or hosted use, choose concrete retention windows, backup expiry, subprocessors, support-access policy, consent language, and external-provider deletion behavior. OpenAI request retention and data controls must be disclosed before live interview content is sent in Milestone 4.
