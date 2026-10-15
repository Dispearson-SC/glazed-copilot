"""Stress battery, pure part: case loading, reply quality checks, per-turn trace metrics, aggregates, compare
and Markdown rendering. No network and no backend imports, so it is unit tested from backend/tests/unit.

The IO runner is run.py (it drives the public API the same way the CLI does)."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KINDS = ("simple", "intent", "specialist", "multi_specialist", "proposal", "unsupported", "follow_up", "burst")
FREQUENT_INTENTS = ("day_summary", "active_issues", "order_plan", "stockout_risk", "expiring_items",
                    "upcoming_deliveries", "staffing", "promo_list", "data_integrity", "transfer_options")


class BatteryError(ValueError):
    pass


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    turns: tuple[str, ...]
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Battery:
    version: int
    store_id: str
    sim_today: str
    mode: str
    cases: tuple[Case, ...]

    @property
    def turn_count(self) -> int:
        return sum(len(c.turns) for c in self.cases)


def load_cases(path: Path | str) -> Battery:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("mode") != "sandbox":
        raise BatteryError("mode must be 'sandbox': the battery never runs in a live case")
    seen: set[str] = set()
    cases: list[Case] = []
    for raw in data.get("cases") or []:
        cid, kind = str(raw.get("id") or ""), str(raw.get("kind") or "")
        if not cid:
            raise BatteryError("every case needs an id")
        if cid in seen:
            raise BatteryError(f"duplicate case id {cid!r}")
        if kind not in KINDS:
            raise BatteryError(f"case {cid!r}: unknown kind {kind!r}")
        turns = tuple(str(t) for t in raw.get("turns") or [] if str(t).strip())
        if not turns:
            raise BatteryError(f"case {cid!r} has no turns")
        seen.add(cid)
        cases.append(Case(cid, kind, turns, dict(raw.get("expect") or {})))
    if not cases:
        raise BatteryError("the battery has no cases")
    return Battery(int(data.get("version", 1)), str(data["store_id"]), str(data["sim_today"]), "sandbox",
                   tuple(cases))


# ---- quality checks ----

_THINK = re.compile(r"</?\s*think\s*>", re.IGNORECASE)
# Scripts a Spanish reply never needs: Cyrillic, Greek, Arabic, Hebrew, Devanagari, Thai, Hangul, CJK, kana.
_FOREIGN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿऀ-ॿ฀-๿"
                      r"ᄀ-ᇿ぀-ヿ㐀-䶿一-鿿가-힯]")
_EN = {"the", "and", "is", "are", "of", "with", "for", "this", "that", "you", "your", "we", "will", "be",
       "on", "it", "to", "have", "has", "store", "sales", "today", "week", "which", "there"}
_ES = {"el", "la", "de", "que", "y", "en", "los", "las", "por", "para", "con", "es", "un", "una", "se",
       "no", "del", "al", "hoy", "tu", "su", "lo", "como", "más", "mas"}
_SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_INTERNAL_WORDS = re.compile(r"\b(orchestrator|peer|peers|backend|agent[_ ]core|tool[_ ]?call|toolset|"
                             r"profile_id|turn_id|case_id)\b", re.IGNORECASE)
_REFUSAL = re.compile(r"no (tengo|cuento con|dispongo|hay datos|hay informaci[oó]n|puedo|manejo|registro|tenemos)|"
                      r"no est[aá] disponible|fuera de (mi|nuestro) alcance|sin datos de|no se encuentra", re.IGNORECASE)

# Things that look like numbers but are identifiers: dates, times, SKU/store codes, ids.
_NOT_NUMBERS = re.compile(r"\d{4}-\d{2}-\d{2}|\b\d{1,2}:\d{2}\b|\b[A-Za-z]+[-_]?\d+\w*|\d+[-_][A-Za-z]\w*")
_NUMBER = re.compile(r"(?<![\w.,])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_SMALL_INT = 10


def _spanish_typo(token: str) -> bool:
    """`de_no`, `de_la`: Spanish function words a model joined with an underscore (L13), not a field name."""
    return all(part in _ES for part in token.split("_"))


def conversation_sources(earlier: list[dict[str, Any]], current: dict[str, Any]) -> tuple[list[str], bool]:
    """What a turn's numbers may be traced to: its own tool results and peer texts plus those of the EARLIER turns of
    the same conversation (a follow-up repeats figures it already fetched, L13). Complete only when every one is."""
    turns = [*earlier, current]
    sources = [str(x) for t in turns for x in (*t.get("tool_results", []), *t.get("peer_texts", []))]
    return sources, all(t.get("results_complete", True) is not False for t in turns)


def looks_like_refusal(text: str) -> bool:
    return bool(_REFUSAL.search(text or ""))


def extract_numbers(text: str) -> list[str]:
    cleaned = _NOT_NUMBERS.sub(" ", text or "")
    return [m.group(0).rstrip(".") for m in _NUMBER.finditer(cleaned)]


def _value(token: str) -> float:
    return float(token.replace(",", ""))


def _decimals(token: str) -> int:
    return len(token.split(".", 1)[1]) if "." in token else 0


def _source_values(sources: list[str]) -> list[float]:
    out: list[float] = []
    for s in sources:
        for m in re.finditer(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?", s):
            try:
                out.append(float(m.group(0)))
            except ValueError:
                continue
    return out


def _traceable(token: str, values: list[float]) -> bool:
    r, tol = _value(token), 0.5 * 10 ** -_decimals(token) + 1e-9
    for v in values:
        for cand in (v, v * 100, abs(v), abs(v) * 100):
            if abs(cand - abs(r)) <= max(tol, 1e-9):
                return True
    return False


# ---- garbled fragments (P12): text a model mangled ----

# Glued words. Spanish has many real words made of two frequent ones (porque, contiene, media, demás, ellas), so
# only pairs that are never a word count: a preposition run into an article (`dela`, `enel`, `conlos`), and `hoy` or
# `usted` run into another word (`hoyusted`, `ustedtiene`).
_GLUED_PAIR = re.compile(
    r"\b(?:de|en|con|por|para|a|que|y)(?:el|la|los|las)\b|\bhoy[a-záéíóúñü]{3,}|[a-záéíóúñü]{2,}usted(?:es)?\b|"
    r"\busted(?:es)?[a-záéíóúñü]{3,}")
_REAL_WORDS = frozenset({"ella", "ellas", "yla", "alas", "ala", "hoyos", "hoyo", "hoya"})  # real words the pattern hits
_GLUED_DIGIT = re.compile(r"\b(?:a|al|con|de|del|el|en|la|las|los|para|por|un|una|y)\d+[\w.,]*", re.IGNORECASE)
# English function words that do not exist in Spanish (so `no`, `a` and `es` are not among them), written in lower
# case: product names are English but capitalised ("Better For You Breakfast Sandwich").
_STRAY_EN = frozenset({"the", "and", "with", "which", "however", "also", "will", "should", "would", "your", "you",
                       "this", "that", "there", "here", "about", "from", "into", "but", "or", "of", "is", "are",
                       "today", "sales", "order", "orders", "store"})
_FULL_WIDTH = re.compile(r"[，。：；！？（）、【】「」]")
_MD_DEBRIS = re.compile(r"(?m)(?:^|\s)\*\*\s*:|\*{3,}\s*$|^\s*\*\*\s*$|^#{1,6}\s*$")


def garbled_fragments(reply: str) -> list[str]:
    """Fragments of a Spanish reply a model mangled: words glued together (`hoyusted`, `dela`) or to a number
    (`en1`), English function words inside Spanish (`and`), full-width punctuation (`，`) and markdown debris (`**:`
    with nothing bold before it, a lone `**` or `#`). Only English inside a reply that is otherwise Spanish counts:
    an English reply is the `non_spanish` flag's."""
    text = reply or ""
    found: list[str] = []
    tokens = re.findall(r"[A-Za-záéíóúñüÁÉÍÓÚÑÜ]+", text)
    words = [w.lower() for w in tokens]
    found += [m.group(0) for m in _GLUED_PAIR.finditer(text.lower()) if m.group(0) not in _REAL_WORDS]
    found += [m.group(0) for m in _GLUED_DIGIT.finditer(text)]
    if sum(w in _ES for w in words) > sum(w in _EN for w in words):
        found += [w for w in tokens if w in _STRAY_EN]  # lower case as written: not a product name
    found += _FULL_WIDTH.findall(text)
    found += [m.group(0).strip() for m in _MD_DEBRIS.finditer(text)]
    return found


