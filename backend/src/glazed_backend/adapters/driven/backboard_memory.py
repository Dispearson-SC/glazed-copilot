"""ExperienceMemoryPort over Backboard (backboard-sdk, async).

One assistant per store, created lazily; its id is persisted in an AssistantRepository.
Only explicit add_memory / search_memories are used. memory="Auto" is never used.
Any failure (missing key, 429 after backoff, network) raises MemoryUnavailable so callers degrade.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any, Callable

from ...domain import Experience
from ...domain.models import MemoryUnavailable, utcnow

BACKOFF = (0.5, 1.0, 2.0)


class BackboardMemory:
    def __init__(self, api_key: str, assistants: Any, client_factory: Callable[[], Any] | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 display_name: Callable[[str], str] | None = None) -> None:
        self.api_key, self.assistants, self._sleep = api_key, assistants, sleep
        self._display = display_name or (lambda store_id: store_id)
        self._factory = client_factory or self._default_client

    def _default_client(self) -> Any:
        from backboard import BackboardClient
        return BackboardClient(api_key=self.api_key)

    async def _assistant_id(self, client: Any, store_id: str) -> str:
        known = self.assistants.get(store_id)
        if known:
            return known
        created = await client.create_assistant(
            name=self._assistant_name(store_id),
            description=f"Experience memory for store {store_id}",
            system_prompt="Stores decision and outcome experiences for one Glazed store. Not a source of numbers.")
        aid = str(created.assistant_id)
        self.assistants.set(store_id, aid)
        return aid

    def _assistant_name(self, store_id: str) -> str:
        return f"Glazed · {self._display(store_id)}"

    def rename(self, store_id: str) -> str | None:
        """Give an existing store assistant its display-name label. None when it has no assistant yet."""
        aid = self.assistants.get(store_id)
        if not aid:
            return None
        name = self._assistant_name(store_id)

        async def op(client: Any) -> None:
            await client.update_assistant(aid, name=name)

        self._run(op)
        return name

    def _run(self, op: Callable[[Any], Any]) -> Any:
        if not self.api_key:
            raise MemoryUnavailable("BACKBOARD_API_KEY missing")
        from backboard.exceptions import BackboardRateLimitError
        for attempt in range(len(BACKOFF) + 1):
            try:
                return asyncio.run(op(self._factory()))
            except BackboardRateLimitError as exc:
                if attempt == len(BACKOFF):
                    raise MemoryUnavailable(f"Backboard rate limited (429): {exc}") from exc
                self._sleep(BACKOFF[attempt])
            except MemoryUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001 - degrade on any provider failure
                raise MemoryUnavailable(f"Backboard error: {type(exc).__name__}: {exc}") from exc
        raise MemoryUnavailable("Backboard unavailable")

    def remember(self, store_id: str, experience: Experience) -> None:
        meta = {"store_id": store_id, "kind": experience.kind, "created_at": experience.created_at.isoformat()}
        if experience.decision_id:
            meta["decision_id"] = experience.decision_id
        if experience.ref:
            meta["ref"] = experience.ref

        async def op(client: Any) -> None:
            aid = await self._assistant_id(client, store_id)
            await client.add_memory(aid, experience.text, meta)

        self._run(op)

    def recall(self, store_id: str, query: str, limit: int = 5) -> list[Experience]:
        async def op(client: Any) -> dict:
            aid = await self._assistant_id(client, store_id)
            return await client.search_memories(aid, query, limit)

        res = self._run(op)
        out = []
        for m in (res or {}).get("memories", []):
            meta = m.get("metadata") or {}
            raw = m.get("created_at") or meta.get("created_at")
            try:
                created = datetime.fromisoformat(str(raw)) if raw else utcnow()
            except ValueError:
                created = utcnow()
            out.append(Experience(m.get("content", ""), meta.get("kind", "memory"), store_id,
                                  meta.get("decision_id"), created, m.get("score"), meta.get("ref")))
        return out
