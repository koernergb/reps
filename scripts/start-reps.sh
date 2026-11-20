#!/usr/bin/env bash
# Start Reps locally: Docker, Postgres, sandbox image, migrate/seed, web+API, browser.
# Ctrl+C stops the app processes. Learner data lives in the Docker Postgres volume.
set -euo pipefail
cd "$(dirname "$0")/.."

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

env_get() {
  local key="$1" default="${2:-}" line
  [[ -f .env ]] || { printf '%s' "$default"; return; }
  line="$(grep -E "^${key}=" .env | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$default"
  else
    printf '%s' "${line#*=}"
  fi
}

need() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

wait_for() {
  local label="$1" url="$2" seconds="${3:-90}" i
  for ((i = 1; i <= seconds; i++)); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$label is ready."
      return 0
    fi
    sleep 1
  done
  die "Timed out waiting for $label ($url)."
}

ensure_env() {
  if [[ ! -f .env ]]; then
    [[ -f .env.example ]] || die ".env.example is missing; cannot create .env."
    cp .env.example .env
    log "Created .env from .env.example. Add GEMINI_API_KEY or OPENAI_API_KEY if you want the LLM interviewer."
  fi
}

ensure_docker() {
  need docker
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  [[ "$(uname -s)" == "Darwin" ]] || die "Docker is not running. Start Docker, then re-run."
  log "Starting Docker Desktop…"
  open -a Docker || die "Could not open Docker Desktop. Install it, then re-run."
  local i
  for ((i = 1; i <= 120; i++)); do
    if docker info >/dev/null 2>&1; then
      log "Docker is ready."
      return 0
    fi
    sleep 1
  done
  die "Docker Desktop did not become ready in time."
}

ensure_deps() {
  need pnpm
  need uv
  need curl
  if [[ ! -d node_modules ]] || [[ ! -d apps/api/.venv ]]; then
    log "Installing dependencies…"
    make setup
  fi
}

ensure_sandbox() {
  local image
  image="$(env_get SANDBOX_IMAGE reps-sandbox:dev)"
  if docker image inspect "$image" >/dev/null 2>&1; then
    return 0
  fi
  log "Building sandbox image ($image)…"
  make sandbox-build
}

API_HOST="$(env_get API_HOST 127.0.0.1)"
API_PORT="$(env_get API_PORT 8000)"
WEB_ORIGIN="$(env_get WEB_ORIGIN http://localhost:3000)"
API_HEALTH="http://${API_HOST}:${API_PORT}/health"

already_running() {
  curl -sf "$API_HEALTH" >/dev/null 2>&1 && curl -sf "$WEB_ORIGIN" >/dev/null 2>&1
}

open_app() {
  log "Opening ${WEB_ORIGIN}"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$WEB_ORIGIN"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$WEB_ORIGIN" >/dev/null 2>&1 || true
  fi
}

ensure_env
ensure_docker
ensure_deps

log "Starting Postgres…"
make services-up
ensure_sandbox

log "Applying migrations…"
make db-migrate
log "Syncing problem corpus…"
make db-seed

if already_running; then
  log "Reps is already running."
  open_app
  exit 0
fi

log "Starting web + API (Ctrl+C to stop)…"
# New process group so Ctrl+C / EXIT can stop make + pnpm + child servers.
set -m
make dev &
DEV_PID=$!

cleanup() {
  trap - EXIT INT TERM
  if kill -0 "$DEV_PID" >/dev/null 2>&1; then
    kill -TERM -"$DEV_PID" >/dev/null 2>&1 || kill -TERM "$DEV_PID" >/dev/null 2>&1 || true
    wait "$DEV_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

wait_for "API" "$API_HEALTH" 90
wait_for "web" "$WEB_ORIGIN" 90
open_app

log "Reps is running. Web: ${WEB_ORIGIN}  API: http://${API_HOST}:${API_PORT}"
wait "$DEV_PID"
