"""One-call views for agents: the store snapshot and (later) the briefing, built by composing metrics and use cases.

The metrics part of a snapshot is deterministic for a (case, simulated day), so it is cached; pending proposals and
recent decisions change within a day and are always read live.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from ..domain import Case

log = logging.getLogger(__name__)

WINDOW_DAYS = 7
MAX_ISSUES, MAX_INTEGRITY, MAX_LINES, MAX_EVIDENCE, MAX_DECISIONS, MAX_PENDING = 5, 3, 5, 3, 5, 10
_ISSUE_DROP = ("as_of_date", "engine_version", "store_id", "store_display_name")
_CONFIDENCE_KEEP = ("score", "n_backtest", "noise_capped")  # replay internals (effect mean, noise floor) stay out
_LINE_KEEP = ("sku", "name", "supplier_id", "supplier_name", "qty", "cases", "est_cost_usd", "expected_delivery",
              "projected_stockout_date", "order_deadline", "order_deadline_status", "stockout_risk_without_order")
_PROPOSAL_KEEP = ("proposal_id", "case_id", "issue_id", "action_type", "params", "tier", "status", "reason",
                  "agent_id")


def _mid(d: Any) -> float:
    return float((d or {}).get("mid") or 0.0) if isinstance(d, dict) else 0.0


def trim_issue(issue: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in issue.items() if k not in _ISSUE_DROP}
    out["evidence"] = list(issue.get("evidence") or [])[:MAX_EVIDENCE]
    opts = []
    for o in issue.get("options") or []:
        o = dict(o)
        if isinstance(o.get("confidence"), dict):
            o["confidence"] = {k: v for k, v in o["confidence"].items() if k in _CONFIDENCE_KEEP}
        o.pop("tier_reasons", None)
        opts.append(o)
    out["options"] = opts
    return out


def trim_line(line: dict[str, Any]) -> dict[str, Any]:
    out = {k: line.get(k) for k in _LINE_KEEP}
    out["expected_loss_usd"] = round(_mid(line.get("expected_waste_usd")) + _mid(line.get("expected_lost_sales_usd")), 2)
    out["below_min_order"] = bool(line.get("min_order_warning"))
    if isinstance(line.get("issue"), dict):
        out["issue_id"] = line["issue"].get("issue_id")
    return out


def _trim_proposal(p: Any, scope: str) -> dict[str, Any]:
    return {**{k: getattr(p, k) for k in _PROPOSAL_KEEP}, "created_at": p.created_at.isoformat(), "scope": scope}


class SnapshotBuilder:
    """Composes MetricsPort reads into the snapshot payload. `served` receives the full issues so that an agent can
    propose one of the snapshot's options without calling /issues first."""

    def __init__(self, metrics: Any, proposals: Any, name_of: Callable[[str], str], served: dict) -> None:
        self.metrics, self.proposals, self.name_of, self.served = metrics, proposals, name_of, served

    def core(self, case: Case) -> dict[str, Any]:
        sid, as_of = case.store_id, case.sim_today
        start = as_of - timedelta(days=WINDOW_DAYS - 1)
        k = self.metrics.kpis(sid, as_of, start, as_of)
        pool = self.metrics.issues(sid, as_of, 10_000)
        ops = sorted((i for i in pool if i.get("category") != "integrity"), key=lambda i: -float(i.get("severity_usd") or 0))
        integ = sorted((i for i in pool if i.get("category") == "integrity"), key=lambda i: -float(i.get("exposure_usd") or 0))
        for i in ops[:MAX_ISSUES]:
            self.served[(case.case_id, i["issue_id"])] = i
        plan = self.metrics.order_plan(sid, as_of)
        lines = plan.get("lines", [])
        for ln in lines:
            if isinstance(ln.get("issue"), dict):
                self.served[(case.case_id, ln["issue"]["issue_id"])] = ln["issue"]
        trimmed = [trim_line(ln) for ln in lines]
        today, tomorrow = as_of.isoformat(), (as_of + timedelta(days=1)).isoformat()
        return {
            "store_id": sid, "store_display_name": self.name_of(sid), "as_of": as_of.isoformat(),
            "window": {"from": start.isoformat(), "to": as_of.isoformat()},
            "kpis": {n: k.get(n) for n in ("net_sales", "transactions", "waste_usd", "lost_sales_usd", "tx_per_staff_hour")},
            "top_issues": [trim_issue(i) for i in ops[:MAX_ISSUES]],
            "integrity": [{"issue_id": i["issue_id"], "kind": i.get("kind"), "sku": i.get("sku"),
                           "exposure_usd": i.get("exposure_usd"),
                           "summary": (i.get("data_caveats") or [f"{i.get('kind')} {i.get('sku') or ''}".strip()])[0]}
                          for i in integ[:MAX_INTEGRITY]],
            "order_plan": {
                "due_today": [t for t in trimmed if t["order_deadline"] == today],
                "due_tomorrow": [t for t in trimmed if t["order_deadline"] == tomorrow],
                "top_lines": sorted(trimmed, key=lambda t: -t["expected_loss_usd"])[:MAX_LINES],
                "total_lines": plan.get("total_lines", len(lines)),
                "deadline_passed": sum(1 for t in trimmed if t["order_deadline_status"] == "deadline_passed")},
            "suppliers": [{"supplier_id": s["supplier_id"], "supplier_name": s.get("supplier_name"),
                           "on_time_pct": s.get("on_time_pct"), "fill_pct": s.get("fill_pct"),
                           "next_delivery": s.get("next_delivery")}
                          for s in self.metrics.supplier_performance(sid, as_of)],
        }

    def live(self, case: Case) -> dict[str, Any]:
        """Case-scoped records first, then the rest of the store's, each tagged with its scope."""
        mine = self.proposals.list(case_id=case.case_id)
        rest = [p for p in self.proposals.list(store_id=case.store_id) if p.case_id != case.case_id]
        tagged = [(p, "case") for p in mine] + [(p, "store") for p in rest]
        pending = [_trim_proposal(p, s) for p, s in tagged if p.status == "pending"][:MAX_PENDING]
        decided = sorted(((p, s) for p, s in tagged if p.status in ("approved", "rejected")),
                         key=lambda t: (t[1] != "case", -t[0].created_at.timestamp()))
        return {"pending_proposals": pending,
                "recent_decisions": [_trim_proposal(p, s) for p, s in decided[:MAX_DECISIONS]]}


