# Stress battery

A fixed set of manager questions run against a live glazed backend, so latency and quality can be compared
before and after a change (baseline -> Phase 3 deploy -> Phase 5).

## What it does

- `scripts/stress/cases.json`: 25 turns in Spanish on store `S001` at `2026-07-19`: a simple question, the 10
  frequent intents, 3 specialist questions, a multi-specialist question, a proposal (must stay pending), an
  unsupported-data question (must be refused), a 3-turn follow-up and a burst of 5 simultaneous turns.
- Every case runs in a fresh **sandbox** case titled `stress <label> <case>`. The runner never calls a decision
  or approve endpoint, so no real decision is taken.
- Each turn is driven like `glazed ask`: `POST /api/v1/cases/{id}/messages`, poll
  `GET /api/v1/cases/{id}/turns/{turn_id}` every second until `done|failed|waiting_approval` (timeout 900 s),
  then `GET /api/v1/trace?case_id=` for the turn's tool calls and peer asks.

Per turn it records: total latency, first-progress latency (first poll that shows a specialist consulted),
first-text latency `first_text_s` (the backend's `first_text_ms`: since P5 it follows Core's SSE feed; null on a
build that streams nothing, or with `GLAZED_CORE_STREAM=false`), status, tool calls by name, peer asks and peers, policy
denials, sanitizer fragments and rewrite, token/cost fields when the API exposes them (it does not today), errors,
expectation checks (`proposal_pending`, `refusal`, `multi_peer`) and quality flags:

| flag | meaning |
|---|---|
| `think_tags` | `<think>` tags leaked into the reply |
| `foreign_script` | non-Latin script characters |
| `garbled` | replacement characters, or garbled fragments (P12): a preposition glued to an article (`dela`, `enel`), `hoy`/`usted` glued to a word (`hoyusted`), a word glued to a number (`en1`), lower-case English function words inside a Spanish reply (`and`, `the`; capitalised product names do not count), full-width punctuation (`，`) and markdown debris (`**:` with nothing before it, a lone `**` or `#`). Each turn's `quality.garbled_fragments` lists them; the aggregates add `garbled_fragments_total` and `garbled_turns`, and `compare` shows both |
| `non_spanish` | English stopwords dominate |
| `internal_names` | snake_case identifiers (agents, tools, fields) or words like orchestrator/peer/backend; two Spanish function words a model joined with `_` (`de_no`) are a typo, not a name |
| `untraceable_numbers` | a number (>10 or decimal) absent from the tool results and peer answers of this turn AND the earlier turns of the same conversation (a follow-up repeats figures it already fetched) |

The number check needs the tool results. When the trace does not carry them (the live build only records the
calls) or a result is clipped, misses go to `unverified_numbers` and do not raise the flag.

`llm_calls_estimate` is an upper-bound guess: per turn, tool calls + 1 + 3 per peer ask (+1 for a rewrite).

## Run

From the repository root, with httpx on the path (the backend `.deps` has it):

```bash
export PYTHONPATH=/path/to/glazed-copilot/backend/.deps
python3 scripts/stress/run.py run --label baseline            # default API http://localhost:8100
python3 scripts/stress/run.py run --label phase3 --api http://localhost:8100
python3 scripts/stress/run.py run --label smoke --only simple  # a subset by case id
python3 scripts/stress/run.py compare scripts/stress/results/baseline-<ts>.json \
  scripts/stress/results/phase3-<ts>.json --out scripts/stress/results/baseline-vs-phase3.md
```

Auth: on 401 the runner logs in with `GLAZED_STRESS_EMAIL` + `GLAZED_STRESS_PASSWORD`, or with the demo login of
the first admin, and sends the session as a Bearer token. Nothing secret is printed.

Results land in `scripts/stress/results/<label>-<timestamp>.json` (written after every turn) and `.md`.
Each run makes real LLM calls: run it once per stage.

## Tests

```bash
cd backend && PYTHONPATH=<.deps>:src python3 -m pytest tests/unit/test_stress_battery.py
```
