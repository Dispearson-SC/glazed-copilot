.PHONY: deps test backend-test cli-test frontend-test api up down load-data seed-memory cli
PY ?= python3
# Always an absolute --env-file: compose reads .env from infra/ otherwise and MINIMAX_API ends up empty.
COMPOSE = docker compose -f $(CURDIR)/infra/docker-compose.yml $(if $(wildcard $(CURDIR)/.env),--env-file $(CURDIR)/.env,$(warning .env missing: secrets will be empty))
API_URL ?= http://localhost:8100

deps:
	cd backend && $(PY) -m pip install --target .deps -e . --no-deps && $(PY) -m pip install --target .deps duckdb fastapi uvicorn httpx "psycopg[binary]" pytest pydantic
	cd cli && $(PY) -m pip install --target .deps typer rich httpx pytest
	cd frontend && npm install

test: backend-test cli-test frontend-test
backend-test:
	cd backend && PYTHONPATH=.deps:src $(PY) -m pytest -q
cli-test:
	cd cli && PYTHONPATH=.deps:src $(PY) -m pytest -q
frontend-test:
	cd frontend && npm test -- --run && npm run build

api:
	cd backend && PYTHONPATH=.deps:src $(PY) -m uvicorn glazed_backend.adapters.driving.app:create_app_from_env --factory --port 8100

# Whole stack: Postgres, backend, Agent-Core and its peer worker. Needs .env (see .env.example).
up:
	$(COMPOSE) up -d --build $(SERVICES)
down:
	$(COMPOSE) down

load-data:
	cd backend && PYTHONPATH=.deps:src $(PY) -m glazed_backend.loader $(or $(PARQUET_DIR),../../Dataset/clean)
seed-memory:
	set -a; [ -f .env ] && . ./.env; set +a; cd backend && PYTHONPATH=.deps:src $(PY) scripts/seed_experiences.py --stores $(or $(STORES),S030)

# make cli ARGS="day --json"
cli:
	cd cli && GLAZED_API_URL=$${GLAZED_API_URL:-$(API_URL)} PYTHONPATH=.deps:src $(PY) -m glazed_cli $(ARGS)