def _money(x: float) -> str:
    return f"${x:,.0f}"


def headline(core: dict[str, Any]) -> list[dict[str, Any]]:
    """At most five facts, computed from the snapshot by code so that no model has to derive them."""
    kp, out = core["kpis"], []
    if kp.get("waste_usd") is not None:
        out.append({"key": "waste_7d", "text": f"Merma 7 días {_money(kp['waste_usd'])}", "value": kp["waste_usd"],
                    "unit": "USD", "source": "kpis"})
    ls = kp.get("lost_sales_usd") or {}
    if ls:
        out.append({"key": "lost_sales", "text": f"Venta perdida estimada {_money(ls['low'])}–{_money(ls['high'])}",
                    "value": ls["mid"], "unit": "USD", "source": "kpis.lost_sales_usd", "low": ls["low"], "high": ls["high"]})
    due = len(core["order_plan"]["due_today"])
    out.append({"key": "orders_due_today", "text": f"{due} pedidos vencen hoy", "value": due, "unit": "pedidos",
                "source": "order_plan"})
    sups = [s for s in core["suppliers"] if s.get("on_time_pct") is not None]
    if sups:
        w = min(sups, key=lambda s: s["on_time_pct"])
        out.append({"key": "worst_supplier",
                    "text": f"Proveedor con menor puntualidad: {w.get('supplier_name') or w['supplier_id']} "
                            f"({w['on_time_pct']:.1f}%)", "value": w["on_time_pct"], "unit": "%",
                    "source": "suppliers.performance"})
    if core["top_issues"]:
        t = core["top_issues"][0]
        label = " ".join(x for x in (t.get("product_name") or t.get("sku"), t.get("kind")) if x)
        out.append({"key": "top_issue", "text": f"Mayor problema: {label} ({_money(float(t.get('severity_usd') or 0))})",
                    "value": t.get("severity_usd"), "unit": "USD", "source": "issues", "issue_id": t["issue_id"]})
    return out[:5]


