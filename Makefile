.PHONY: deps test backend-test cli-test etl-test frontend-test api up down data data-local load-data seed-memory cli submodules
PY ?= python3
# Always an absolute --env-file: compose reads .env from infra/ otherwise and MINIMAX_API ends up empty.
COMPOSE = docker compose -f $(CURDIR)/infra/docker-compose.yml $(if $(wildcard $(CURDIR)/.env),--env-file $(CURDIR)/.env,$(warning .env missing: secrets will be empty))
API_URL ?= http://localhost:8100
# Optional: LOCAL=1 adds infra/docker-compose.local.yml (no Traefik; web published on GLAZED_WEB_PORT).
COMPOSE += $(if $(LOCAL),-f $(CURDIR)/infra/docker-compose.local.yml)
# The holdout forecast dir mounted at /forecast in the backend defaults to data/forecast/out (see docker-compose.yml);
# override with GLAZED_FORECAST_DIR.

deps:
	cd backend && $(PY) -m pip install --target .deps -e . --no-deps && $(PY) -m pip install --target .deps duckdb fastapi uvicorn httpx "psycopg[binary]" pytest pydantic
	cd cli && $(PY) -m pip install --target .deps typer rich httpx pytest
	cd frontend && npm install

test: backend-test cli-test etl-test frontend-test
backend-test:
	cd backend && PYTHONPATH=.deps:src $(PY) -m pytest -q
cli-test:
	cd cli && PYTHONPATH=.deps:src $(PY) -m pytest -q
etl-test:
	cd data/etl && PYTHONPATH=.deps:. $(PY) -m pytest -q
	cd data/forecast && PYTHONPATH=.deps:. $(PY) -m pytest -q
frontend-test:
	cd frontend && npm test -- --run && npm run build

api:
	cd backend && PYTHONPATH=.deps:src $(PY) -m uvicorn glazed_backend.adapters.driving.app:create_app_from_env --factory --port 8100

# Fetch the git submodules (agent-core/ and vendor/dataset-road2tech/) when the repo was cloned without --recursive.
submodules:
	git submodule update --init --recursive

# Build the derived data (data/clean/*.parquet, glazed.duckdb, data/forecast/out/forecast.parquet) from the raw CSVs
# in a one-shot python:3.12 container. Takes a few minutes and ~3 GB of RAM (limit: DATA_BUILD_MEM, default 6g).
data: submodules
	$(COMPOSE) --profile tools run --rm --build --user $$(id -u):$$(id -g) data-build
# Same without Docker: needs `pip install -r data/requirements.txt` (use PY=/path/to/venv/bin/python).
data-local: submodules
	PY=$(PY) sh data/build.sh

# Whole stack: Postgres, backend, Agent-Core and its peer worker. Needs .env (see .env.example).
up:
	$(COMPOSE) up -d --build $(SERVICES)
down:
	$(COMPOSE) down

load-data:
	cd backend && PYTHONPATH=.deps:src $(PY) -m glazed_backend.loader $(or $(PARQUET_DIR),../data/clean)
seed-memory:
	set -a; [ -f .env ] && . ./.env; set +a; cd backend && PYTHONPATH=.deps:src $(PY) scripts/seed_experiences.py --stores $(or $(STORES),S030)

# make cli ARGS="day --json"
cli:
	cd cli && GLAZED_API_URL=$${GLAZED_API_URL:-$(API_URL)} PYTHONPATH=.deps:src $(PY) -m glazed_cli $(ARGS)
