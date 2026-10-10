"""Post a message and poll its turn until it settles."""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from glazed_cli.client import Api, ApiError, CliError

TERMINAL = ("done", "failed", "waiting_approval")


def poll_interval() -> float:
    return float(os.environ.get("GLAZED_POLL_INTERVAL", "1.0"))


PROGRESS_EVERY = 15.0


def ask(api: Api, case_id: str, text: str, timeout: float,
        on_wait: Callable[[], Any] | None = None, on_progress: Callable[[], Any] | None = None,
        progress_every: float = PROGRESS_EVERY) -> dict:
    turn_id = api.post(f"/api/v1/cases/{case_id}/messages", {"text": text})["turn_id"]
    start = time.monotonic()
    deadline = start + timeout
    last_beat = start
    while True:
        try:
            turn = api.get(f"/api/v1/cases/{case_id}/turns/{turn_id}")
        except ApiError as exc:
            # The Core answers 404 while the turn is queued behind another one in the conversation.
            if not str(exc).startswith("404"):
                raise
            turn = {"status": "pending"}
        if turn["status"] in TERMINAL:
            return turn
        now = time.monotonic()
        if now >= deadline:
            raise CliError(f"Timed out after {timeout:g}s waiting for turn {turn_id} "
                           f"(case {case_id}); it may still finish on the backend.")
        if on_progress and now - last_beat >= progress_every:
            last_beat = now
            on_progress()
        time.sleep(poll_interval())
