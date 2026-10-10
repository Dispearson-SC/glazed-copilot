"""Thin HTTP client for the backend public API (/api/v1)."""
from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_URL = "http://localhost:8080"
# Tests inject an httpx.MockTransport here.
TRANSPORT: httpx.BaseTransport | None = None


class CliError(Exception):
    """An error to show to the user as a single line."""


class ApiError(CliError):
    pass


class BackendDown(CliError):
    pass


def resolve_url(flag: str | None) -> str:
    return flag or os.environ.get("GLAZED_API_URL") or DEFAULT_URL


class Api:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None,
                 timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, transport=transport or TRANSPORT,
                                  timeout=timeout)

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        try:
            resp = self._http.request(method, path, **kw)
        except httpx.TransportError as exc:
            raise BackendDown(
                f"Cannot reach the backend at {self.base_url} ({type(exc).__name__}). "
                "Is it running? Set GLAZED_API_URL or use --api.") from None
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise ApiError(f"{resp.status_code}: {detail}")
        return resp.json()

    def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=clean)

    def post(self, path: str, body: dict | None = None) -> Any:
        return self._request("POST", path, json=body or {})

    def patch(self, path: str, body: dict) -> Any:
        return self._request("PATCH", path, json=body)
