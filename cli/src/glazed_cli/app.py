"""Typer application: wiring only. Every command talks to the public API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import typer

from datetime import date as _date, timedelta

from glazed_cli import render, turns
from glazed_cli.client import Api, CliError, resolve_url
from glazed_cli.state import State

app = typer.Typer(help="Glazed store copilot CLI.", no_args_is_help=True, add_completion=False)
case_app = typer.Typer(help="Manage cases (sessions): new, list, use, show, fork.", no_args_is_help=True)
app.add_typer(case_app, name="case")
alert_app = typer.Typer(help="Act on a single alert.", no_args_is_help=True)
app.add_typer(alert_app, name="alert")
backtest_app = typer.Typer(help="Run and read backtests (simulated, labelled 'backtest').", no_args_is_help=True)
app.add_typer(backtest_app, name="backtest")


@dataclass
class Ctx:
    api: Api
    as_json: bool

    def out(self, data: Any, human: Callable[[Any], None]) -> None:
        """Print raw JSON with --json, otherwise run the human renderer."""
        if self.as_json:
            import json
            typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            human(data)


@app.callback()
def _root(ctx: typer.Context,
          as_json: bool = typer.Option(False, "--json", help="Print raw JSON."),
          api_url: Optional[str] = typer.Option(None, "--api", help="Backend URL (env GLAZED_API_URL).")) -> None:
    ctx.obj = Ctx(Api(resolve_url(api_url)), as_json)


def current_case_id(case: str | None) -> str:
    cid = case or State.load().current_case
    if not cid:
        raise CliError("No current case. Run `glazed case new --store S030 --date 2026-03-10` "
                       "or `glazed case use <case_id>`.")
    return cid


def _guard(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn CliError into a one-line message and exit code 1."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a: Any, **kw: Any) -> Any:
        try:
            return fn(*a, **kw)
        except CliError as exc:
            typer.echo(str(exc), err=False)
            raise typer.Exit(1)
    return wrapper


@app.command()
@_guard
def stores(ctx: typer.Context) -> None:
    """List the stores."""
    c: Ctx = ctx.obj
    data = c.api.get("/api/v1/stores")
    c.out(data, lambda d: render.console().print(render.records_table(
        "Stores", d, ["store_id", "name", "format", "site_id", "region"])))


# ---- cases ----

def _announce_case(c: Ctx, case: dict, verb: str) -> None:
    c.out(case, lambda d: render.console().print(
        f"{verb} case [bold]{d['case_id']}[/bold]  store={d['store_id']} "
        f"sim_today={d['sim_today']} mode={d['mode']}"))


@case_app.command("new")
@_guard
def case_new(ctx: typer.Context,
             store: str = typer.Option(..., "--store", help="Store id, e.g. S030."),
             date: str = typer.Option(..., "--date", help="Simulated today (YYYY-MM-DD)."),
             mode: str = typer.Option("live", "--mode", help="live | sandbox | backtest."),
             title: Optional[str] = typer.Option(None, "--title")) -> None:
    """Create an isolated case and make it current."""
    c: Ctx = ctx.obj
    body = {"store_id": store, "sim_today": date, "mode": mode}
    if title:
        body["title"] = title
    case = c.api.post("/api/v1/cases", body)
    State(current_case=case["case_id"]).save()
    _announce_case(c, case, "Created")


@case_app.command("list")
@_guard
def case_list(ctx: typer.Context, store: Optional[str] = typer.Option(None, "--store")) -> None:
    """List cases (the current one is marked with *)."""
    c: Ctx = ctx.obj
    data = c.api.get("/api/v1/cases", store_id=store)
    cur = State.load().current_case
    c.out(data, lambda d: render.console().print(render.case_table(d, cur)))


@case_app.command("use")
@_guard
def case_use(ctx: typer.Context, case_id: str) -> None:
    """Switch the current case."""
    c: Ctx = ctx.obj
    case = c.api.get(f"/api/v1/cases/{case_id}")
    State(current_case=case["case_id"]).save()
    _announce_case(c, case, "Using")


@case_app.command("show")
@_guard
def case_show(ctx: typer.Context, case: Optional[str] = typer.Option(None, "--case")) -> None:
    """Show the current case."""
    c: Ctx = ctx.obj
    data = c.api.get(f"/api/v1/cases/{current_case_id(case)}")
    c.out(data, lambda d: render.render_object("Case", d, render.console()))


@case_app.command("fork")
@_guard
def case_fork(ctx: typer.Context, title: Optional[str] = typer.Option(None, "--title"),
              case: Optional[str] = typer.Option(None, "--case")) -> None:
    """Fork the current case into a what-if child and switch to it."""
    c: Ctx = ctx.obj
    parent = current_case_id(case)
    child = c.api.post(f"/api/v1/cases/{parent}/fork", {"title": title} if title else {})
    State(current_case=child["case_id"]).save()
    c.out(child, lambda d: render.console().print(
        f"Forked {parent} -> [bold]{d['case_id']}[/bold]; now using the child."))


# ---- ask / day / advance ----

@app.command()
@_guard
def ask(ctx: typer.Context, question: str,
        case: Optional[str] = typer.Option(None, "--case", help="Use this case without making it current."),
        new: bool = typer.Option(False, "--new", help="Start an isolated case first (needs --store and --date)."),
        store: Optional[str] = typer.Option(None, "--store"),
        date: Optional[str] = typer.Option(None, "--date"),
        timeout: float = typer.Option(120.0, "--timeout", help="Seconds to wait for the answer.")) -> None:
    """Ask the copilot a question in the current case."""
    c: Ctx = ctx.obj
    if new:
        if not store or not date:
            raise CliError("--new needs --store and --date, e.g. --new --store S030 --date 2026-03-10.")
        created = c.api.post("/api/v1/cases", {"store_id": store, "sim_today": date, "mode": "live"})
        State(current_case=created["case_id"]).save()
        case_id = created["case_id"]
    else:
        case_id = current_case_id(case)
    out = render.console()
    if c.as_json:
        turn = turns.ask(c.api, case_id, question, timeout)
        c.out(turn, lambda _: None)
    else:
        with out.status("Thinking..."):
            turn = turns.ask(c.api, case_id, question, timeout)
    if turn["status"] == "failed":
        raise CliError(f"The turn failed: {turn.get('error') or 'unknown error'}")
    if c.as_json:
        return
    if turn.get("reply"):
        out.print(turn["reply"])
    if turn["status"] == "waiting_approval":
        pending = c.api.get("/api/v1/proposals", case_id=case_id, status="pending")
        out.print("\n[yellow]This turn is waiting for your approval.[/yellow] "
                  "Use `glazed decide <proposal_id> --approve|--reject`.")
        if pending:
            out.print(render.proposals_table(pending, "Pending proposals"))


@app.command()
@_guard
def day(ctx: typer.Context, date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD; default sim_today-1."),
        case: Optional[str] = typer.Option(None, "--case")) -> None:
    """Day summary of the current case's store."""
    c: Ctx = ctx.obj
    case_id = current_case_id(case)
    if not date:
        sim_today = c.api.get(f"/api/v1/cases/{case_id}")["sim_today"]
        date = (_date.fromisoformat(sim_today) - timedelta(days=1)).isoformat()
    data = c.api.get(f"/api/v1/cases/{case_id}/day-summary", date=date)
    c.out(data, lambda d: render.render_object(f"Day summary {date}", d, render.console()))


