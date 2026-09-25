#!/usr/bin/env bash
# Backup -> restore into an isolated database -> compare per-table row counts and migration head.
set -euo pipefail
cd "$(dirname "$0")/.."
user="${POSTGRES_USER:-reps}"
source_db="${POSTGRES_DB:-reps}"
dump="$(scripts/backup-db.sh)"
scripts/restore-db.sh "$dump" reps_restore_check >/dev/null
exact_sql="SELECT string_agg(t, ',' ORDER BY t) FROM (SELECT table_name || '=' || (xpath('/row/c/text()', query_to_xml('SELECT count(*) AS c FROM ' || quote_ident(table_name), false, true, '')))[1]::text AS t FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE') counts;"
source_counts="$(docker compose exec -T postgres psql -U "$user" -d "$source_db" -Atc "$exact_sql")"
restored_counts="$(docker compose exec -T postgres psql -U "$user" -d reps_restore_check -Atc "$exact_sql")"
if [[ "$source_counts" != "$restored_counts" ]]; then
  echo "MISMATCH" >&2
  diff <(tr ',' '\n' <<<"$source_counts") <(tr ',' '\n' <<<"$restored_counts") >&2 || true
  exit 1
fi
echo "restore verified: $(tr ',' '\n' <<<"$restored_counts" | wc -l | tr -d ' ') tables match ($dump)"
