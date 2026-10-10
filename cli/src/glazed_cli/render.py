"""Terminal rendering helpers (rich). Output is English; data passes through as-is."""
from __future__ import annotations

import json
from typing import Any, Iterable

from rich.console import Console
from rich.table import Table


def console() -> Console:
    # Created per call so tests capturing stdout see the output.
    return Console(highlight=False)


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def table(title: str, columns: Iterable[str], rows: Iterable[Iterable[Any]]) -> Table:
    t = Table(title=title, title_justify="left")
    for c in columns:
        t.add_column(c)
    for row in rows:
        t.add_row(*[fmt(v) for v in row])
    return t


def records_table(title: str, records: list[dict], columns: list[str] | None = None) -> Table:
    cols = columns or list(dict.fromkeys(k for r in records for k in r))
    return table(title, cols, ([r.get(c) for c in cols] for r in records))


def render_object(title: str, obj: dict, out: Console) -> None:
    """Generic view: scalars as key/value, lists of dicts as their own tables."""
    scalars = {k: v for k, v in obj.items() if not _is_records(v) and not isinstance(v, dict)}
    out.print(table(title, ["field", "value"], scalars.items()))
    for key, value in obj.items():
        if _is_records(value):
            out.print(records_table(key, value))
        elif isinstance(value, dict):
            render_object(key, value, out)


def _is_records(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(i, dict) for i in v)


def case_table(cases: list[dict], current: str | None) -> Table:
    return table("Cases", ["", "case_id", "store", "sim_today", "mode", "parent", "title"], (
        ["*" if c["case_id"] == current else "", c["case_id"], c["store_id"], c["sim_today"],
         c["mode"], c.get("parent_case_id"), c.get("title")] for c in cases))