@app.command()
@_guard
def advance(ctx: typer.Context, days: Optional[int] = typer.Option(None, "--days", min=1),
            to: Optional[str] = typer.Option(None, "--to", help="Target date YYYY-MM-DD."),
            case: Optional[str] = typer.Option(None, "--case")) -> None:
    """Move the case clock forward and list the new alerts."""
    c: Ctx = ctx.obj
    if days is not None and to:
        raise CliError("Use either --days or --to, not both.")
    body = {"to": to} if to else {"days": days or 1}
    data = c.api.post(f"/api/v1/cases/{current_case_id(case)}/advance", body)

    def human(d: dict) -> None:
        out = render.console()
        out.print(f"sim_today is now [bold]{d['sim_today']}[/bold]")
        if d["new_alerts"]:
            out.print(render.alerts_table(d["new_alerts"], "New alerts"))
        else:
            out.print("No new alerts.")
    c.out(data, human)


# ---- alerts, proposals ----

@app.command()
@_guard
def alerts(ctx: typer.Context, store: Optional[str] = typer.Option(None, "--store"),
           state: Optional[str] = typer.Option(None, "--state", help="e.g. nueva, vista, en_analisis.")) -> None:
    """List alerts."""
    c: Ctx = ctx.obj
    data = c.api.get("/api/v1/alerts", store_id=store, state=state)
    c.out(data, lambda d: render.console().print(render.alerts_table(d) if d else "No alerts."))