def quality(reply: str, tool_results: list[str], question: str = "", complete: bool | None = None) -> dict[str, Any]:
    """Flags: think_tags, foreign_script, garbled, non_spanish, internal_names, untraceable_numbers.
    Numbers are traced against the turn's tool results (and the question). A clipped result (the public trace keeps
    300 chars, ending in an ellipsis) makes the check incomplete: misses are then reported as `unverified_numbers`
    and do not raise the flag. `complete=False` (tool calls whose results the trace does not carry) does the same."""
    text = reply or ""
    flags: list[str] = []
    if _THINK.search(text):
        flags.append("think_tags")
    if _FOREIGN.search(text):
        flags.append("foreign_script")
    fragments = garbled_fragments(text)
    if "�" in text or fragments:
        flags.append("garbled")
    words = re.findall(r"[a-záéíóúñü]+", text.lower())
    en, es = sum(w in _EN for w in words), sum(w in _ES for w in words)
    if en >= 3 and en > es:
        flags.append("non_spanish")
    snake = {t for t in _SNAKE.findall(text) if not _spanish_typo(t)}
    internal = sorted(snake | {m.group(0) for m in _INTERNAL_WORDS.finditer(text)})
    if internal:
        flags.append("internal_names")
    numbers = extract_numbers(text)
    values = _source_values(list(tool_results) + [question])
    misses = [n for n in numbers if not _traceable(n, values)
              and not ("." not in n and "," not in n and abs(_value(n)) <= _SMALL_INT)]
    complete = (complete is not False) and not any(str(r).endswith("…") for r in tool_results)
    untraceable = misses if complete else []
    if untraceable:
        flags.append("untraceable_numbers")
    return {"flags": flags, "internal_names": internal, "numbers_checked": len(numbers),
            "untraceable_numbers": untraceable, "unverified_numbers": [] if complete else misses,
            "sources_complete": complete, "garbled_fragments": fragments}


