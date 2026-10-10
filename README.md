# Glazed Copilot

A store copilot for the Glazed Co. coffee and donut chain (SOFTEK Road To Tech 2026, "Tienda Inteligente para Retail").
A store manager asks, by text or voice, what to order, what is about to be wasted or go out of stock, and which promotions
to run. A FastAPI backend computes every number from the cleaned sales and inventory data (reorder plans with a holdout
Poisson-GLM forecast, waste and stock-out exposure, promotion audits); an LLM agent runtime (Agent-Core) only explains
and proposes, and each proposal waits for the manager's approval.

## Architecture

```
 browser (PWA, React)
   |  https
 Traefik  (or published port, see "No Traefik")        <- infra/docker-compose.yml, services below
   |
 web (nginx: static PWA + /api proxy)  -- /internal/ is never exposed
   |  /api/v1
 backend (FastAPI, hexagonal) ---------- DuckDB  data/clean/glazed.duckdb   (all metrics, read-only)
   |        |       |                     Parquet data/forecast/out/forecast.parquet (glm_poisson forecast)
   |        |       +-- MiniMax (voice STT/TTS, intent classifier)
   |        +---------- Postgres 16 (cases, proposals, users)       <- db
   |  REST
 core + core-peer-worker (Agent-Core, vertical "glazed") -- MiniMax LLM
   |  tools call back /internal/v1/*  (the agent never invents a number)
 backend

 data/  ETL + forecast job:  vendor/dataset-road2tech (raw CSV) -> data/clean -> data/forecast/out
```

| Path | Content |
|---|---|
| `backend/` | FastAPI service (domain, application, ports, adapters, metrics) and its tests |
| `frontend/` | React PWA (Vite, Tailwind, Vitest) |
| `cli/` | terminal client of the public API |
| `agent-core/` | git submodule: Agent-Core runtime, branch `vertical/glazed` |
| `vendor/dataset-road2tech/` | git submodule: the organizers' raw CSVs |
| `data/` | reproducible ETL + forecast build (see `data/README.md`) |
| `infra/` | `docker-compose.yml`, `docker-compose.local.yml`, Dockerfiles, nginx |
| `docs/` | `architecture.md` and the analysis reports in `docs/results/` (Spanish) |

## Prerequisites

Docker with Compose v2.24 or newer, `make`, `git`, and about 4 GB of free RAM for the stack plus 3 GB while `make data`
runs. A MiniMax API key. For development and tests also Python 3.12+ and Node 22.
No license file is shipped with this repository.

## Quick start on a new server

```sh
git clone --recursive https://github.com/Dispearson-SC/glazed-copilot.git
cd glazed-copilot                      # already cloned without --recursive?  make submodules
cp .env.example .env                   # then edit .env, see below
make data                              # builds data/clean/glazed.duckdb and data/forecast/out/forecast.parquet
make up                                # builds and starts db, backend, core, core-peer-worker, web
```

Fill in `.env` (every variable is documented in `.env.example`):

| Variable | Needed for |
|---|---|
| `MINIMAX_API_KEY` | required: Agent-Core LLM, voice, intent classifier |
| `POSTGRES_PASSWORD` | set a real one before the first `make up` (it is baked into the volume) |
| `GLAZED_SESSION_SECRET` | required with `GLAZED_AUTH_REQUIRED=true` (`openssl rand -hex 32`) |
| `GLAZED_PUBLIC_HOST`, `TRAEFIK_NETWORK` | Traefik routing (below) |
| `GLAZED_WEB_BASICAUTH` | basic auth in front of the app (`echo "user:$(openssl passwd -apr1 'pw')"`, escape `$` as `$$`), or set `GLAZED_WEB_GATE=glazed-web-open` to drop it |
| `BACKBOARD_API_KEY` | optional: per-store experience memory; without it recall is simply empty |

The first `make up` also builds the Agent-Core image from `agent-core/Core`. Check it:

```sh
curl -s http://localhost:8100/api/v1/health            # backend (published on 127.0.0.1 only)
curl -s https://$GLAZED_PUBLIC_HOST/api/v1/health      # through the proxy, add -u user:password with the basic-auth gate
docker compose -f infra/docker-compose.yml ps          # db and core should be healthy
```

