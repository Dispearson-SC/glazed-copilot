"""Stress battery runner: drives the glazed backend public API exactly like the CLI (`glazed ask`):
POST /api/v1/cases/{id}/messages -> poll GET /api/v1/cases/{id}/turns/{turn_id} until done|failed|waiting_approval,
then reads GET /api/v1/trace?case_id= for tool calls and peer asks.

Safety: every case is a fresh `sandbox` case; the runner never calls a decision/approve endpoint.

Usage (from the repository root):
  python3 scripts/stress/run.py run --label baseline [--api http://localhost:8100] [--only simple,burst] [--repeat N]
  python3 scripts/stress/run.py tag scripts/stress/results/A.json decisions.json
  python3 scripts/stress/run.py compare scripts/stress/results/A.json scripts/stress/results/B.json

`--repeat N` (P13) asks every case N times, round after round (a fresh sandbox case each time), so provider drift
spreads over every case; each turn records its `repeat`, and compare pairs (case, turn, repeat). The Core's fast-path
verdict per turn is not exposed by the backend: export it from the Core audit and `tag` the result with it
(decisions.json is a list of {turn_id, fast_path} or a {turn_id: fast_path} map), e.g.
  psql "$AGENT_CORE_DB" -Atc "select json_agg(json_build_object('turn_id', turn_id, 'fast_path', fast_path))
                              from audit_turn_routes where fast_path is not null" > decisions.json
compare then reports per-path medians: `composite` turns, `defer` turns (the path every mode runs the same way, so a
change there between two runs is provider drift) and `pass` turns (`on` runs the entry profile instead: behaviour).

Auth: when /api/v1 answers 401 the runner logs in with GLAZED_STRESS_EMAIL + GLAZED_STRESS_PASSWORD if set,
otherwise with the demo login as the first admin of /api/v1/auth/demo-users. Credentials are never printed.
Needs httpx (the backend .deps has it: PYTHONPATH=backend/.deps or the glazed-copilot checkout's .deps)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # `compare` needs no network; `run` reports the missing dependency
    httpx = None  # type: ignore[assignment]

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import battery  # noqa: E402

TERMINAL = ("done", "failed", "waiting_approval")
DEFAULT_API = "http://localhost:8100"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


class Api:
    def __init__(self, base: str, headers: dict[str, str] | None = None) -> None:
        self.http = httpx.Client(base_url=base.rstrip("/"), timeout=60.0, headers=headers)

    def call(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return self.http.request(method, path, **kw)

    def json(self, method: str, path: str, **kw: Any) -> Any:
        r = self.call(method, path, **kw)
        r.raise_for_status()
        return r.json()

    def login(self) -> None:
        if self.call("GET", "/api/v1/stores").status_code != 401:
            return
        email, pwd = os.environ.get("GLAZED_STRESS_EMAIL"), os.environ.get("GLAZED_STRESS_PASSWORD")
        if email and pwd:
            r = self.call("POST", "/api/v1/auth/login", json={"email": email, "password": pwd})
        else:
            users = self.json("GET", "/api/v1/auth/demo-users")
            admin = next(u for u in users if u.get("role") == "admin")
            r = self.call("POST", "/api/v1/auth/demo-login", json={"email": admin["email"]})
        token = r.cookies.get("glazed_session")
        if r.status_code >= 400 or not token:
            raise SystemExit(f"login failed with HTTP {r.status_code}")
        # The session cookie may be Secure (not sent over plain http): the guard also accepts it as a Bearer token.
        self.http.headers["Authorization"] = f"Bearer {token}"
        log("logged in")


def new_case(api: Api, b: battery.Battery, label: str, case_id: str) -> str:
    body = {"store_id": b.store_id, "sim_today": b.sim_today, "mode": b.mode,
            "title": f"stress {label} {case_id}"}
    return api.json("POST", "/api/v1/cases", json=body)["case_id"]


def ask(api: Api, backend_case: str, text: str, timeout: float, poll: float) -> dict[str, Any]:
    """One turn, timed from the POST to the terminal poll. first_progress_s = first poll that shows a specialist
    being consulted; first_text_s = the backend's `first_text_ms` (it follows Core's SSE feed, P5), or the first poll
    that showed a `partial_reply` when the backend reports no time (None on a build that streams nothing)."""
    t0 = time.monotonic()
    out: dict[str, Any] = {"first_text_s": None, "first_progress_s": None, "polls": 0}
    try:
        turn_id = api.json("POST", f"/api/v1/cases/{backend_case}/messages", json={"text": text})["turn_id"]
    except httpx.HTTPError as exc:
        return {**out, "status": "error", "error": f"start: {exc}", "latency_s": round(time.monotonic() - t0, 2)}
    out["turn_id"] = turn_id
    turn: dict[str, Any] = {}
    errors = 0
    while True:
        out["polls"] += 1
        try:
            r = api.call("GET", f"/api/v1/cases/{backend_case}/turns/{turn_id}")
            if r.status_code == 404:
                turn = {"status": "pending"}
            else:
                r.raise_for_status()
                turn = r.json()
        except httpx.HTTPError as exc:
            errors += 1
            out.setdefault("poll_errors", []).append(str(exc)[:200])
            if errors > 10:
                return {**out, "status": "error", "error": "too many poll errors",
                        "latency_s": round(time.monotonic() - t0, 2)}
        elapsed = time.monotonic() - t0
        if turn.get("progress") and out["first_progress_s"] is None:
            out["first_progress_s"] = round(elapsed, 2)
        reported = battery.first_text_seconds(turn)
        if reported is not None:
            out["first_text_s"] = reported
        elif turn.get("partial_reply") and out["first_text_s"] is None:
            out["first_text_s"] = round(elapsed, 2)
        if turn.get("status") in TERMINAL:
            break
        if elapsed > timeout:
            return {**out, "status": "timeout", "error": f"no terminal status after {timeout:g}s",
                    "still_running": bool(turn.get("still_running")), "latency_s": round(elapsed, 2)}
        time.sleep(poll)
    out.update({"status": turn["status"], "latency_s": round(time.monotonic() - t0, 2),
                "reply": turn.get("reply") or "", "error": turn.get("error"),
                "sanitized_fragments": len(turn.get("sanitized_fragments") or []),
                "rewritten": bool((turn.get("reply_meta") or {}).get("rewritten")),
                "progress": turn.get("progress") or [],
                # P13: the Core's fast-path verdict, when the backend exposes it (else `tag` adds it from the audit)
                **({"fast_path": turn["fast_path"]} if turn.get("fast_path") else {}),
                "usage": {k: turn[k] for k in ("usage", "cost", "tokens") if k in turn} or None})
    return out


def finish_turn(api: Api, case: battery.Case, idx: int, question: str, backend_case: str,
                res: dict[str, Any], burst: bool, earlier: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """`earlier`: the trace metrics of the conversation's previous turns (appended to here), so a follow-up's numbers
    are traced against everything the conversation fetched (L13)."""
    events: list[dict[str, Any]] = []
    if res.get("turn_id"):
        try:
            events = api.json("GET", "/api/v1/trace", params={"case_id": backend_case})
        except httpx.HTTPError as exc:
            res.setdefault("poll_errors", []).append(f"trace: {exc}"[:200])
    m = battery.trace_metrics(events, str(res.get("turn_id")))
    reply = res.get("reply") or ""
    checks: dict[str, bool] = {}
    if case.expect.get("proposal"):
        pending = api.json("GET", "/api/v1/proposals", params={"case_id": backend_case, "status": "pending"})
        checks["proposal_pending"] = bool(pending) or res.get("status") == "waiting_approval"
    if case.expect.get("refusal"):
        checks["refusal"] = battery.looks_like_refusal(reply)
    if case.expect.get("min_peer_asks"):
        checks["multi_peer"] = m["peer_asks"] >= int(case.expect["min_peer_asks"])
    sources, complete = battery.conversation_sources(earlier or [], m)
    if earlier is not None:
        earlier.append(m)
    q = battery.quality(reply, sources, question, complete=complete)
    return {"case_id": case.id, "kind": case.kind, "turn_index": idx, "burst": burst, "question": question,
            "backend_case_id": backend_case, **{k: v for k, v in res.items()},
            "tool_calls": m["tool_calls"], "peer_asks": m["peer_asks"], "tools": m["tools"], "peers": m["peers"],
            "policy_denials": m["policy_denials"], "results_complete": m["results_complete"], "checks": checks, "quality": q,
            "expect": case.expect}


def llm_calls_estimate(turns: list[dict[str, Any]]) -> int:
    """Upper-bound guess: one model step per tool call plus the final answer, ~3 steps per peer ask, and one
    extra turn when the backend asked for a rewrite."""
    return sum((t.get("tool_calls") or 0) + 1 + 3 * (t.get("peer_asks") or 0) + (1 if t.get("rewritten") else 0)
               for t in turns if t.get("status") != "error")


def run(args: argparse.Namespace) -> Path:
    if httpx is None:
        raise SystemExit("run needs httpx: set PYTHONPATH to the backend .deps")
    b = battery.load_cases(args.cases)
    only = set(args.only.split(",")) if args.only else None
    cases = [c for c in b.cases if only is None or c.id in only]
    api = Api(args.api)
    api.login()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{args.label}-{stamp}.json"
    record: dict[str, Any] = {"label": args.label, "started_at": stamp, "api": args.api, "store_id": b.store_id,
                              "sim_today": b.sim_today, "battery_version": b.version, "turns": []}
    lock = threading.Lock()

    def save() -> None:
        with lock:
            record["aggregate"] = battery.aggregate(record["turns"])
            record["llm_calls_estimate"] = llm_calls_estimate(record["turns"])
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    record["repeat"] = args.repeat
    ordered = [c for c in cases if c.kind != "burst"] + [c for c in cases if c.kind == "burst"]
    for rep, case in battery.schedule(ordered, args.repeat):
        tag = f"{case.id}" + (f" r{rep}" if args.repeat > 1 else "")
        if case.kind != "burst":
            backend_case = new_case(api, b, args.label, case.id)
            history: list[dict[str, Any]] = []
            for idx, q in enumerate(case.turns):
                log(f"{tag}[{idx}] asking")
                res = ask(api, backend_case, q, args.timeout, args.poll)
                t = {**finish_turn(api, case, idx, q, backend_case, res, burst=False, earlier=history), "repeat": rep}
                record["turns"].append(t)
                save()
                log(f"{tag}[{idx}] {t['status']} {t['latency_s']}s tools={t['tool_calls']} peers={t['peer_asks']} "
                    f"flags={t['quality']['flags']} checks={t['checks']}")
            continue
        backend_cases = [new_case(api, b, args.label, f"{case.id}-{i}") for i in range(len(case.turns))]
        barrier = threading.Barrier(len(case.turns))

        def one(i: int, case: battery.Case = case, backend_cases: list[str] = backend_cases,
                barrier: threading.Barrier = barrier) -> dict[str, Any]:
            local = Api(args.api, headers=dict(api.http.headers))
            barrier.wait()
            res = ask(local, backend_cases[i], case.turns[i], args.timeout, args.poll)
            return finish_turn(local, case, i, case.turns[i], backend_cases[i], res, burst=True)

        log(f"{tag}: {len(case.turns)} simultaneous turns")
        with ThreadPoolExecutor(len(case.turns)) as pool:
            for t in pool.map(one, range(len(case.turns))):
                record["turns"].append({**t, "repeat": rep})
                log(f"{tag}[{t['turn_index']}] {t['status']} {t['latency_s']}s flags={t['quality']['flags']}")
        save()

    record["finished_at"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    save()
    path.with_suffix(".md").write_text(battery.render_markdown(record), encoding="utf-8")
    log(f"wrote {path} and {path.with_suffix('.md')}")
    return path


def tag(args: argparse.Namespace) -> None:
    """Add the audited fast-path verdicts to a result file (by turn id) and rewrite its aggregate and summary."""
    path = Path(args.result)
    record = json.loads(path.read_text(encoding="utf-8"))
    raw = json.loads(Path(args.decisions).read_text(encoding="utf-8")) or {}
    decisions = raw if isinstance(raw, dict) else {str(r["turn_id"]): str(r["fast_path"]) for r in raw
                                                   if r.get("turn_id") and r.get("fast_path")}
    record["turns"] = battery.tag_decisions(record.get("turns", []), decisions)
    record["aggregate"] = battery.aggregate(record["turns"])
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    path.with_suffix(".md").write_text(battery.render_markdown(record), encoding="utf-8")
    tagged = sum(1 for t in record["turns"] if t.get("fast_path"))
    log(f"tagged {tagged} of {len(record['turns'])} turns in {path}")


def compare(args: argparse.Namespace) -> None:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    md = battery.render_compare_markdown(battery.compare(before, after))
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
    print(md)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run the battery against a live backend")
    r.add_argument("--label", required=True, help="e.g. baseline, phase3, phase5")
    r.add_argument("--api", default=os.environ.get("GLAZED_API_URL", DEFAULT_API))
    r.add_argument("--cases", default=str(HERE / "cases.json"))
    r.add_argument("--out", default=str(HERE / "results"))
    r.add_argument("--only", help="comma-separated case ids")
    r.add_argument("--timeout", type=float, default=900.0, help="seconds per turn")
    r.add_argument("--poll", type=float, default=1.0, help="poll interval seconds")
    r.add_argument("--repeat", type=int, default=1,
                   help="ask every case this many times, round after round (P13: spreads provider drift)")
    t = sub.add_parser("tag", help="add audited fast-path verdicts (by turn id) to a result file")
    t.add_argument("result")
    t.add_argument("decisions", help="JSON: [{turn_id, fast_path}] or {turn_id: fast_path}")
    c = sub.add_parser("compare", help="compare two result files")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--out", help="also write the Markdown here")
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    {"run": run, "tag": tag, "compare": compare}[args.cmd](args)


if __name__ == "__main__":
    main()
