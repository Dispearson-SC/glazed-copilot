"""Export the internal API's OpenAPI contract: the snapshot Agent-Core builds its glazed tools from.

Usage (from backend/):
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py            # rewrite the snapshot
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py --check    # exit 1 if stale/diverged

The snapshot (tests/fixtures/internal_openapi.json) is the OpenAPI document of an application that
mounts only the /internal/v1 routes, so a change to the public API does not move it. Copy it to
Agent-Core's Core/tests/fixtures/glazed_tools/ after a deliberate change to the marks or the routes.

Agent-Core reads the SERVED document (`/openapi.json` of the whole application), not the snapshot.
The two are not byte-equal (FastAPI qualifies an internal schema name a public model also uses), so
`--check` also compares the internal operations of the served document with the snapshot's, every
`$ref` resolved (`served_divergence`): what the tools are built from must be the same.
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


def _resolved(node: Any, spec: dict[str, Any], seen: tuple[str, ...] = ()) -> Any:
    """`node` with each `#/components/schemas/X` reference replaced by X (a cycle stays a ref)."""
    if isinstance(node, list):
        return [_resolved(item, spec, seen) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/") and len(node) == 1:
        name = ref.rsplit("/", 1)[1]
        target = spec.get("components", {}).get("schemas", {}).get(name)
        if target is None or name in seen:
            return node
        return _resolved(target, spec, (*seen, name))
    return {key: _resolved(value, spec, seen) for key, value in node.items()}


def internal_operations(spec: dict[str, Any]) -> dict[str, Any]:
    """The /internal/v1 paths of `spec`, every schema reference resolved."""
    return {
        path: _resolved(item, spec)
        for path, item in spec.get("paths", {}).items()
        if path.startswith(PREFIX)
    }


def served_divergence(served: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    """The internal paths whose operations differ between the served document and the snapshot
    (missing on either side included), sorted; `[]` when Agent-Core sees the snapshot's contract."""
    ours, theirs = internal_operations(served), internal_operations(snapshot)
    return sorted(p for p in ours.keys() | theirs.keys() if ours.get(p) != theirs.get(p))


def _served() -> dict[str, Any]:
    """The document the service serves at /openapi.json, public routes included."""
    from glazed_backend.adapters.driving.app import create_app
    from tests.unit.test_forecast_internal import make_container  # in-memory fakes

    spec: dict[str, Any] = create_app(make_container()).openapi()
    return spec


def _current() -> dict[str, Any]:
    from glazed_backend.adapters.driving.app import create_app
    from tests.unit.test_forecast_internal import make_container  # in-memory fakes

    container = make_container()
    create_app(container)  # completes the container (briefings, sessions) as the service does
    return internal_spec(container)


def main(argv: list[str]) -> int:
    current = _current()
    text = json.dumps(current, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    diverged = served_divergence(_served(), current)
    if diverged:
        print(
            "the served /openapi.json differs from the internal contract at: " + ", ".join(diverged),
            file=sys.stderr,
        )
        return 1
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
