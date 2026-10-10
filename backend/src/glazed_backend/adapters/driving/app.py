"""Composition root: wires ports to adapters by environment and builds the FastAPI app."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ...application import TurnTracker
from ...domain import DomainError, FutureDate, InvalidTransition, NotFound
from ...domain.models import CoreError
from .internal_api import build_internal_router
from .public_api import build_public_router


@dataclass
class Container:
    metrics: Any
    core: Any
    cases: Any
    alerts: Any
    proposals: Any
    executions: Any
    backtests: Any
    trace: Any
    clock: Any
    memory: Any = None
    storage: str = "memory"
    core_status: str = "configured"
    cors_origins: list[str] | None = None  # None -> DEFAULT_CORS_ORIGINS
    turn_timeout_s: float = 120.0  # a Core turn with no answer after this long is reported as failed
    turn_tracker: Any = field(default_factory=TurnTracker)
    served: dict = field(default_factory=dict)  # (case_id, issue_id) -> issue as served, for option lookup


DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def cors_origins_from_env(env: dict[str, str]) -> list[str]:
    raw = env.get("GLAZED_CORS_ORIGINS", "")
    parsed = [o.strip() for o in raw.split(",") if o.strip()]
    return parsed or list(DEFAULT_CORS_ORIGINS)


class _NoCore:
    def _fail(self, *a: Any, **k: Any) -> Any:
        raise CoreError("GLAZED_CORE_URL is not configured")

    create_conversation = send_turn = get_turn = list_transcript = _fail


def create_app(c: Container) -> FastAPI:
    app = FastAPI(title="glazed-backend")
    app.add_middleware(CORSMiddleware, allow_origins=c.cors_origins or DEFAULT_CORS_ORIGINS,
                       allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])

    def err(status: int):
        async def handler(_: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status, content={"detail": str(exc)})
        return handler

    app.add_exception_handler(NotFound, err(404))
    app.add_exception_handler(InvalidTransition, err(409))
    app.add_exception_handler(FutureDate, err(400))
    app.add_exception_handler(CoreError, err(502))
    app.add_exception_handler(DomainError, err(400))
    app.include_router(build_public_router(c))
    app.include_router(build_internal_router(c))
    return app


def build_container(env: dict[str, str] | None = None) -> Container:
    from ..driven.duckdb_metrics import DuckDBMetrics
    from ..driven.memory import (InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions,
                                 InMemoryProposals, InMemoryTrace, SystemClock, InMemoryAssistants)
    env = dict(os.environ if env is None else env)
    path = env.get("GLAZED_DUCKDB_PATH")
    if not path or not os.path.exists(path):
        raise RuntimeError("GLAZED_DUCKDB_PATH must point to glazed.duckdb")
    metrics = DuckDBMetrics(path)
    core_url = env.get("GLAZED_CORE_URL")
    if core_url:
        from ..driven.agent_core_http import AgentCoreHttp
        core: Any = AgentCoreHttp.from_env(core_url, env)
    else:
        core = _NoCore()
    cors = cors_origins_from_env(env)
    key = env.get("BACKBOARD_API_KEY", "")
    from ..driven.backboard_memory import BackboardMemory
    from .store_names import StoreNames
    if env.get("GLAZED_STORAGE", "memory") == "postgres":
        from ..driven.postgres import PostgresStore
        store = PostgresStore(env["GLAZED_DATABASE_URL"])
        store.migrate()
        return Container(metrics, core, store.cases, store.alerts, store.proposals, store.executions,
                         store.backtests, store.trace, SystemClock(),
                         BackboardMemory(key, store.assistants, display_name=StoreNames(metrics).of), "postgres",
                         "configured" if core_url else "missing", cors,
                         float(env.get("GLAZED_TURN_TIMEOUT_S", "120")))
    return Container(metrics, core, InMemoryCases(), InMemoryAlerts(), InMemoryProposals(), InMemoryExecutions(),
                     InMemoryBacktests(), InMemoryTrace(), SystemClock(),
                     BackboardMemory(key, InMemoryAssistants(), display_name=StoreNames(metrics).of), "memory",
                     "configured" if core_url else "missing", cors,
                         float(env.get("GLAZED_TURN_TIMEOUT_S", "120")))


def create_app_from_env() -> FastAPI:
    return create_app(build_container())
