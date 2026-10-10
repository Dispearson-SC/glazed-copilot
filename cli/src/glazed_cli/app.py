"""Typer application: wiring only. Every command talks to the public API."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

import typer

from glazed_cli import render
from glazed_cli.client import Api, CliError, resolve_url
from glazed_cli.state import State

app = typer.Typer(help="Glazed store copilot CLI.", no_args_is_help=True, add_completion=False)
case_app = typer.Typer(help="Manage cases (sessions): new, list, use, show, fork.", no_args_is_help=True)
app.add_typer(case_app, name="case")


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


def main() -> None:
    app()
