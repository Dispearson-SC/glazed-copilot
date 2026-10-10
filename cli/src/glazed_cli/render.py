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


def alerts_table(alerts: list[dict], title: str = "Alerts") -> Table:
    return table(title, ["alert_id", "type", "store", "severity_usd", "state", "as_of", "issue_key"], (
        [a["alert_id"], a.get("alert_type"), a.get("store_id"), a.get("severity_usd"), a.get("state"),
         a.get("as_of"), a.get("issue_key")] for a in alerts))


def proposals_table(items: list[dict], title: str = "Proposals") -> Table:
    return table(title, ["proposal_id", "action", "tier", "status", "params", "rationale"], (
        [p["proposal_id"], p.get("action_type"), p.get("tier"), p.get("status"), p.get("params"),
         p.get("rationale")] for p in items))


_AGENT_COLORS = {
    "orchestrator": "bright_white", "present": "green", "past": "blue", "supply": "yellow",
    "strategist": "magenta", "sentinel": "red", "auditor": "cyan", "liaison": "bright_blue",
    "backend": "bright_black", "manager": "bright_green",
}
_FALLBACK = ["orange3", "purple", "turquoise2", "pink3", "gold3", "spring_green3"]


def agent_color(agent: str) -> str:
    if agent in _AGENT_COLORS:
        return _AGENT_COLORS[agent]
    return _FALLBACK[sum(map(ord, agent)) % len(_FALLBACK)]


def short_payload(payload: Any, limit: int = 100) -> str:
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        text = payload["text"]
    else:
        text = json.dumps(payload, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def trace_table(events: list[dict]) -> Table:
    t = Table(title="Agent trace", title_justify="left")
    for col in ("time", "from -> to", "kind", "payload"):
        t.add_column(col, overflow="fold")
    for e in events:
        a, b = e["from_agent"], e["to_agent"]
        t.add_row(str(e["ts"])[11:19] or str(e["ts"]),
                  f"[{agent_color(a)}]{a}[/] -> [{agent_color(b)}]{b}[/]",
                  e["kind"], short_payload(e.get("payload")))
    return t


_METRICS = [("waste_usd", "Waste ($)"), ("lost_sales_usd", "Lost sales ($)"), ("net_usd", "Net ($)")]


def backtest_report(run: dict, out: Console) -> None:
    res = dict(run.get("results") or {})
    base = res.pop("baseline", None) or {}
    out.print(f"[bold]BACKTEST[/bold] run {run['run_id']}  store={run['store_id']}  "
              f"{run['period_from']} .. {run['period_to']}  policy={run.get('policy') or 'default'}  "
              f"(label: {run.get('label', 'backtest')} - simulated, not real operations)")
    t = Table(title="Backtest vs current practice", title_justify="left")
    for col in ("metric", "backtest", "current practice", "improvement"):
        t.add_column(col, justify="right" if col != "metric" else "left")
    for key, label in _METRICS:
        if key not in res:
            continue
        mine, theirs = res.pop(key), base.get(key)
        if theirs is None:
            t.add_row(label, fmt(mine), "-", "-")
            continue
        # Lower waste/lost sales is better; higher net is better.
        gain = (mine - theirs) if key == "net_usd" else (theirs - mine)
        t.add_row(label, fmt(mine), fmt(theirs), f"{gain:+,.2f}")
    out.print(t)
    if res:
        render_object("Other results", res, out)
