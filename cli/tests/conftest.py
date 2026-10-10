"""Shared fixtures: a fake backend speaking the public API contract."""
from __future__ import annotations

import json

import httpx
import pytest

from glazed_cli import client as client_mod

CASE = {
    "case_id": "c1", "store_id": "S030", "sim_today": "2026-03-10", "mode": "live",
    "parent_case_id": None, "core_conversation_id": "conv1",
    "title": "S030 2026-03-10", "created_at": "2026-10-10T10:00:00Z",
}


class FakeApi:
    """Records requests and answers from a (method, path) -> response table."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], object] = {}

    def on(self, method: str, path: str, body: object, status: int = 200) -> None:
        """body may be a value or a list (consumed in order, last one repeats)."""
        self.routes[(method, path)] = (status, body)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        key = (request.method, request.url.path)
        if key not in self.routes:
            return httpx.Response(404, json={"detail": f"no route {key}"})
        status, body = self.routes[key]
        if isinstance(body, list):
            item = body.pop(0) if len(body) > 1 else body[0]
        else:
            item = body
        return httpx.Response(status, json=item)

    def last(self) -> httpx.Request:
        return self.calls[-1]

    def last_json(self) -> dict:
        return json.loads(self.last().content)


@pytest.fixture
def api(monkeypatch, tmp_path):
    fake = FakeApi()
    monkeypatch.setattr(client_mod, "TRANSPORT", httpx.MockTransport(fake.handler))
    monkeypatch.setenv("GLAZED_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("GLAZED_API_URL", "http://backend.test")
    monkeypatch.setenv("GLAZED_POLL_INTERVAL", "0")
    monkeypatch.setenv("NO_COLOR", "1")
    return fake