### Traefik

The `web` service carries Traefik labels for `Host(${GLAZED_PUBLIC_HOST})` with HTTP-to-HTTPS redirect and a Let's
Encrypt resolver. It joins the existing Docker network named by `TRAEFIK_NETWORK` (default `traefik`; `docker network ls`
on the server). If your Traefik names its entrypoints or resolver differently, set `TRAEFIK_ENTRYPOINT_HTTP`,
`TRAEFIK_ENTRYPOINT_HTTPS` and `TRAEFIK_CERTRESOLVER`.

### No Traefik

```sh
make up LOCAL=1        # adds infra/docker-compose.local.yml: no labels, no proxy network
```

The web is then at `http://localhost:${GLAZED_WEB_PORT:-8080}` (set `GLAZED_COOKIE_SECURE=false` for plain HTTP). There
is no TLS or basic auth in this mode; put your own reverse proxy in front of it for a public server.

### Users and demo login

Passwords are read from stdin, never from arguments. With `GLAZED_AUTH_REQUIRED=true` create at least one user:

```sh
C="docker compose -f infra/docker-compose.yml --env-file .env exec -T backend"
printf '%s' 'a-strong-password' | $C python -m glazed_backend.scripts.users add \
  --email admin@example.com --name "Admin" --role admin --stores S001,S002 --password-stdin
$C python -m glazed_backend.scripts.users list
```

Run `python -m glazed_backend.scripts.users --help` for roles and options. Alternatively set `GLAZED_ADMIN_EMAIL` and
`GLAZED_ADMIN_PASSWORD` and the backend creates or updates that admin on start. `GLAZED_DEMO_LOGIN=true` adds a
passwordless user picker for demos; never enable it on a real deployment.

### Voice

Push-to-talk speech-to-text and text-to-speech go through the backend to MiniMax (`MINIMAX_API_KEY`), so the key never
reaches the browser. Defaults: voice `Spanish_Intonategirl`, model `speech-2.8-hd`, STT `asr-1.0`
(`GLAZED_TTS_VOICE`, `GLAZED_TTS_MODEL`, `GLAZED_STT_MODEL`). `GLAZED_VOICE=false` disables it. Microphone capture in
the browser requires HTTPS (or `localhost`).

## Makefile

| Target | What it does |
|---|---|
| `make submodules` | fetch `agent-core/` and `vendor/dataset-road2tech/` |
| `make data` | build `data/clean` (Parquet + `glazed.duckdb`) and `data/forecast/out/forecast.parquet` in a one-shot container |
| `make data-local` | same on the host (`pip install -r data/requirements.txt`) |
| `make up` / `make down` | start (build) / stop the stack; `SERVICES="db backend"` limits it, `LOCAL=1` skips Traefik |
| `make deps` | host dev dependencies (backend and cli in `.deps/`, frontend `npm install`) |
| `make test` | backend, cli, ETL/forecast and frontend suites |
| `make api` | run the backend on the host at :8100 (in-memory repositories unless `GLAZED_STORAGE=postgres`) |
| `make cli ARGS="day --json"` | run the terminal client |
| `make load-data` | optional: copy the Parquet tables into Postgres schema `glazed` |
| `make seed-memory` | optional: seed Backboard experience memory (`BACKBOARD_API_KEY`) |

## Tests

```sh
make deps
make backend-test      # cd backend && PYTHONPATH=.deps:src python3 -m pytest -q
make cli-test
make etl-test          # needs: pip install -r data/requirements-dev.txt
make frontend-test     # vitest + type-check + production build
docker compose -f infra/docker-compose.yml --env-file .env.example config -q    # validate the compose file
```

The backend integration tests run against `data/clean/glazed.duckdb` and `vendor/dataset-road2tech` and skip themselves
when `make data` has not been run.

## Updating a running server

```sh
git pull --recurse-submodules && make data && make up
```

`make data` is only needed when the ETL, the forecast job or the dataset changed.
