"""CorePort over Agent-Core's REST API.

Mapping: Core tenant = store_id; Core session_id = case_id (stored as case.core_conversation_id),
so a Core tool that knows its session id can send it as X-Glazed-Case.
Routes used: POST /turns (202), GET /turns/{id}, GET /admin/conversations/{session_id} (role admin).
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from ...domain import NotFound
from ...domain.models import CoreError


class AgentCoreHttp:
    """Identity per Agent-Core's Glazed vertical (VERTICAL_GLAZED.md): channel `glazed`, role `glazed-manager`
    (`glazed-service` for scheduled turns), tenant = store, session = case, profile `glazed_orchestrator`."""

    def __init__(self, base_url: str, profile_id: str = "glazed_orchestrator", subject_id: str = "manager-1",
                 timeout: float = 30.0, client: httpx.Client | None = None, channel: str = "glazed",
                 roles: str = "glazed-manager", service_roles: str = "glazed-service") -> None:
        self.profile_id, self.subject_id = profile_id, subject_id
        self.channel, self.roles, self.service_roles = channel, roles, service_roles
        self._c = client or httpx.Client(base_url=base_url, timeout=timeout)

    @classmethod
    def from_env(cls, base_url: str, env: dict[str, str]) -> "AgentCoreHttp":
        return cls(base_url, env.get("GLAZED_CORE_PROFILE", "glazed_orchestrator"),
                   env.get("GLAZED_CORE_SUBJECT", "manager-1"), channel=env.get("GLAZED_CORE_CHANNEL", "glazed"),
                   roles=env.get("GLAZED_CORE_ROLES", "glazed-manager"),
                   service_roles=env.get("GLAZED_CORE_SERVICE_ROLES", "glazed-service"))

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