@alert_app.command("seen")
@_guard
def alert_seen(ctx: typer.Context, alert_id: str) -> None:
    """Mark an alert as seen (state 'vista')."""
    c: Ctx = ctx.obj
    data = c.api.patch(f"/api/v1/alerts/{alert_id}", {"state": "vista"})
    c.out(data, lambda d: render.console().print(f"Alert {d['alert_id']} is now [bold]{d['state']}[/bold]."))


@app.command()
@_guard
def proposals(ctx: typer.Context, status: Optional[str] = typer.Option(None, "--status", help="e.g. pending."),
              case: Optional[str] = typer.Option(None, "--case"),
              all_cases: bool = typer.Option(False, "--all", help="Do not filter by the current case.")) -> None:
    """List proposals of the current case (use --all for every case)."""
    c: Ctx = ctx.obj
    case_id = None if all_cases else (case or State.load().current_case)
    data = c.api.get("/api/v1/proposals", case_id=case_id, status=status)
    c.out(data, lambda d: render.console().print(render.proposals_table(d) if d else "No proposals."))


@app.command()
@_guard
def decide(ctx: typer.Context, proposal_id: str,
           approve: bool = typer.Option(False, "--approve"), reject: bool = typer.Option(False, "--reject"),
           reason: Optional[str] = typer.Option(None, "--reason")) -> None:
    """Approve or reject a proposal (rejecting needs --reason)."""
    c: Ctx = ctx.obj
    if approve == reject:
        raise CliError("Choose exactly one of --approve or --reject.")
    if reject and not (reason or "").strip():
        raise CliError("Rejecting needs a reason: --reason \"...\".")
    body: dict[str, Any] = {"approved": approve}
    if reason:
        body["reason"] = reason
    ex = c.api.post(f"/api/v1/proposals/{proposal_id}/decision", body)
    c.out(ex, lambda d: render.console().print(
        f"Proposal {proposal_id} {'approved' if approve else 'rejected'}: execution "
        f"[bold]{d['status']}[/bold] (source: {d['source']}). {d.get('detail') or ''}"))


# ---- backtest, trace ----

@backtest_app.command("run")
@_guard
def backtest_run(ctx: typer.Context, date_from: str = typer.Option(..., "--from"),
                 date_to: str = typer.Option(..., "--to"), policy: Optional[str] = typer.Option(None, "--policy"),
                 store: Optional[str] = typer.Option(None, "--store", help="Create a fresh backtest case for this store."),
                 case: Optional[str] = typer.Option(None, "--case")) -> None:
    """Run a backtest over a period and print the report."""
    c: Ctx = ctx.obj
    if store:
        created = c.api.post("/api/v1/cases", {
            "store_id": store, "sim_today": date_to, "mode": "backtest",
            "title": f"backtest {store} {date_from}..{date_to}"})
        State(current_case=created["case_id"]).save()
        case_id = created["case_id"]
    else:
        case_id = current_case_id(case)
    body = {"date_from": date_from, "date_to": date_to}
    if policy:
        body["policy"] = policy
    data = c.api.post(f"/api/v1/cases/{case_id}/backtests", body)
    c.out(data, lambda d: render.backtest_report(d, render.console()))


@backtest_app.command("show")
@_guard
def backtest_show(ctx: typer.Context, run_id: str) -> None:
    """Show a backtest report."""
    c: Ctx = ctx.obj
    data = c.api.get(f"/api/v1/backtests/{run_id}")
    c.out(data, lambda d: render.backtest_report(d, render.console()))


@app.command()
@_guard
def trace(ctx: typer.Context, case: Optional[str] = typer.Option(None, "--case"),
          store: Optional[str] = typer.Option(None, "--store")) -> None:
    """Agent-communication timeline (current case, or a whole store with --store)."""
    c: Ctx = ctx.obj
    case_id = case if (case or store) else current_case_id(None)
    data = c.api.get("/api/v1/trace", store_id=store, case_id=case_id)
    c.out(data, lambda d: render.console().print(render.trace_table(d) if d else "No trace events."))


def main() -> None:
    app()
