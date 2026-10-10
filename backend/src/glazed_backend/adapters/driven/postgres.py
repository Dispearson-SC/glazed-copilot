"""Postgres repositories (psycopg 3). Schema `glazed`; migrations are plain SQL files applied at startup."""
from __future__ import annotations

import threading
from importlib import resources
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ...domain import Alert, AlertState, BacktestRun, Case, Execution, Proposal, TraceEvent

_TABLES = ("store_assistants", "trace_events", "backtests", "executions", "proposals", "alerts", "cases")


class PostgresStore:
    """Owns one autocommit connection (guarded by a lock) and exposes one repository per port."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._lock = threading.Lock()
        self._conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        self.cases, self.alerts = _Cases(self), _Alerts(self)
        self.proposals, self.executions = _Proposals(self), _Executions(self)
        self.backtests, self.trace = _Backtests(self), _Trace(self)
        self.assistants = _Assistants(self)

    def migrate(self) -> None:
        files = sorted(f for f in resources.files("glazed_backend.migrations").iterdir() if f.name.endswith(".sql"))
        with self._lock:
            self._conn.execute("CREATE SCHEMA IF NOT EXISTS glazed")
            self._conn.execute("CREATE TABLE IF NOT EXISTS glazed.schema_migrations (name text PRIMARY KEY)")
            done = {r["name"] for r in self._conn.execute("SELECT name FROM glazed.schema_migrations").fetchall()}
            for f in files:
                if f.name not in done:
                    self._conn.execute(f.read_text())
                    self._conn.execute("INSERT INTO glazed.schema_migrations VALUES (%s)", (f.name,))

    def truncate_all(self) -> None:
        with self._lock:
            self._conn.execute("TRUNCATE " + ", ".join(f"glazed.{t}" for t in _TABLES))

    def q(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall() if cur.description else []


class _Repo:
    def __init__(self, store: PostgresStore) -> None:
        self.s = store

    def _one(self, sql: str, params: tuple) -> dict[str, Any] | None:
        rows = self.s.q(sql, params)
        return rows[0] if rows else None


class _Cases(_Repo):
    _COLS = ("case_id", "store_id", "sim_today", "mode", "parent_case_id", "core_conversation_id", "title",
             "created_at", "issue_key")

    def add(self, c: Case) -> None:
        cols = ", ".join(self._COLS)
        sets = ", ".join(f"{k}=EXCLUDED.{k}" for k in self._COLS[1:])
        self.s.q(f"INSERT INTO glazed.cases ({cols}) VALUES ({', '.join(['%s'] * 9)})"
                 f" ON CONFLICT (case_id) DO UPDATE SET {sets}", [getattr(c, k) for k in self._COLS])

    update = add

    def _row(self, r: dict | None) -> Case | None:
        return Case(**{k: r[k] for k in self._COLS}) if r else None

    def get(self, case_id: str) -> Case | None:
        return self._row(self._one("SELECT * FROM glazed.cases WHERE case_id=%s", (case_id,)))

    def get_by_issue_key(self, issue_key: str) -> Case | None:
        return self._row(self._one("SELECT * FROM glazed.cases WHERE issue_key=%s LIMIT 1", (issue_key,)))

    def get_by_conversation(self, conversation_id: str) -> Case | None:
        return self._row(self._one("SELECT * FROM glazed.cases WHERE core_conversation_id=%s LIMIT 1",
                                   (conversation_id,)))

    def list(self, store_id: str | None = None) -> list[Case]:
        rows = self.s.q("SELECT * FROM glazed.cases WHERE (%s::text IS NULL OR store_id=%s) ORDER BY created_at",
                        (store_id, store_id))
        return [self._row(r) for r in rows]  # type: ignore[misc]


class _Alerts(_Repo):
    def add(self, a: Alert) -> None:
        self.s.q("INSERT INTO glazed.alerts (alert_id, alert_type, store_id, case_id, severity_usd, state, issue,"
                 " issue_key, as_of, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                 " ON CONFLICT (alert_id) DO UPDATE SET state=EXCLUDED.state, severity_usd=EXCLUDED.severity_usd,"
                 " issue=EXCLUDED.issue", [a.alert_id, a.alert_type, a.store_id, a.case_id, a.severity_usd,
                                           a.state.value, Jsonb(a.issue), a.issue_key, a.as_of, a.created_at])

    update = add

    @staticmethod
    def _row(r: dict | None) -> Alert | None:
        return Alert(r["alert_id"], r["alert_type"], r["store_id"], r["case_id"], r["severity_usd"],
                     AlertState(r["state"]), r["issue"], r["issue_key"], r["as_of"], r["created_at"]) if r else None

    def get(self, alert_id: str) -> Alert | None:
        return self._row(self._one("SELECT * FROM glazed.alerts WHERE alert_id=%s", (alert_id,)))

    def get_by_issue_key(self, issue_key: str) -> Alert | None:
        return self._row(self._one("SELECT * FROM glazed.alerts WHERE issue_key=%s", (issue_key,)))

    def list(self, store_id: str | None = None, state: AlertState | None = None) -> list[Alert]:
        st = state.value if state else None
        rows = self.s.q("SELECT * FROM glazed.alerts WHERE (%s::text IS NULL OR store_id=%s)"
                        " AND (%s::text IS NULL OR state=%s) ORDER BY severity_usd DESC", (store_id, store_id, st, st))
        return [self._row(r) for r in rows]  # type: ignore[misc]


class _Proposals(_Repo):
    def add(self, p: Proposal) -> None:
        self.s.q("INSERT INTO glazed.proposals VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                 " ON CONFLICT (proposal_id) DO UPDATE SET status=EXCLUDED.status, reason=EXCLUDED.reason,"
                 " params=EXCLUDED.params, reason_category=EXCLUDED.reason_category,"
                 " reason_confidence=EXCLUDED.reason_confidence",
                 [p.proposal_id, p.case_id, p.store_id, p.issue_id, p.action_type, Jsonb(p.params), p.tier, p.rationale,
                  p.status, p.reason, p.agent_id, p.created_at, p.reason_category, p.reason_confidence])

    update = add

    @staticmethod
    def _row(r: dict | None) -> Proposal | None:
        return Proposal(r["proposal_id"], r["case_id"], r["store_id"], r["issue_id"], r["action_type"], r["params"],
                        r["tier"], r["rationale"], r["status"], r["reason"], r["agent_id"], r["created_at"],
                        r["reason_category"], r["reason_confidence"]) if r else None

    def get(self, proposal_id: str) -> Proposal | None:
        return self._row(self._one("SELECT * FROM glazed.proposals WHERE proposal_id=%s", (proposal_id,)))

    def list(self, case_id: str | None = None, store_id: str | None = None, status: str | None = None) -> list[Proposal]:
        rows = self.s.q("SELECT * FROM glazed.proposals WHERE (%s::text IS NULL OR case_id=%s)"
                        " AND (%s::text IS NULL OR store_id=%s) AND (%s::text IS NULL OR status=%s) ORDER BY created_at",
                        (case_id, case_id, store_id, store_id, status, status))
        return [self._row(r) for r in rows]  # type: ignore[misc]


class _Executions(_Repo):
    def add(self, e: Execution) -> None:
        self.s.q("INSERT INTO glazed.executions VALUES (%s,%s,%s,%s,%s,%s,%s)",
                 [e.execution_id, e.proposal_id, e.case_id, e.source, e.status, e.detail, e.executed_at])

    def list(self, case_id: str) -> list[Execution]:
        return [Execution(**r) for r in self.s.q(
            "SELECT * FROM glazed.executions WHERE case_id=%s ORDER BY executed_at", (case_id,))]


class _Backtests(_Repo):
    def add(self, r: BacktestRun) -> None:
        self.s.q("INSERT INTO glazed.backtests VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                 [r.run_id, r.case_id, r.store_id, r.period_from, r.period_to, r.policy, Jsonb(r.results),
                  r.created_at, r.label])

    @staticmethod
    def _row(r: dict | None) -> BacktestRun | None:
        return BacktestRun(r["run_id"], r["case_id"], r["store_id"], r["period_from"], r["period_to"], r["policy"],
                           r["results"], r["created_at"], r["label"]) if r else None

    def get(self, run_id: str) -> BacktestRun | None:
        return self._row(self._one("SELECT * FROM glazed.backtests WHERE run_id=%s", (run_id,)))

    def list(self, case_id: str | None = None) -> list[BacktestRun]:
        rows = self.s.q("SELECT * FROM glazed.backtests WHERE (%s::text IS NULL OR case_id=%s) ORDER BY created_at",
                        (case_id, case_id))
        return [self._row(r) for r in rows]  # type: ignore[misc]


class _Trace(_Repo):
    def record(self, e: TraceEvent) -> None:
        self.s.q("INSERT INTO glazed.trace_events VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (event_id) DO NOTHING",
                 [e.event_id, e.case_id, e.store_id, e.ts, e.from_agent, e.to_agent, e.kind, Jsonb(e.payload)])

    def list(self, case_id: str | None = None, store_id: str | None = None) -> list[TraceEvent]:
        rows = self.s.q("SELECT * FROM glazed.trace_events WHERE (%s::text IS NULL OR case_id=%s)"
                        " AND (%s::text IS NULL OR store_id=%s) ORDER BY ts", (case_id, case_id, store_id, store_id))
        return [TraceEvent(r["case_id"], r["store_id"], r["ts"], r["from_agent"], r["to_agent"], r["kind"],
                           r["payload"], r["event_id"]) for r in rows]


class _Assistants(_Repo):
    def get(self, store_id: str) -> str | None:
        r = self._one("SELECT assistant_id FROM glazed.store_assistants WHERE store_id=%s", (store_id,))
        return r["assistant_id"] if r else None

    def set(self, store_id: str, assistant_id: str) -> None:
        self.s.q("INSERT INTO glazed.store_assistants VALUES (%s,%s) ON CONFLICT (store_id) DO UPDATE"
                 " SET assistant_id=EXCLUDED.assistant_id", [store_id, assistant_id])
