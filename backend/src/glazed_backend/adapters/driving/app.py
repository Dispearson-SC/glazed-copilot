"""Composition root: wires ports to adapters by environment and builds the FastAPI app."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ...application import TurnTracker
from ..driven.forecast import BaselineForecast, WeekdayFlow
from ..driven.memory import InMemoryDecisionMemories, InMemoryOutcomes, InMemoryTurns, InMemoryUsers
from ...application.auth import LoginThrottle, PasswordHasher, SessionTokens, ensure_admin
from ...domain import DomainError, FutureDate, InvalidCredentials, InvalidTransition, NotFound, TooManyAttempts, Unprocessable
from ...domain.models import CoreError
from .auth_api import AuthGuard, build_auth_router
from .internal_api import build_internal_router
from .public_api import build_public_router
from .voice_api import build_voice_router


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
    turn_timeout_s: float = 600.0  # soft timeout: past it a turn Core still runs is flagged still_running, not failed
    turn_tracker: Any = field(default_factory=TurnTracker)
    classifier: Any = None  # TextClassifierPort (Jev via Backboard, LLM fallback); None -> escape labels
    served: dict = field(default_factory=dict)  # (case_id, issue_id) -> issue as served, for option lookup
    warm_on_startup: bool = False  # production only: precompute recent briefings and init clients in the background
    briefings: Any = None  # BriefingService; built from the other ports when not given
    forecasters: list = field(default_factory=lambda: [BaselineForecast()])  # ForecastPort adapters, first admissible wins
    flow_forecaster: Any = field(default_factory=WeekdayFlow)  # FlowForecastPort
    turns: Any = field(default_factory=InMemoryTurns)  # TurnRepository: stored replies for the conversation history
    outcomes: Any = field(default_factory=InMemoryOutcomes)  # measured outcomes of approved decisions
    decision_memories: Any = field(default_factory=InMemoryDecisionMemories)  # preferences kept from rejection reasons
    users: Any = field(default_factory=InMemoryUsers)  # UserRepository
    auth_required: bool = False  # GLAZED_AUTH_REQUIRED: every /api/v1 route but health, login, logout and me needs a session
    demo_login: bool = False  # GLAZED_DEMO_LOGIN: passwordless user picker (/auth/demo-users, /auth/demo-login); demo only
    cookie_secure: bool = False  # GLAZED_COOKIE_SECURE: the session cookie carries the Secure attribute (behind HTTPS)
    sessions: Any = None  # SessionTokens; a random-secret instance is built when not given
    hasher: Any = field(default_factory=PasswordHasher)
    login_throttle: Any = field(default_factory=LoginThrottle)
    voice: Any = None  # VoiceDesk (STT/TTS for the chat); None -> voice routes answer 503


DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def cors_origins_from_env(env: dict[str, str]) -> list[str]:
    raw = env.get("GLAZED_CORS_ORIGINS", "")
    parsed = [o.strip() for o in raw.split(",") if o.strip()]
    return parsed or list(DEFAULT_CORS_ORIGINS)


class _NoCore:
    def _fail(self, *a: Any, **k: Any) -> Any:
        raise CoreError("GLAZED_CORE_URL is not configured")

    create_conversation = send_turn = get_turn = list_transcript = health = _fail


def create_app(c: Container) -> FastAPI:
    if c.briefings is None:
        from ...application.briefing import BriefingService, SnapshotBuilder
        from .store_names import StoreNames
        from ...application.notes import ManagerNotes
        notes = ManagerNotes(c.cases, c.trace, c.decision_memories, c.memory, c.clock)
        c.briefings = BriefingService(SnapshotBuilder(c.metrics, c.proposals, StoreNames(c.metrics).of, c.served, c.cases, notes), c.clock, c.cases,
                                   (c.memory.warm,) if hasattr(c.memory, "warm") else ())
    if c.sessions is None:
        c.sessions = SessionTokens.from_env({})
    guard = AuthGuard(c)
    app = FastAPI(title="glazed-backend")
    app.add_middleware(CORSMiddleware, allow_origins=c.cors_origins or DEFAULT_CORS_ORIGINS, allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])

    def err(status: int):
        async def handler(_: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status, content={"detail": str(exc)})
        return handler

    async def too_many(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)},
                            headers={"Retry-After": str(getattr(exc, "retry_after_s", 300))})

    app.add_exception_handler(InvalidCredentials, err(401))
    app.add_exception_handler(TooManyAttempts, too_many)
    app.add_exception_handler(NotFound, err(404))
    app.add_exception_handler(InvalidTransition, err(409))
    app.add_exception_handler(FutureDate, err(400))
    app.add_exception_handler(CoreError, err(502))
    app.add_exception_handler(Unprocessable, err(422))
    app.add_exception_handler(DomainError, err(400))
    app.include_router(build_auth_router(c, guard))
    app.include_router(build_public_router(c, guard))
    app.include_router(build_voice_router(c, guard))
    app.include_router(build_internal_router(c))
    if c.warm_on_startup:
        @app.on_event("startup")
        def warm() -> None:  # a background thread: startup never waits for it, and it never raises
            c.briefings.warm_recent()
    return app


def build_container(env: dict[str, str] | None = None) -> Container:
    from ..driven.duckdb_metrics import DuckDBMetrics
    from ..driven.memory import (InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions,
                                 InMemoryProposals, InMemoryTrace, SystemClock, InMemoryAssistants)
    env = dict(os.environ if env is None else env)
    path = env.get("GLAZED_DUCKDB_PATH")
    if not path or not os.path.exists(path):
        raise RuntimeError("GLAZED_DUCKDB_PATH must point to glazed.duckdb")
    from ...metrics.types import config_from_env
    metrics = DuckDBMetrics(path, env.get("GLAZED_RAW_PATH"), config_from_env(env))
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
        classifier = build_classifier(env, store.assistants)
        return _with_auth(Container(metrics, core, store.cases, store.alerts, store.proposals, store.executions,
                         store.backtests, store.trace, SystemClock(),
                         BackboardMemory(key, store.assistants, display_name=StoreNames(metrics).of), "postgres",
                         "configured" if core_url else "missing", cors,
                         float(env.get("GLAZED_TURN_TIMEOUT_S", "600")), classifier=classifier, warm_on_startup=True, turns=store.turns,
                         decision_memories=store.memories, outcomes=store.outcomes, forecasters=build_forecasters(env),
                         users=store.users), env)
    classifier = build_classifier(env, None)
    return _with_auth(Container(metrics, core, InMemoryCases(), InMemoryAlerts(), InMemoryProposals(), InMemoryExecutions(),
                     InMemoryBacktests(), InMemoryTrace(), SystemClock(),
                     BackboardMemory(key, InMemoryAssistants(), display_name=StoreNames(metrics).of), "memory",
                     "configured" if core_url else "missing", cors,
                         float(env.get("GLAZED_TURN_TIMEOUT_S", "600")), classifier=classifier, warm_on_startup=True,
                         forecasters=build_forecasters(env)), env)


def _flag(env: dict[str, str], name: str) -> bool:
    return env.get(name, "false").strip().lower() in ("1", "true", "yes", "on")


def _with_auth(c: Container, env: dict[str, str]) -> Container:
    """Auth settings from the environment, plus the optional GLAZED_ADMIN_EMAIL/PASSWORD bootstrap."""
    c.auth_required = _flag(env, "GLAZED_AUTH_REQUIRED")
    c.demo_login = _flag(env, "GLAZED_DEMO_LOGIN")
    c.cookie_secure = _flag(env, "GLAZED_COOKIE_SECURE")
    c.sessions = SessionTokens.from_env(env)
    ensure_admin(c.users, c.hasher, env)
    c.voice = build_voice(env)
    return c


def build_voice(env: dict[str, str]) -> Any:
    """Voice needs MINIMAX_API_KEY; GLAZED_VOICE=false switches it off. Without a key the desk is None (routes answer 503)."""
    from ...application.voice import VoiceDesk
    from ..driven.minimax_voice import DEFAULT_STT_MODEL, DEFAULT_TTS_MODEL, DEFAULT_VOICE, MiniMaxVoice
    key = env.get("MINIMAX_API_KEY", "")
    voice_id = env.get("GLAZED_TTS_VOICE") or DEFAULT_VOICE
    model = env.get("GLAZED_TTS_MODEL") or DEFAULT_TTS_MODEL
    if not key:
        return VoiceDesk(None, voice_id, model, enabled=False)
    svc = MiniMaxVoice(key, voice_id, model, env.get("GLAZED_STT_MODEL") or DEFAULT_STT_MODEL,
                       env.get("MINIMAX_API_BASE", "https://api.minimax.io/v1"))
    return VoiceDesk(svc, voice_id, model, enabled=env.get("GLAZED_VOICE", "true").strip().lower() not in ("0", "false", "no", "off"))


def build_forecasters(env: dict[str, str]) -> list[Any]:
    """The Parquet forecast comes first when GLAZED_FORECAST_PATH points at an existing file; the baseline always
    follows, so a missing file never breaks the service and cases dated before the file's origin still get a forecast."""
    from datetime import date
    from ..driven.forecast import FileForecast, HOLDOUT_ORIGIN
    path = env.get("GLAZED_FORECAST_PATH", "")
    chain: list[Any] = []
    if path and os.path.isfile(path):
        origin = env.get("GLAZED_FORECAST_ORIGIN")
        chain.append(FileForecast(path, date.fromisoformat(origin) if origin else HOLDOUT_ORIGIN))
    return chain + [BaselineForecast()]


def build_classifier(env: dict[str, str], assistants: Any = None) -> Any:
    """Jev through Backboard first (account access is unverified), then the MiniMax fallback. A missing key only
    removes its adapter; with none configured every answer is the escape label."""
    from ..driven.classifiers import BackboardSystemOne, ChainClassifier, LLMFallback
    adapters: list[Any] = []
    if env.get("BACKBOARD_API_KEY"):
        adapters.append(BackboardSystemOne(env["BACKBOARD_API_KEY"], assistants=assistants))
    if env.get("MINIMAX_API_KEY"):
        adapters.append(LLMFallback(env["MINIMAX_API_KEY"], env.get("MINIMAX_API_BASE", "https://api.minimax.io/v1"),
                                    env.get("MINIMAX_CLASSIFIER_MODEL", "MiniMax-M3.1-flash-preview")))
    return ChainClassifier(adapters)


def create_app_from_env() -> FastAPI:
    return create_app(build_container())
