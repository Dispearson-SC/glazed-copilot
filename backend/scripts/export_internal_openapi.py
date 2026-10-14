"""Export the internal API's OpenAPI contract: the snapshot Agent-Core builds its glazed tools from.

Usage (from backend/):
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py            # rewrite the snapshot
  PYTHONPATH=.deps:src python3 scripts/export_internal_openapi.py --check    # exit 1 if it is stale

The snapshot (tests/fixtures/internal_openapi.json) holds only the /internal/v1 paths and the schemas
they reference, so a change to the public API does not move it. Copy it to Agent-Core's
Core/tests/fixtures/glazed_tools/ after a deliberate change to the marks or to the internal routes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SNAPSHOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "internal_openapi.json"
PREFIX = "/internal/v1"


def _refs(node: Any) -> set[str]:
    if isinstance(node, dict):
        found = {node["$ref"].rsplit("/", 1)[-1]} if isinstance(node.get("$ref"), str) else set()
        return found.union(*(_refs(v) for v in node.values())) if node else found
    if isinstance(node, list):
        return set().union(*(_refs(v) for v in node)) if node else set()
    return set()


def internal_contract(spec: dict[str, Any]) -> dict[str, Any]:
    """The internal paths of a full OpenAPI document plus the schemas they (transitively) use."""
    paths = {p: item for p, item in spec["paths"].items() if p.startswith(PREFIX)}
    schemas: dict[str, Any] = spec.get("components", {}).get("schemas", {})
    needed: set[str] = set()
    todo = _refs(paths)
    while todo:
        name = todo.pop()
        if name in needed or name not in schemas:
            continue
        needed.add(name)
        todo |= _refs(schemas[name])
    contract: dict[str, Any] = {"openapi": spec["openapi"], "info": spec["info"], "paths": paths}
    if needed:
        contract["components"] = {"schemas": {n: schemas[n] for n in sorted(needed)}}
    return contract


def _current() -> dict[str, Any]:
    from tests.unit.test_forecast_internal import build  # the app with in-memory fakes

    client, _ = build()
    return internal_contract(client.get("/openapi.json").json())


def main(argv: list[str]) -> int:
    text = json.dumps(_current(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if "--check" in argv:
        return 0 if SNAPSHOT.read_text(encoding="utf-8") == text else 1
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv[1:]))
