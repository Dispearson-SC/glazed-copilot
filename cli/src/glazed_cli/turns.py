"""Post a message and poll its turn until it settles."""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from glazed_cli.client import Api, CliError

TERMINAL = ("done", "failed", "waiting_approval")


def poll_interval() -> float:
    return float(os.environ.get("GLAZED_POLL_INTERVAL", "1.0"))


def ask(api: Api, case_id: str, text: str, timeout: float,
        on_wait: Callable[[], Any] | None = None) -> dict:
    turn_id = api.post(f"/api/v1/cases/{case_id}/messages", {"text": text})["turn_id"]
    deadline = time.monotonic() + timeout
    while True:
        turn = api.get(f"/api/v1/cases/{case_id}/turns/{turn_id}")
        if turn["status"] in TERMINAL:
            return turn
        if time.monotonic() >= deadline:
            raise CliError(f"Timed out after {timeout:g}s waiting for turn {turn_id} "
                           f"(case {case_id}); it may still finish on the backend.")
        time.sleep(poll_interval())
