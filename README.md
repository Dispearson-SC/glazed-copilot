# glazed-copilot

Store copilot for Glazed Co. Monorepo: `backend/` (FastAPI, hexagonal), `cli/`, `frontend/`, `infra/`, `docs/`.
Agent-Core (the agent runtime) lives next to this repo in `../Agent-Core` and calls the backend's internal API for every number.

## Quick start
```
cp .env.example .env
make deps && make test
make api          # in-memory repos + DuckDB metrics on :8100
make up           # Postgres 16 in container glazed-db on host port 55432
```
See `docs/architecture.md` for layout, ports, the case model and the API contract.