# ---- trace metrics ----

def trace_metrics(events: list[dict[str, Any]], turn_id: str) -> dict[str, Any]:
    """Tool calls, peer asks and tool results of one turn from GET /api/v1/trace events."""
    tools: dict[str, int] = {}
    peers: list[str] = []
    results: list[str] = []
    peer_texts: list[str] = []
    denials = 0
    result_count = 0
    for e in events:
        p = e.get("payload") or {}
        if str(p.get("turn_id")) != turn_id:
            continue
        core = p.get("core_kind")
        if core == "tool_call":
            name = str(p.get("tool") or "")
            tools[name] = tools.get(name, 0) + 1
            if name == "ask_peer":
                args = p.get("args") or {}
                target = args.get("agent_id") or args.get("target_agent_id") or args.get("target")
                if target and target not in peers:
                    peers.append(str(target))
        elif core == "policy_denial":
            denials += 1
        if core in ("tool_result", "tool_call") and p.get("result"):
            results.append(str(p["result"]))
            result_count += 1
        if core == "peer_exchange" and p.get("text"):
            peer_texts.append(str(p["text"]))
    data_calls = sum(tools.values()) - tools.get("ask_peer", 0)
    return {"tool_calls": sum(tools.values()), "peer_asks": tools.get("ask_peer", 0), "tools": tools,
            "results_complete": result_count >= data_calls,
            "peers": peers, "policy_denials": denials, "tool_results": results, "peer_texts": peer_texts}


# ---- aggregates ----

def percentile(values: list[float], p: float) -> float | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    rank = max(1, math.ceil(p / 100 * len(vals)))
    return vals[rank - 1]


