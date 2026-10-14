"""The `x-agent-*` OpenAPI marks of the internal API: which operations an agent tool calls (D85, G2).

Agent-Core builds its tools from the marked operations of /openapi.json. Only metadata: nothing here
changes what a route does. `x-agent-description` is the text the model reads (the tool docstrings
the Agent-Core tools carried before they were generated), so editing it changes what the model is told.
Adding `x-agent-tool` to a route is what makes it callable by an agent; the public API is never marked.
"""
from typing import Any


def _tool(name: str, effect: str, description: str, more: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"x-agent-tool": True, "x-agent-name": name, "x-agent-effect": effect,
            "x-agent-description": description, **(more or {})}


AGENT_TOOLS: dict[str, dict[str, Any]] = {
    "get_kpis": _tool(
        "get_kpis", "read",
        """KPIs for the store over a date window (`date_from` to `date_to`, ISO dates).

One call covers the whole window: use it once instead of one call per day.

Returns sales and traffic figures plus the two losses in USD: `waste_usd` and
`lost_sales_usd`, the latter as {low, mid, high} (a range, never a point value; quote
all three). `lost_sales_usd` may be absent; never estimate it yourself.
Results carry `store_display_name`: use it, never the store code.""",
    ),
    "get_snapshot": _tool(
        "get_snapshot", "read",
        """Everything a specialist usually needs, in one call. Call it FIRST.

Returns store_display_name, as_of, window {from, to}, `kpis` (net_sales, transactions,
waste_usd, lost_sales_usd {low, mid, high}, tx_per_staff_hour), `top_issues` (up to 5
Issues with options), `integrity` (up to 3 {kind, exposure_usd, summary}), `order_plan`
{due_today, due_tomorrow, top_lines}, `suppliers` (on_time_pct, fill_pct,
next_delivery), pending_proposals, recent_decisions and cache_age_s.
A field may be absent; never estimate it yourself. Do not re-fetch this data.""",
    ),
    "get_briefing": _tool(
        "get_briefing", "read",
        """The precomputed briefing of the case. Call it FIRST on every question.

Returns `snapshot` (kpis, top_issues with options, integrity, order_plan, suppliers,
pending_proposals, recent_decisions), `headline` (up to 5 facts computed by code, each
with value, unit and source) and `suggested_focus` (issue_ids worth the manager's
attention). Use the issue_id and option_id of `top_issues` to propose.
A field may be absent; never estimate it yourself.""",
    ),
    "get_day_summary": _tool(
        "get_day_summary", "read",
        """Summary of one day (ISO date) for the store: sales, traffic, waste, incidents.""",
    ),
    "get_issues": _tool(
        "get_issues", "read",
        """Active issues for the store relevant to your role, most urgent first.

`category` is "operational" (the backend default when omitted), "integrity"
(data-quality issues, with `exposure_usd`) or "all"; `kind` narrows to one issue kind.

Each issue has: issue_id, kind, sku?, supplier_id?, store_display_name, as_of,
severity_usd, `evidence` [{metric, value, unit, period, source}], `data_caveats` [str]
and `options` (up to 4, always including `do_nothing` with its cost). Each option has:
option_id, action_type, params, expected_benefit_usd {low, mid, high}, cost_usd,
net_usd_mid, loss_impact {waste_usd_delta, lost_sales_usd_delta}, confidence {score
0-1, n_backtest, method}, tier (N0-N3, computed by the backend), tier_reasons, urgency
{deadline_date?, reason}, risk, if_act and if_not. Present only these options.
Optional fields (sku, supplier_id, deadline_date, if_act, if_not) are absent when the
backend has no value: a field may be absent; never estimate it yourself.
An empty list means there are no issues.""",
    ),
    "explain_metric": _tool(
        "explain_metric", "read",
        """How a metric is defined and computed (not its value). Use before explaining one.""",
    ),
    "get_order_plan": _tool(
        "get_order_plan", "read",
        """The order plan (draft) computed by the backend, one line per SKU.

Lines carry the quantity plus: service_level_target, order_deadline,
projected_stockout_date, stockout_risk_without_order, vs_current_practice
{received_to_sold, qty_delta} and min_order_warning.
Any of these may be absent; never estimate it yourself.
If one is absent, say it is not available. Results carry `store_display_name`.""",
    ),
    "project_inventory": _tool(
        "project_inventory", "read",
        """Projected stock of one SKU for the next `horizon` days (1-30), from the backend.

Includes the projected stockout date when there is one. Fields may be absent; never
estimate it yourself.""",
    ),
    "forecast_demand": _tool(
        "forecast_demand", "read",
        """Forecast demand of one SKU on a FUTURE date, from the backend's model.

Use it for any question about future demand; never estimate a forecast yourself.
`target_date` must be after the case's current date. Returns `qty` (the p50),
`qty_range` {p10, p50, p90} (quote the range, never only the point), optional
`quantiles`, `censored_share` (share of history with stockouts), `weather_kind`
("observed"), `model`, `model_version` and `forecast_origin`. If `forecast_available`
is false the forecast is unavailable: say so.""",
    ),
    "forecast_daily_flow": _tool(
        "forecast_daily_flow", "read",
        """Forecast the store's transactions and average ticket on a FUTURE date (daily).

Use it for any question about future traffic; never estimate a forecast yourself.
`target_date` must be after the case's current date. Returns `transactions`
{p10, p50, p90}, `footfall` (null when there is no data), `avg_ticket`
{p10, p50, p90}, `granularity` ("daily"), `model` and `forecast_origin`. Quote the
range and the model. If `forecast_available` is false the forecast is unavailable.""",
    ),
    "get_supplier_performance": _tool(
        "get_supplier_performance", "read",
        """Supplier lead times and delays for the store, as computed by the backend.

Fields may be absent; never estimate it yourself.""",
    ),
    "get_history": _tool(
        "get_history", "read",
        """Past decisions and recorded events for the store, as the backend stores them.

A decision's measured result is only present once the backend has measured it; it may
be absent; never estimate it yourself, say the result is not available yet.""",
    ),
    "evaluate_promo": _tool(
        "evaluate_promo", "read",
        """Backend-computed evaluation (uplift, cost, verdict) of a promotion.

Fields may be absent; never estimate it yourself.""",
    ),
    "recall_experiences": _tool(
        "recall_experiences", "read",
        """Recall past experiences of this store from long-term memory (Backboard).

Returns entries with text, kind, created_at and optionally decision_id and score. They
are leads, not facts: re-verify any number with get_history or evaluate_promo using the
decision_id before citing it. A `warning` means memory is unavailable: use history only.""",
        more={"x-agent-warning": True},
    ),
    "check_compliance": _tool(
        "check_compliance", "read",
        """Whether approved decisions were carried out, as measured by the backend.

Without `decision_id` it covers all approved decisions of the case, otherwise only
that one. Returns the checked decisions; each has `decision_id`, `execution_status`
(executed, not_executed or partial) and, once the horizon passed, a `diagnosis`:
`not_executed`, `within_range`, `external_event` (a registered event overlaps the
horizon) or `forecast_error`, with the observed vs simulated figures (label
`backtest`). Only order-quantity actions are measurable; a field may be absent; never
estimate it yourself. An empty list means there is nothing to check.""",
        more={"x-agent-row-limit": 1000},
    ),
    "get_transfer_options": _tool(
        "get_transfer_options", "read",
        """Transfer options between stores, computed by the backend (optionally for one `sku`).

Returns `options`: {option_id, sku, product_name, from_store, to_store, to_store_name,
qty, surplus_units, deficit_units, transfer_cost_usd, waste_avoided_usd,
lost_sales_avoided_usd, net_usd, confidence, expires_on, rationale_es}, plus
`do_nothing` and `assumptions` (the cost assumptions). Quote the confidence, the cost
assumptions and the do-nothing comparison. A field may be absent; never estimate it.""",
    ),
    "get_inventory_status": _tool(
        "get_inventory_status", "read",
        """Stock status per SKU: on hand, days_of_cover, status and the next delivery.

`sort` is "days_of_cover" (emptiest shelf first, the default), "turnover" (fastest
first) or "slow" (slow movers with the most money tied up first); `limit` is 1-50.
Each item has `days_of_cover`, `status` (critical when the cover ends before the next
delivery, watch or ok) with `status_reason`, `next_delivery_date`,
`projected_stockout_date` and `forecast_outflow_units`. A field may be absent; never
estimate it yourself. Use it for any question about what is running out or what is
covered until the next delivery.""",
    ),
    "get_expiring": _tool(
        "get_expiring", "read",
        """Items about to expire in the next `days` (1-30, default 7) and the waste they imply.

Returns `items` (the largest lots first: sku, product_name, expiring_units,
expiry_date, `waste_usd` as {low, mid, high} - a range, quote all three), `by_day`
(the waste_usd range per expiry date), `total_items` and `total_waste_usd`. Lot ages
are inferred, not measured. Use it for any question about expiry or waste to come.""",
    ),
    "get_deliveries": _tool(
        "get_deliveries", "read",
        """The delivery calendar of the next `days` (1-14, default 7): which supplier comes when.

Returns `days`, one entry per date with its `deliveries`: open purchase orders (kind
open_po, with po_id, expected_date, lines and value_usd) and scheduled supplier slots
(kind scheduled, no lines). Use it to answer when a supplier arrives; never guess a
delivery date.""",
    ),
    "get_staffing": _tool(
        "get_staffing", "read",
        """Recommended staff hours per future day (daily only; there is no hourly staffing).

`days` is 1-14, default 7. Each day has `forecast_transactions` and
`recommended_staff_hours` as {low, mid, high}; `planned_staff_hours` and `gap_hours`
are null because there is no roster in the data. `benchmark` gives the format's
transactions per staff hour. Say plainly that the data is daily when asked about hours.""",
    ),
    "get_promos": _tool(
        "get_promos", "read",
        """Promotions with their audit verdict and evaluation.

`status` is "active", "upcoming" or "past" (all when omitted); `days` (1-365, default
14) is the window around the case date. Each item has `audit_verdict` (block, allow or
insufficient_evidence) and, only for promos that already ended, an `evaluation`
(uplift_pct, expected_uplift_pct, confidence). A promo without evaluation has no result
yet: never claim an uplift.""",
    ),
    "get_outlook": _tool(
        "get_outlook", "read",
        """Outlook for the next `days` (1-7, default 2: tomorrow and the day after).

Each day has `net_sales`, `transactions` and `avg_ticket` as {low, mid, high},
`expected_waste_usd` and `expected_lost_sales_usd` as {low, mid, high} ranges (quote
all three), `weather` (null without a feed) and `weather_note`. Every day is a
projection. Use it for any question about today, tomorrow or the next days.""",
    ),
    "get_issue_analysis": _tool(
        "get_issue_analysis", "read",
        """The deterministic analysis of one issue (use an issue_id from get_issues).

Returns the `recommendation` (option_id, label), its `pros` and `cons`, `confidence`
{score, calibrated}, `tier`, `deadline`, `impact_usd` {low, mid, high}, `problem` and
`dialog`: `why`, `if_accept`, `if_not_act` (the do_nothing case) and `alternatives`
with their net_usd_mid. Always give the confidence and the do_nothing comparison with
a recommendation.""",
    ),
    "audit_promo": _tool(
        "audit_promo", "read",
        """Audit a promotion idea against past evidence BEFORE recommending it.

Returns {verdict, recommendation, similar, alternative, reasons, noise_floor_pct}.
`verdict` is `block` (do not recommend it), `allow` or `insufficient_evidence`.
`similar` lists comparable past promos (each may carry this store's
`store_evaluation`), `alternative` a better idea when there is one and `reasons` the
evidence. On `block`, recommend `do_nothing`. A field may be absent; never estimate
it yourself.""",
        more={"x-agent-replay": "interrupted"},
    ),
    "classify_text": _tool(
        "classify_text", "read",
        """Classify free text with Jev into a fixed label set.

`kind` is `rejection_reason` (why the manager rejected a proposal) or
`deviation_cause` (why a decision was not carried out as planned). Returns
{label, confidence, model, calibrated, adapter} plus `warning` when an earlier
classifier failed. The label is `needs_review` (rejection_reason) or `no_match`
(deviation_cause) when nothing fits or confidence is under 0.4. `confidence` only
measures how well the text fits the label; it is not the confidence of a
recommendation, and `calibrated` false means a fallback model answered. Quote the
label as returned; never invent a category.""",
        more={"x-agent-replay": "interrupted"},
    ),
    "record_event": _tool(
        "record_event", "write",
        """Record an operational event (holiday, outage, promo...) over a date range.""",
    ),
    "propose_action": _tool(
        "propose_action", "write",
        """Propose one option of an issue. NOTHING is executed: the manager decides.

Send only the `issue_id` and `option_id` returned by get_issues, and a short
`rationale` in prose. The backend copies action_type, params and tier from the stored
option; you cannot set or change them. Returns the pending proposal (or an error). The
call carries an `Idempotency-Key` (case + issue + option), so repeating it after a
timeout does not create a second proposal.""",
        more={"x-agent-idempotency": ["issue_id", "option_id"]},
    ),
    "save_manager_note": _tool(
        "save_manager_note", "write",
        """Save a note the manager asked to record (a closure, an event, supplier news...).

Call it when the manager asks to note, remember or record something, or states a fact
about future operations. `text` is the manager's own words; `category` defaults to
`eventos`; `date_from` / `date_to` (ISO dates) bound the period it applies to;
`impact` is a short free label when the manager gave one. Returns {saved, memory_id,
event_id, category, date_from, date_to}. Only say it was saved when `saved` is true.
A write of the manager's own words, done by backend code; it changes no store data.""",
    ),
    "propose_transfer": _tool(
        "propose_transfer", "write",
        """Propose one transfer option. NOTHING is executed: the manager approves or rejects.

Send only an `option_id` returned by get_transfer_options and a short `rationale`. The
backend copies the transfer from the stored option and creates a pending proposal. The
call carries an `Idempotency-Key` (case + option), so a retry after a timeout does not
create a second proposal.""",
        more={"x-agent-idempotency": ["option_id"]},
    ),
}
