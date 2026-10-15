"""CorePort over Agent-Core's REST API.

Mapping: Core tenant = store_id; Core session_id = case_id (stored as case.core_conversation_id),
so a Core tool that knows its session id can send it as X-Glazed-Case.
Routes used: POST /turns (202), GET /turns/{id}, GET /turns/{id}/events (SSE, P5),
GET /admin/conversations/{session_id} (role admin).
"""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from ...domain import NotFound
from ...domain.models import CoreError


class _TurnNotYetKnown(Exception):
    """The events route answered 404 before any frame: the Core may not have the turn yet."""


class AgentCoreHttp:
    """Identity per Agent-Core's Glazed vertical (VERTICAL_GLAZED.md): channel `glazed`, role `glazed-manager`
    (`glazed-service` for scheduled turns), tenant = store, session = case, profile `glazed_orchestrator`."""

    # Every SSE stream holds one pooled connection for the length of a turn, out of the same pool sending and
    # polling use (httpx's default: 100). Past this many open streams a new one is refused at once and the turn is
    # polled instead, so streams can never take the connections the rest of the API needs.
    DEFAULT_MAX_STREAMS = 16

    def __init__(self, base_url: str, profile_id: str = "glazed_orchestrator", subject_id: str = "manager-1",
                 timeout: float = 30.0, client: httpx.Client | None = None, channel: str = "glazed",
                 roles: str = "glazed-manager", service_roles: str = "glazed-service",
                 max_streams: int = DEFAULT_MAX_STREAMS, sleep: Callable[[float], None] = time.sleep) -> None:
        if max_streams < 0:
            raise ValueError(f"max_streams must be at least 0, got {max_streams}")
        self.profile_id, self.subject_id = profile_id, subject_id
        self.channel, self.roles, self.service_roles = channel, roles, service_roles
        self.max_streams = max_streams
        self._streams = threading.BoundedSemaphore(max_streams) if max_streams else None
        self._c = client or httpx.Client(base_url=base_url, timeout=timeout)
        self._sleep = sleep

    @classmethod
    def from_env(cls, base_url: str, env: dict[str, str]) -> "AgentCoreHttp":
        return cls(base_url, env.get("GLAZED_CORE_PROFILE", "glazed_orchestrator"),
                   env.get("GLAZED_CORE_SUBJECT", "manager-1"), channel=env.get("GLAZED_CORE_CHANNEL", "glazed"),
                   roles=env.get("GLAZED_CORE_ROLES", "glazed-manager"),
                   service_roles=env.get("GLAZED_CORE_SERVICE_ROLES", "glazed-service"),
                   max_streams=int(env.get("GLAZED_CORE_MAX_STREAMS", cls.DEFAULT_MAX_STREAMS)))

    def _headers(self, store_id: str, admin: bool = False, service: bool = False) -> dict[str, str]:
        roles = self.service_roles if service else self.roles
        return {"X-Subject-Id": self.subject_id, "X-Tenant-Id": store_id, "X-Channel": self.channel,
                "X-Roles": f"{roles},admin" if admin else roles}

    def _call(self, method: str, url: str, store_id: str, admin: bool = False, service: bool = False,
              **kw: Any) -> httpx.Response:
        try:
            resp = self._c.request(method, url, headers=self._headers(store_id, admin, service), **kw)
        except httpx.HTTPError as exc:
            raise CoreError(f"Agent-Core unreachable: {exc}") from exc
        if resp.status_code == 404:
            raise NotFound(f"Agent-Core: {url} not found")
        if resp.status_code >= 400:
            raise CoreError(f"Agent-Core {resp.status_code} on {method} {url}: {resp.text[:200]}")
        return resp

    PROBE_PATH, PROBE_TIMEOUT_S = "/openapi.json", 2.0  # the Core has no /health or /profiles route: its schema is the cheap probe

    def health(self) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            resp = self._c.get(self.PROBE_PATH, timeout=self.PROBE_TIMEOUT_S)
        except httpx.HTTPError as exc:
            raise CoreError(f"Agent-Core unreachable: {exc}") from exc
        return {"ok": resp.status_code < 500, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}

    def create_conversation(self, case_id: str, store_id: str) -> str:
        return case_id  # the Core creates the session lazily on the first turn

    def send_turn(self, conversation_id: str, store_id: str, text: str, service: bool = False) -> str:
        body = {"session_id": conversation_id, "profile_id": self.profile_id, "text": text}
        return self._call("POST", "/turns", store_id, service=service, json=body).json()["turn_id"]

    def get_turn(self, turn_id: str, store_id: str) -> dict[str, Any]:
        return self._call("GET", f"/turns/{turn_id}", store_id).json()

    STREAM_TIMEOUT = httpx.Timeout(10.0, read=60.0)  # Core sends a keepalive comment on a quiet stream
    # Right after POST /turns the Core may not know the turn yet (its route step runs before the turn exists), so a
    # 404 on the events route is retried after each of these waits before the turn falls back to polling (L18: without
    # it every stream of the phase5 battery was refused and first_text was never measured). Other errors never retry.
    # About 3 s in all (L24): the route step (800 ms router deadline) and the queue pick-up come first, and a 1 s
    # window missed them after a restart, so the whole turn was shown only when it finished.
    STREAM_OPEN_RETRY_DELAYS_S: tuple[float, ...] = (0.15, 0.3, 0.6, 1.0, 1.0)

    def stream_turn(self, turn_id: str, store_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        """The turn's Server-Sent Events as (event, data) pairs, until the server closes the stream. Comments
        (keepalives) are skipped; an HTTP error raises CoreError (the caller then polls). Past `max_streams` open
        streams it raises CoreError before taking a connection; a closed or failed stream gives its slot back."""
        if self._streams is None or not self._streams.acquire(blocking=False):
            raise CoreError(f"Agent-Core stream refused: {self.max_streams} streams already open, polling instead")
        try:
            yield from self._events(turn_id, store_id)
        finally:
            self._streams.release()

    def _events(self, turn_id: str, store_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        for delay in self.STREAM_OPEN_RETRY_DELAYS_S:
            try:
                yield from self._events_once(turn_id, store_id)
                return
            except _TurnNotYetKnown:
                self._sleep(delay)
        try:
            yield from self._events_once(turn_id, store_id)
        except _TurnNotYetKnown as exc:
            raise CoreError(f"Agent-Core 404 on GET /turns/{turn_id}/events") from exc

    def _events_once(self, turn_id: str, store_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
        headers = {**self._headers(store_id), "Accept": "text/event-stream"}
        try:
            with self._c.stream("GET", f"/turns/{turn_id}/events", headers=headers,
                                timeout=self.STREAM_TIMEOUT) as resp:
                if resp.status_code == 404:
                    raise _TurnNotYetKnown(turn_id)
                if resp.status_code >= 400:
                    raise CoreError(f"Agent-Core {resp.status_code} on GET /turns/{turn_id}/events")
                event, data = "message", []
                for line in resp.iter_lines():
                    if not line:
                        if data:
                            yield event, json.loads("\n".join(data))
                        event, data = "message", []
                    elif line.startswith(":"):
                        continue
                    elif line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].strip())
                if data:
                    yield event, json.loads("\n".join(data))
        except httpx.HTTPError as exc:
            raise CoreError(f"Agent-Core stream unreachable: {exc}") from exc

    def list_transcript(self, conversation_id: str, store_id: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            page = self._call("GET", f"/admin/conversations/{conversation_id}", store_id, admin=True,
                              params=params).json()
            entries.extend(page.get("entries", []))
            cursor = page.get("next_cursor")
            if not page.get("has_more") or not cursor:
                return entries
