"""Local CLI state: which case is current. Stored in ~/.glazed/state.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def state_path() -> Path:
    override = os.environ.get("GLAZED_STATE")
    return Path(override) if override else Path.home() / ".glazed" / "state.json"


@dataclass
class State:
    current_case: str | None = None

    @classmethod
    def load(cls) -> "State":
        try:
            data = json.loads(state_path().read_text())
            return cls(current_case=data.get("current_case"))
        except (OSError, ValueError, AttributeError):
            return cls()

    def save(self) -> None:
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"current_case": self.current_case}, indent=2))
