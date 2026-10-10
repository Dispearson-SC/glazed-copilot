# glazed CLI

Command line client for the Glazed store copilot. It talks only to the backend public API (`/api/v1/*`).

## Install and test

```bash
cd cli
pip install -e '.[test]'      # console script: glazed
python -m pytest -q
```

Without a venv: `python3 -m pip install --target .deps typer httpx rich pytest`, then
`PYTHONPATH=.deps:src python3 -m pytest -q` and `PYTHONPATH=.deps:src python3 -m glazed_cli --help`.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `GLAZED_API_URL` or `--api` | `http://localhost:8080` | Backend base URL |
| `GLAZED_STATE` | `~/.glazed/state.json` | Where the current case is remembered |
| `--json` (global) | off | Print raw JSON instead of tables |

If the backend is down you get one line, not a traceback.

## The cases model

A **case** is the unit of conversation: a store, a simulated "today" and a mode (`live`, `sandbox`, `backtest`).

- **Iterate**: `glazed ask` keeps using the current case, so the agents remember earlier questions.
- **Isolate**: `glazed case new ...` or `glazed ask --new --store S030 --date 2026-03-10 "..."` starts a clean case; nothing leaks between cases.
- **Fork (what-if)**: `glazed case fork --title "no promo"` copies the current case into a child and switches to it. The original is untouched.
- `glazed case use <id>` switches; `--case <id>` on a command targets another case without switching.

## Examples

```bash
glazed stores
glazed case new --store S030 --date 2026-03-10 --mode sandbox --title "March replay"
glazed ask "How was a normal sales day?"          # polls until done; --timeout 300 to wait longer
glazed ask --new --store S030 --date 2026-03-10 "Any stockout risk?"
glazed day                                         # sim_today - 1; or --date 2026-03-05
glazed advance --days 3                            # or --to 2026-03-20; lists new alerts
glazed alerts --store S030 --state nueva
glazed alert seen <alert_id>
glazed proposals --status pending                  # current case; --all for every case
glazed decide <proposal_id> --approve
glazed decide <proposal_id> --reject --reason "stock arrives tomorrow"
glazed case fork --title "what if we skip the order"
glazed backtest run --from 2026-03-01 --to 2026-03-14 --policy default
glazed backtest run --store S030 --from 2026-03-01 --to 2026-03-14   # fresh backtest case
glazed backtest show <run_id>
glazed trace                                       # agent timeline of the current case
glazed trace --store S030
```

When `ask` ends in `waiting_approval`, the pending proposals are listed; decide them with `glazed decide`.
Backtest results are labelled "backtest": they are simulated and compared with current practice, never real operations.

## Backend contract assumptions

Beyond `docs`/the public API contract: `BacktestRun.results` is expected as
`{waste_usd, lost_sales_usd, net_usd, baseline?: {waste_usd, lost_sales_usd, net_usd}}` (extra keys are shown generically);
the day summary is any JSON object (scalars and lists of records are rendered as tables);
`POST .../decision` conflicts (already decided) answer 4xx with `{"detail": ...}`.
