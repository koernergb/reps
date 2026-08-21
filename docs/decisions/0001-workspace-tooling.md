# ADR 0001: Workspace and build tooling

- Status: Proposed
- Date: 2026-08-20

## Decision

Use a pnpm 11 workspace for JavaScript packages and `uv` for the Python API. Keep orchestration in package scripts and a small root Makefile rather than introducing Turborepo before build volume justifies it. Require Node 22+ and Python 3.12; CI uses the current Node 24 LTS line.

## Why

The repository has one frontend and one backend. pnpm provides deterministic workspace installs, while uv provides a fast lockfile-driven Python environment. Avoiding another task runner reduces configuration during product discovery.

## Consequences

- There are two lockfiles: `pnpm-lock.yaml` and `apps/api/uv.lock`.
- Root commands delegate into each package.
- Add a build orchestrator only when measured CI/runtime pain warrants it.