def first_text_seconds(turn: dict[str, Any]) -> float | None:
    """Seconds from sending the turn to its first streamed text, from the backend's `first_text_ms` (P5: the backend
    follows Core's SSE feed). None when the backend did not report it (an older build, or no text streamed)."""
    ms = turn.get("first_text_ms")
    if isinstance(ms, bool) or not isinstance(ms, (int, float)):
        return None
    return round(ms / 1000, 2)


def aggregate(turns: list[dict[str, Any]]) -> dict[str, Any]:
    lat = [t["latency_s"] for t in turns if t.get("latency_s") is not None]
    first = [t["first_text_s"] for t in turns if t.get("first_text_s") is not None]
    failed = [t for t in turns if t.get("status") not in ("done", "waiting_approval")]
    flags: dict[str, int] = {}
    for t in turns:
        for f in (t.get("quality") or {}).get("flags", []):
            flags[f] = flags.get(f, 0) + 1
        for name, ok in (t.get("checks") or {}).items():
            if ok is False:
                flags[f"check:{name}"] = flags.get(f"check:{name}", 0) + 1
    burst = [t for t in turns if t.get("burst")]
    burst_lat = [t["latency_s"] for t in burst if t.get("latency_s") is not None]
    return {
        "turns": len(turns),
        "failed": len(failed),
        "failure_rate": round(len(failed) / len(turns), 3) if turns else None,
        "latency_p50_s": percentile(lat, 50),
        "latency_p95_s": percentile(lat, 95),
        "latency_max_s": max(lat) if lat else None,
        "first_text_turns": len(first),
        "first_text_p50_s": percentile(first, 50),
        "first_text_p95_s": percentile(first, 95),
        "tool_calls_total": sum(t.get("tool_calls") or 0 for t in turns),
        "peer_asks_total": sum(t.get("peer_asks") or 0 for t in turns),
        "flag_counts": dict(sorted(flags.items())),
        "garbled_fragments_total": sum(len((t.get("quality") or {}).get("garbled_fragments") or []) for t in turns),
        "garbled_turns": sum(1 for t in turns if (t.get("quality") or {}).get("garbled_fragments")),
        "burst": {"turns": len(burst), "failed": sum(1 for t in burst if t in failed),
                  "latency_max_s": max(burst_lat) if burst_lat else None,
                  "latency_p50_s": percentile(burst_lat, 50)} if burst else None,
    }


def _key(t: dict[str, Any]) -> tuple[str, int]:
    return (str(t["case_id"]), int(t.get("turn_index", 0)))


def _flags(t: dict[str, Any]) -> list[str]:
    q = list((t.get("quality") or {}).get("flags", []))
    q += [f"check:{k}" for k, ok in (t.get("checks") or {}).items() if ok is False]
    return q


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    a_turns = {_key(t): t for t in after.get("turns", [])}
    rows = []
    for t in before.get("turns", []):
        k = _key(t)
        o = a_turns.get(k)
        row: dict[str, Any] = {"case_id": k[0], "turn_index": k[1], "before_s": t.get("latency_s"),
                               "before_status": t.get("status")}
        if o is not None:
            b_lat, a_lat = t.get("latency_s"), o.get("latency_s")
            row.update({"after_s": a_lat, "after_status": o.get("status"),
                        "latency_delta_s": round(a_lat - b_lat, 2) if None not in (a_lat, b_lat) else None,
                        "tool_calls": [t.get("tool_calls"), o.get("tool_calls")],
                        "peer_asks": [t.get("peer_asks"), o.get("peer_asks")],
                        "new_flags": sorted(set(_flags(o)) - set(_flags(t))),
                        "fixed_flags": sorted(set(_flags(t)) - set(_flags(o)))})
        rows.append(row)
    ab, aa = before.get("aggregate") or {}, after.get("aggregate") or {}
    agg = {}
    for name in ("latency_p50_s", "latency_p95_s", "latency_max_s", "first_text_p50_s", "first_text_p95_s",
                 "failure_rate", "tool_calls_total", "peer_asks_total", "garbled_fragments_total", "garbled_turns"):
        b, a = ab.get(name), aa.get(name)
        agg[name] = {"before": b, "after": a,
                     "delta": round(a - b, 3) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None}
    return {"before": before.get("label"), "after": after.get("label"), "rows": rows, "aggregate": agg,
            "flag_counts": {"before": ab.get("flag_counts", {}), "after": aa.get("flag_counts", {})},
            "burst": {"before": ab.get("burst"), "after": aa.get("burst")}}


