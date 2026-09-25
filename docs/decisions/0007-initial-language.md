# ADR 0007: Python-only MVP execution

- Status: Proposed
- Date: 2026-08-20

## Decision

Support Python 3.12 only through private-beta validation. Store language as an explicit field in problems, sessions, submissions, and execution jobs so later languages do not require semantic overloading.

## Why

One runtime reduces sandbox surface, corpus/test duplication, editor complexity, evaluation variance, and support load. Python covers the initial early-career interview-prep audience well enough to test the learning loop.

## Expansion trigger

Add another language only after Milestone 12 validates the core loop and user research identifies meaningful demand. Each language requires its own sandbox review, reference solutions, hidden tests, limits, and content sign-off.
