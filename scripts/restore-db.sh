#!/usr/bin/env bash
# Restore a backup into a database (default: an isolated rehearsal database).
#   scripts/restore-db.sh backups/reps-....dump                # -> reps_restore_check
#   scripts/restore-db.sh backups/reps-....dump reps --yes     # overwrite the live database
set -euo pipefail
cd "$(dirname "$0")/.."
file="${1:?usage: restore-db.sh <dump> [database] [--yes]}"
database="${2:-reps_restore_check}"
user="${POSTGRES_USER:-reps}"
if [[ "$database" == "${POSTGRES_DB:-reps}" && "${3:-}" != "--yes" ]]; then
  echo "Refusing to overwrite the live database without --yes. Stop 'make dev' first." >&2
  exit 1
fi
docker compose exec -T postgres psql -U "$user" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"${database}\"" -c "CREATE DATABASE \"${database}\""
docker compose exec -T postgres pg_restore -U "$user" -d "$database" --no-owner --exit-on-error < "$file"
echo "restored $file into $database"