# ---- Markdown ----

def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def render_markdown(run: dict[str, Any]) -> str:
    agg = run["aggregate"]
    lines = [f"# Stress battery: {run['label']}", "",
             f"Started {run.get('started_at')} on store {run.get('store_id')} at {run.get('sim_today')} "
             f"(sandbox cases). Estimated LLM calls: {_fmt(run.get('llm_calls_estimate'))}.", "",
             "| case | turn | status | latency s | tool calls | peer asks | flags |",
             "|---|---|---|---|---|---|---|"]
    for t in run["turns"]:
        lines.append(f"| {t['case_id']} | {t.get('turn_index', 0)} | {t.get('status')} | {_fmt(t.get('latency_s'))} | "
                     f"{_fmt(t.get('tool_calls'))} | {_fmt(t.get('peer_asks'))} | {', '.join(_flags(t)) or '-'} |")
    lines += ["", "## Aggregates", "",
              f"- turns: {agg['turns']}, failed: {agg['failed']} (failure rate {_fmt(agg['failure_rate'])})",
              f"- latency p50 {_fmt(agg['latency_p50_s'])} s, p95 {_fmt(agg['latency_p95_s'])} s, "
              f"max {_fmt(agg['latency_max_s'])} s",
              f"- first text p50 {_fmt(agg.get('first_text_p50_s'))} s, p95 {_fmt(agg.get('first_text_p95_s'))} s "
              f"({_fmt(agg.get('first_text_turns'))} turns streamed text)",
              f"- tool calls {agg['tool_calls_total']}, peer asks {agg['peer_asks_total']}",
              f"- flags: {json.dumps(agg['flag_counts'], ensure_ascii=False) if agg['flag_counts'] else 'none'}",
              f"- garbled fragments {_fmt(agg.get('garbled_fragments_total'))} in {_fmt(agg.get('garbled_turns'))} turns",
              f"- burst: {json.dumps(agg['burst']) if agg.get('burst') else 'none'}", ""]
    return "\n".join(lines)


def render_compare_markdown(cmp: dict[str, Any]) -> str:
    lines = [f"# Stress battery compare: {cmp['before']} -> {cmp['after']}", "",
             "| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in cmp["rows"]:
        tc, pa = r.get("tool_calls") or ["-", "-"], r.get("peer_asks") or ["-", "-"]
        lines.append(f"| {r['case_id']} | {r['turn_index']} | {_fmt(r.get('before_s'))} | {_fmt(r.get('after_s'))} | "
                     f"{_fmt(r.get('latency_delta_s'))} | {r.get('before_status')} -> {r.get('after_status', '-')} | "
                     f"{_fmt(tc[0])} -> {_fmt(tc[1])} | {_fmt(pa[0])} -> {_fmt(pa[1])} | "
                     f"{', '.join(r.get('new_flags') or []) or '-'} | {', '.join(r.get('fixed_flags') or []) or '-'} |")
    lines += ["", "## Aggregates", "", "| metric | before | after | delta |", "|---|---|---|---|"]
    for name, v in cmp["aggregate"].items():
        lines.append(f"| {name} | {_fmt(v['before'])} | {_fmt(v['after'])} | {_fmt(v['delta'])} |")
    lines += ["", f"- flags before: {json.dumps(cmp['flag_counts']['before'], ensure_ascii=False)}",
              f"- flags after: {json.dumps(cmp['flag_counts']['after'], ensure_ascii=False)}",
              f"- burst before: {json.dumps(cmp['burst']['before'])}",
              f"- burst after: {json.dumps(cmp['burst']['after'])}", ""]
    return "\n".join(lines)
