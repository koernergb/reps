.PHONY: setup dev check services-up services-down db-migrate db-seed sandbox-build sandbox-test corpus-validate execution-off execution-on

setup:
	pnpm install
	cd apps/api && uv sync --all-groups

dev:
	pnpm dev

check:
	pnpm check

services-up:
	docker compose up -d --wait postgres

services-down:
	docker compose down

db-migrate:
	pnpm db:migrate

db-seed:
	pnpm db:seed

# Learner code only runs inside this image. Rebuild after changing infra/sandbox.
sandbox-build:
	docker build -t reps-sandbox:dev infra/sandbox

sandbox-test:
	pnpm test:sandbox

corpus-validate:
	pnpm corpus:validate

# Emergency kill switch: new executions are rejected; queued jobs expire.
execution-off:
	@echo "Set EXECUTION_ENABLED=false in .env and restart 'make dev' to disable code execution."

execution-on:
	@echo "Set EXECUTION_ENABLED=true in .env and restart 'make dev' to re-enable code execution."
