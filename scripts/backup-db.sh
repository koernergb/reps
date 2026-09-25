#!/usr/bin/env bash
# Back up the local Reps database to backups/reps-<UTC timestamp>.dump (pg_dump custom format).
# Backups contain learner content (code, transcripts). Keep them on this machine.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="backups/reps-${stamp}.dump"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-reps}" -d "${POSTGRES_DB:-reps}" --format=custom > "$target"
chmod 600 "$target"
echo "$target"
