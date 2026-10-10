"""Store display names for user-facing payloads. store_id stays the internal key."""
from typing import Any


class StoreNames:
    """display_name = "<site_name> · <store_name>": store_name alone repeats across sites."""

    def __init__(self, metrics: Any) -> None:
        self._metrics, self._names = metrics, None

    def of(self, store_id: str) -> str:
        if self._names is None:
            try:
                self._names = {s["store_id"]: s.get("display_name") or s["name"] for s in self._metrics.stores()}
            except Exception:  # noqa: BLE001 - names are cosmetic: never fail a request over them
                return store_id
        return self._names.get(store_id, store_id)

    def tag(self, payload: Any, store_id: str | None = None) -> Any:
        """Add store_display_name to a dict, or to every dict of a list (keyed by its store_id)."""
        if isinstance(payload, list):
            return [self.tag(p, store_id) for p in payload]
        if isinstance(payload, dict):
            sid = payload.get("store_id") or store_id
            if sid:
                return {**payload, "store_display_name": self.of(sid)}
        return payload
