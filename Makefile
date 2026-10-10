.PHONY: test backend-test deps up down api load-data seed-memory
PY ?= python3
deps:
	cd backend && $(PY) -m pip install --target .deps -e . --no-deps && $(PY) -m pip install --target .deps duckdb fastapi uvicorn httpx "psycopg[binary]" pytest pydantic
test: backend-test
backend-test:
	cd backend && PYTHONPATH=.deps:src $(PY) -m pytest -q
api:
	cd backend && PYTHONPATH=.deps:src $(PY) -m uvicorn glazed_backend.adapters.driving.app:create_app_from_env --factory --port 8100
up:
	docker compose -f infra/docker-compose.yml up -d db
down:
	docker compose -f infra/docker-compose.yml down
seed-memory:
	cd backend && PYTHONPATH=.deps:src $(PY) scripts/seed_experiences.py --stores $(or $(STORES),S030)
load-data:
	cd backend && PYTHONPATH=.deps:src $(PY) -m glazed_backend.loader $(or $(PARQUET_DIR),../../Dataset/clean)
