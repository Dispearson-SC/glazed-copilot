"""Follow a Core turn's Server-Sent Events (`GET /turns/{id}/events`) instead of polling it for its text.

One `StreamState` per turn the backend started: the reply text the turn has streamed so far (the snapshot's
`reply_text`, then its `delta` events), when the first text arrived, and whether the turn is over. Only the ROOT
turn's text counts: a peer's deltas never reach the manager. The stream is a speedup, never the authority: the
final reply is still read once from `GET /turns/{id}` (sanitizing, rewrite) and any failure of the stream marks it
`broken`, which sends `GetTurn` back to plain polling.

A delta's `detail` is the Core's chunk identity `<run>:<response>:<index>`: a chunk of another run or response starts
the text over (the model answered again after a tool call, a retried step, or the Core taking a cut draft back with
ONE empty chunk before the turn falls back, P11). The first-text time stays the first chunk's.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..ports import Clock

_TERMINAL_STATES = ("finished", "failed")


@dataclass
class StreamState:
    text: str = ""
    first_text_at: datetime | None = None
    finished: bool = False  # the root turn ended (or the whole tree settled): read the final reply once
    broken: bool = False  # the stream failed or ended early: poll instead
    checked_at: datetime | None = None  # the last time GetTurn asked the Core for the status itself
    chunk: tuple[str, str] | None = None  # (run, response) of the text held; None: unknown (start, after a snapshot)

    @property
    def live(self) -> bool:
        return not self.finished and not self.broken


def _spawn_daemon(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="core-turn-stream", daemon=True).start()


class TurnStreams:
    """In-process registry of turn streams (bounded: the oldest are forgotten past `max_tracked`)."""

    def __init__(self, core: Any, clock: Clock, spawn: Callable[[Callable[[], None]], None] = _spawn_daemon,
                 max_tracked: int = 500) -> None:
        self.core, self.clock, self.spawn, self.max_tracked = core, clock, spawn, max_tracked
        self._states: dict[str, StreamState] = {}
        self._lock = threading.Lock()

    def watch(self, turn_id: str, store_id: str) -> None:
        """Start following `turn_id` in the background. A Core adapter without `stream_turn` is a no-op."""
        stream = getattr(self.core, "stream_turn", None)
        if stream is None:
            return
        self.begin(turn_id)
        self.spawn(lambda: self._consume(turn_id, stream(turn_id, store_id)))

    def begin(self, turn_id: str) -> StreamState:
        with self._lock:
            state = self._states.setdefault(turn_id, StreamState())
            while len(self._states) > self.max_tracked:
                self._states.pop(next(iter(self._states)))
            return state

    def state(self, turn_id: str) -> StreamState | None:
        return self._states.get(turn_id)

    def forget(self, turn_id: str) -> None:
        with self._lock:
            self._states.pop(turn_id, None)

    def _consume(self, turn_id: str, events: Iterator[tuple[str, dict[str, Any]]]) -> None:
        try:
            for kind, data in events:
                self.feed(turn_id, kind, data)
                state = self.state(turn_id)
                if state is None or not state.live:
                    return
        except Exception:  # noqa: BLE001 - a broken stream only means GetTurn polls
            self._mark_broken(turn_id)
            return
        finally:  # close now, not when collected: closing gives the stream's connection (and capped slot) back
            close = getattr(events, "close", None)
            try:
                if close is not None:
                    close()
            except Exception:  # noqa: BLE001 - the turn is followed by polling either way
                pass
        self._mark_broken(turn_id)  # the server closed without saying the turn ended: poll

    def _mark_broken(self, turn_id: str) -> None:
        state = self.state(turn_id)
        if state is not None and not state.finished:
            state.broken = True

    def feed(self, turn_id: str, kind: str, data: dict[str, Any]) -> None:
        """Apply one SSE frame (`kind` is its `event:` name, `data` its JSON) to the turn's state."""
        state = self.state(turn_id)
        if state is None or not isinstance(data, dict):
            return
        if kind == "snapshot":
            for turn in data.get("turns") or []:
                if isinstance(turn, dict) and turn.get("turn_id") == turn_id:
                    if isinstance(turn.get("reply_text"), str):  # the whole text so far, a withdrawn "" included
                        self._text(state, turn["reply_text"], replace=True)
                        state.chunk = None
                    if turn.get("state") in _TERMINAL_STATES:
                        state.finished = True
        elif kind == "delta":
            if data.get("turn_id") == turn_id and isinstance(data.get("text"), str):
                self._text(state, data["text"], replace=self._starts_over(state, data.get("detail")))
        elif kind in _TERMINAL_STATES:
            if data.get("turn_id") == turn_id:
                state.finished = True
        elif kind == "end":
            state.finished = True
        elif kind == "error":
            state.broken = True

    @staticmethod
    def _starts_over(state: StreamState, detail: Any) -> bool:
        """Whether a delta's chunk replaces the text held: it belongs to another (run, response). After a snapshot
        (which holds the latest response whole) a later chunk of it appends; a first chunk of a new one replaces."""
        parts = detail.split(":") if isinstance(detail, str) else []
        if len(parts) != 3 or not parts[2].isdigit():
            return False  # not a chunk identity: append, as before
        which = (parts[0], parts[1])
        known, state.chunk = state.chunk, which
        if known is None:
            return int(parts[2]) == 0
        return which != known

    def _text(self, state: StreamState, text: str, replace: bool) -> None:
        state.text = text if replace else state.text + text
        if state.first_text_at is None and text:
            state.first_text_at = self.clock.now()
