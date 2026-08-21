.PHONY: setup dev check services-up services-down db-migrate

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
