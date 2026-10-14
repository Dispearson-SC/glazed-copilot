"""Export the internal API's OpenAPI contract: the snapshot Agent-Core builds its glazed tools from.

Usage (from backend/):
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py            # rewrite the snapshot
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py --check    # exit 1 if it is stale

The snapshot (tests/fixtures/internal_openapi.json) is the OpenAPI document of an application that
mounts only the /internal/v1 routes, so a change to the public API does not move it. Copy it to Agent-Core's
Core/tests/fixtures/glazed_tools/ after a deliberate change to the marks or to the internal routes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SNAPSHOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "internal_openapi.json"
PREFIX = "/internal/v1"
INTERNAL_VERSION = "1"


def internal_spec(container: Any) -> dict[str, Any]:
    """The OpenAPI document of the INTERNAL router alone, mounted on a fresh application.

    Nothing public (a route, a schema, the application's title or version) can move the snapshot.
    """
    from fastapi import FastAPI

    from glazed_backend.adapters.driving.internal_api import build_internal_router

    internal = FastAPI(title="glazed-internal-api", version=INTERNAL_VERSION)
    internal.include_router(build_internal_router(container))
    spec: dict[str, Any] = internal.openapi()
    return spec


def _current() -> dict[str, Any]:
    from glazed_backend.adapters.driving.app import create_app
    from tests.unit.test_forecast_internal import make_container  # in-memory fakes

    container = make_container()
    create_app(container)  # completes the container (briefings, sessions) as the service does
    return internal_spec(container)


def main(argv: list[str]) -> int:
    text = json.dumps(_current(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if "--check" in argv:
        if not SNAPSHOT.is_file():
            print(f"snapshot missing: {SNAPSHOT} (run without --check to create it)", file=sys.stderr)
            return 1
        if SNAPSHOT.read_text(encoding="utf-8") != text:
            print(f"snapshot stale: {SNAPSHOT} (run without --check to rewrite it)", file=sys.stderr)
            return 1
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv[1:]))