def suggested_focus(core: dict[str, Any]) -> list[str]:
    ids = [i["issue_id"] for i in core["top_issues"][:3]]
    return ids + [i["issue_id"] for i in core["integrity"][:1]]


@dataclass
class _Entry:
    core: dict[str, Any]
    generated_at: datetime
    headline: list[dict[str, Any]]
    focus: list[str]


class BriefingService:
    def __init__(self, builder: SnapshotBuilder, clock: Any, cases: Any = None, warmers: tuple = ()) -> None:
        self.builder, self.clock, self.cases, self.warmers = builder, clock, cases, warmers
        self._cache: dict[tuple[str, date], _Entry] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="briefing")
        self._pending: list[Future] = []

    def clear(self) -> None:
        self._cache.clear()

    def wait_idle(self, timeout: float = 30.0) -> None:
        wait(list(self._pending), timeout=timeout)
        self._pending = [f for f in self._pending if not f.done()]

    def briefing(self, case: Case) -> dict[str, Any]:
        entry = self._entry(case)
        return {"snapshot": self.snapshot(case), "headline": entry.headline, "suggested_focus": entry.focus}

    def refresh(self, case: Case) -> None:
        """Recompute now, replacing the entry for the case's simulated day and dropping its earlier days."""
        core = self.builder.core(case)
        with self._lock:
            for k in [k for k in self._cache if k[0] == case.case_id and k[1] != case.sim_today]:
                del self._cache[k]
            self._cache[(case.case_id, case.sim_today)] = _Entry(core, self.clock.now(), headline(core), suggested_focus(core))

    def refresh_async(self, case: Case) -> None:
        """Background refresh (create, fork, advance). A failure only means the next read computes it itself."""
        def run() -> None:
            try:
                self.refresh(case)
            except Exception:  # noqa: BLE001 - never break the caller over a warm-up
                log.warning("briefing refresh failed for %s", case.case_id, exc_info=True)
        self._pending.append(self._pool.submit(run))

    def warm_recent(self, limit: int = 3) -> None:
        """Precompute the most recently created cases and initialise slow clients; never raises."""
        def run() -> None:
            for w in self.warmers:
                try:
                    w()
                except Exception:  # noqa: BLE001
                    log.warning("warmer failed", exc_info=True)
            try:
                recent = sorted(self.cases.list(), key=lambda c: c.created_at, reverse=True)[:limit] if self.cases else []
                for case in recent:
                    try:
                        self.refresh(case)
                    except Exception:  # noqa: BLE001
                        log.warning("warm-up failed for %s", case.case_id, exc_info=True)
            except Exception:  # noqa: BLE001
                log.warning("warm-up could not list cases", exc_info=True)
        self._pending.append(self._pool.submit(run))

    def keys(self) -> list[tuple[str, date]]:
        return list(self._cache)

    def snapshot(self, case: Case) -> dict[str, Any]:
        entry = self._entry(case)
        now = self.clock.now()
        return {**entry.core, **self.builder.live(case), "generated_at": entry.generated_at.isoformat(),
                "cache_age_s": max(0, int((now - entry.generated_at).total_seconds()))}

    def _entry(self, case: Case) -> _Entry:
        key = (case.case_id, case.sim_today)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        with self._lock:
            hit = self._cache.get(key)
            if hit is None:
                core = self.builder.core(case)
                hit = _Entry(core, self.clock.now(), headline(core), suggested_focus(core))
                self._cache[key] = hit
            return hit
