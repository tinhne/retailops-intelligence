"""Answer templates of the deterministic provider (PROMPT_DESIGN.md §9), version 1.

Each template turns the results of its intent's tool plan into a candidate answer. Every fact and
metric is built from one tool record and cites that record's ref, every number is copied from a
tool result, and the wording follows the prompt's rules: plain text, product vocabulary, exposure
as "value at risk", the priority caveat, store-time-zone timestamps. The output passes the same
validator as a live model's answer.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domains.ai.providers.deterministic.plans import (
    PlanContext,
    Results,
    product_candidates,
    records,
    start_of_yesterday,
)
from app.domains.ai.providers.deterministic.router import Intent, RoutedIntent, Unsupported
from app.domains.exceptions.rules.base import format_local
from app.domains.exceptions.rules.order_fulfillment_overdue import STATUS_ACTIONS
from app.domains.orders.models import OrderStatus

PRIORITY_CAVEAT = (
    "The priority score is a ranking aid built from severity, affected orders, value at risk, "
    "deadline and time open; it is not a measure of business impact, and its weights are defaults "
    "not yet validated with operators."
)
EXPOSURE_CAVEAT = (
    "Value at risk (exposure) is the gross order-line value of the affected orders (BR-404), not a "
    "measured financial impact; it is not additive across exceptions."
)
ESTIMATE_CAVEAT = (
    "Sales velocity and days of cover are estimates from a moving average of past sales "
    "(BR-150..152); they ignore seasonality and promotions."
)
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
SUPPORTED_QUESTIONS = (
    "what needs attention today, the highest-priority exceptions, overdue orders, SKUs at risk of "
    "overselling, what changed since yesterday, why an exception has its severity or priority, "
    "what the team should prioritise, and lookups of a product, an order, imports or trends"
)


@dataclass(frozen=True)
class TemplateInfo:
    as_of: datetime
    timezone: str
    currency: str
    store_name: str


# --- small builders ------------------------------------------------------------------------------


def clip(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def key(record: dict[str, Any]) -> str:
    ref = record["ref"]
    return f"{ref['type']}:{ref['id']}"


def first(results: Results, name: str) -> dict[str, Any] | None:
    found = records(results, name)
    return found[0] if found else None


def result_key(results: Results, name: str) -> str | None:
    ref = (results.get(name) or {}).get("result_ref")
    return f"{ref['type']}:{ref['id']}" if isinstance(ref, dict) else None


def total(results: Results, name: str) -> int:
    return int((results.get(name) or {}).get("total_available") or 0)


def when(value: Any, info: TemplateInfo) -> str:
    if not value:
        return "not set"
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return format_local(moment, info.timezone)


def fact(text: str, *refs: str | None) -> dict[str, Any]:
    return {"text": clip(text), "refs": [r for r in refs if r]}


def metric(
    label: str, value: Any, unit: str, *refs: str | None, formula: str | None = None
) -> dict[str, Any]:
    return {
        "label": label,
        "value": str(value),
        "unit": unit,
        "formula": formula,
        "refs": [r for r in refs if r],
    }


def recommend(text: str, rationale: str) -> dict[str, Any]:
    return {"text": clip(text), "rationale": clip(rationale)}


def answer(
    summary: str,
    *,
    facts: list[dict[str, Any]] | None = None,
    metrics: list[dict[str, Any]] | None = None,
    estimates: list[dict[str, Any]] | None = None,
    recommendations: list[dict[str, Any]] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "summary": clip(summary, 600),
        "facts": (facts or [])[:12],
        "metrics": (metrics or [])[:12],
        "estimates": (estimates or [])[:5],
        "recommendations": (recommendations or [])[:5],
        "limitations": (limitations or [])[:8],
        "references": [],
    }


def exception_line(rec: dict[str, Any], info: TemplateInfo, *, exposure: bool = False) -> str:
    owner = (rec.get("assignee") or {}).get("display_name") or "unassigned"
    due = when(rec.get("due_at"), info)
    parts = [
        f"{rec['reference']} {rec.get('title', '')}: {rec['severity']}, {rec['priority_band']} "
        f"(score {rec['priority_score']}), {rec['status']}, due {due}"
        + (" (past due)" if rec.get("is_past_due") else ""),
        owner,
    ]
    if exposure and rec.get("exposure_amount") not in (None, "0", "0.00"):
        parts.append(f"value at risk {rec['exposure_amount']} {info.currency}")
    return "; ".join(parts) + "."


def refs_list(items: list[dict[str, Any]], limit: int = 5) -> str:
    return ", ".join(str(r.get("reference") or r["ref"]["label"]) for r in items[:limit])


# --- question templates --------------------------------------------------------------------------


def attention_today(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    board = first(res, "summary") or {}
    agg = key(board) if board else None
    active = board.get("active_exceptions", {})
    overdue_now = board.get("orders", {}).get("overdue_now", 0)
    count, p1 = active.get("total", 0), active.get("by_band", {}).get("P1", 0)
    past_due, unassigned = active.get("past_due", 0), active.get("unassigned", 0)
    if count:
        summary = (
            f"{count} active exceptions: {p1} in priority band P1, {past_due} past their due "
            f"time and {unassigned} unassigned. {overdue_now} orders are past their ship-by right "
            "now."
        )
    else:
        summary = (
            f"There are no active exceptions. {overdue_now} orders are past their ship-by now."
        )
    top = records(res, "active")
    overdue = records(res, "overdue")
    facts = [fact(exception_line(rec, info), key(rec)) for rec in top[:6]]
    facts += [
        fact(
            f"Order {o['order_number']} ({o['status']}) is {o['hours_overdue']} hours past its "
            f"ship-by of {when(o.get('ship_by'), info)}.",
            key(o),
        )
        for o in overdue[:3]
    ]
    metrics = [
        metric("Active exceptions", count, "exceptions", agg),
        metric("P1 exceptions", p1, "exceptions", agg),
        metric("Past-due exceptions", past_due, "exceptions", agg),
        metric("Unassigned active exceptions", unassigned, "exceptions", agg),
        metric(
            "Orders past ship-by now",
            overdue_now,
            "orders",
            agg,
            formula="committed status and as_of after ship_by (BR-202)",
        ),
    ]
    urgent = [rec for rec in top if rec["priority_band"] == "P1" or rec.get("is_past_due")]
    recs = []
    if urgent:
        recs.append(
            recommend(
                f"Start with the P1 and past-due exceptions: {refs_list(urgent)}.",
                "They rank highest by priority score or their due time has passed.",
            )
        )
    if overdue:
        recs.append(
            recommend(
                "Work the orders past their ship-by, oldest first: "
                + ", ".join(o["order_number"] for o in overdue[:5])
                + ".",
                "These orders are overdue right now (BR-202).",
            )
        )
    if unassigned:
        recs.append(
            recommend(
                "Assign owners to the unassigned active exceptions in the exception inbox.",
                "Unassigned exceptions have nobody working on them.",
            )
        )
    return answer(
        summary, facts=facts, metrics=metrics, recommendations=recs, limitations=[PRIORITY_CAVEAT]
    )


def top_priority(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    found = records(res, "top")
    count = total(res, "top")
    filters = ""
    if r.severities:
        filters += " with severity " + " or ".join(s.value for s in r.severities)
    if r.exception_types:
        filters += " of type " + " or ".join(t.value for t in r.exception_types)
    if not found:
        return answer(
            f"No active exceptions match{filters}.",
            metrics=[
                metric("Matching active exceptions", count, "exceptions", result_key(res, "top"))
            ],
            limitations=[
                "Only active exceptions (OPEN, ACKNOWLEDGED, IN_PROGRESS, REOPENED) count."
            ],
        )
    first = found[0]
    summary = (
        f"{count} active exceptions match{filters}. The highest priority is {first['reference']} "
        f"with score {first['priority_score']} ({first['priority_band']}, {first['severity']})."
    )
    return answer(
        summary,
        facts=[fact(exception_line(rec, info, exposure=True), key(rec)) for rec in found[:12]],
        metrics=[
            metric("Matching active exceptions", count, "exceptions", result_key(res, "top")),
            metric(
                "Highest priority score",
                first["priority_score"],
                "points",
                key(first),
                formula="S + A + E + D + T, capped at 100 (PRIORITY_MODEL)",
            ),
        ],
        recommendations=[
            recommend(
                f"Open {first['reference']} first and follow its recommended action.",
                "It has the highest priority score among the matching exceptions.",
            )
        ],
        limitations=[PRIORITY_CAVEAT, EXPOSURE_CAVEAT],
    )


def overdue_orders(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    found = records(res, "overdue")
    count = int((res.get("overdue") or {}).get("total_overdue") or 0)
    agg = result_key(res, "overdue")
    if not found:
        return answer(
            "No orders are past their ship-by right now.",
            metrics=[metric("Orders past ship-by", count, "orders", agg)],
            limitations=["Overdue means a committed status and as_of after ship_by (BR-202)."],
        )
    oldest = found[0]
    summary = (
        f"{count} orders are past their ship-by right now. The oldest is {oldest['order_number']} "
        f"({oldest['status']}), {oldest['hours_overdue']} hours past its ship-by."
    )
    facts = []
    for o in found[:10]:
        exception = (o.get("exception") or {}).get("ref")
        tail = f"exception {exception['label']}" if exception else "no exception yet"
        facts.append(
            fact(
                f"Order {o['order_number']} is {o['status']}, {o['hours_overdue']} hours past its "
                f"ship-by of {when(o.get('ship_by'), info)}; severity if detected "
                f"{o['severity_if_detected']}; {tail}.",
                key(o),
                f"exception:{exception['id']}" if exception else None,
            )
        )
    recs = []
    for status in (OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.READY_TO_SHIP):
        group = [o["order_number"] for o in found if o["status"] == status.value]
        if group:
            recs.append(
                recommend(
                    f"{STATUS_ACTIONS[status]} Orders: {', '.join(group[:6])}.",
                    f"These overdue orders are in {status.value} (ORD-OVERDUE recommended action).",
                )
            )
    limitations = ["Overdue means a committed status and as_of after ship_by (BR-202)."]
    if any(not o.get("exception") for o in found):
        limitations.append(
            "Some overdue orders have no exception yet: they became overdue after the last "
            "evaluation run, and the next run will create them."
        )
    return answer(
        summary,
        facts=facts,
        metrics=[
            metric(
                "Orders past ship-by",
                count,
                "orders",
                agg,
                formula="committed status and as_of after ship_by (BR-202)",
            ),
            metric(
                "Hours past ship-by (oldest order)", oldest["hours_overdue"], "hours", key(oldest)
            ),
        ],
        recommendations=recs,
        limitations=limitations,
    )


def oversell_risk(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    risk, oversold = records(res, "risk"), records(res, "oversold")
    n_risk, n_oversold = total(res, "risk"), total(res, "oversold")
    summary = (
        f"{n_risk} products are at risk of overselling and {n_oversold} are already oversold."
        if n_risk or n_oversold
        else "No products are at risk of overselling or oversold right now."
    )
    facts, metrics = [], []
    for rec in risk:
        product = rec["primary_entity"]["ref"]
        position = first(res, f"position:{product['id']}")
        if position:
            facts.append(
                fact(
                    f"{position['ref']['label']}: available {position['available']}, pending "
                    f"demand {position['pending_demand']}, potential shortage "
                    f"{position['potential_shortage']}, incoming {position['incoming']}.",
                    key(position),
                    key(rec),
                )
            )
            metrics.append(
                metric(
                    f"Potential shortage {product['label'].split(' · ')[0]}",
                    position["potential_shortage"],
                    "units",
                    key(position),
                    formula="pending_demand − available (BR-403)",
                )
            )
        else:
            facts.append(fact(f"At risk: {exception_line(rec, info)}", key(rec)))
    facts += [fact(f"Already oversold: {exception_line(rec, info)}", key(rec)) for rec in oversold]
    metrics = [
        metric("Products at oversell risk", n_risk, "products", result_key(res, "risk")),
        metric("Products already oversold", n_oversold, "products", result_key(res, "oversold")),
        *metrics,
    ]
    recs = []
    if risk:
        recs.append(
            recommend(
                "Consider pausing the listing or confirming incoming stock for: "
                + ", ".join(
                    rec["primary_entity"]["ref"]["label"].split(" · ")[0] for rec in risk[:6]
                )
                + ".",
                "Pending orders would exceed available stock if they are paid (BR-403).",
            )
        )
    if oversold:
        recs.append(
            recommend(
                f"Confirm physical stock with a cycle count for the oversold products "
                f"({refs_list(oversold)}), then expedite incoming stock or contact the affected "
                "customers about a delay.",
                "Committed demand already exceeds on-hand stock (INV-OVERSOLD recommended action).",
            )
        )
    return answer(
        summary,
        facts=facts,
        metrics=metrics,
        recommendations=recs,
        limitations=["Oversell risk counts only unpaid orders (CREATED, PAYMENT_PENDING)."],
    )


def changes_since_yesterday(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    since = start_of_yesterday(PlanContext(as_of=info.as_of, timezone=info.timezone))
    trends = first(res, "trends") or {}
    placed = trends.get("series", {}).get("orders_placed", [])
    new, resolved = records(res, "new"), records(res, "resolved")
    n_new, n_resolved = total(res, "new"), total(res, "resolved")
    summary = (
        f"Since the start of yesterday ({when(since, info)}), {n_new} exceptions were detected "
        f"and {n_resolved} were resolved."
    )
    metrics = [
        metric("Exceptions detected since yesterday", n_new, "exceptions", result_key(res, "new")),
        metric(
            "Exceptions resolved since yesterday",
            n_resolved,
            "exceptions",
            result_key(res, "resolved"),
        ),
    ]
    facts = []
    if len(placed) == 2 and trends:
        summary += f" Orders placed: {placed[0]} yesterday and {placed[1]} today so far."
        metrics += [
            metric("Orders placed yesterday", placed[0], "orders", key(trends)),
            metric("Orders placed today so far", placed[1], "orders", key(trends)),
        ]
    facts += [fact(f"New: {exception_line(rec, info)}", key(rec)) for rec in new[:6]]
    facts += [
        fact(
            f"Resolved: {rec['reference']} {rec.get('title', '')} ({rec.get('resolution_code')}).",
            key(rec),
        )
        for rec in resolved[:3]
    ]
    for item in records(res, "imports")[:3]:
        summ = item.get("summary", {})
        facts.append(
            fact(
                f"{item['ref']['label']}: {item['status']}, {summ.get('rows_with_errors', 0)} rows "
                f"with errors and {summ.get('rows_with_warnings', 0)} with warnings.",
                key(item),
            )
        )
    new_p1 = [rec for rec in new if rec["priority_band"] == "P1" and rec["status"] != "RESOLVED"]
    recs = [
        recommend(
            f"Review the new P1 exceptions first: {refs_list(new_p1)}."
            if new_p1
            else "Review the newly detected exceptions in the inbox, highest priority first.",
            "New exceptions have not been triaged yet.",
        )
    ]
    return answer(
        summary,
        facts=facts,
        metrics=metrics,
        recommendations=recs,
        limitations=["Today is a partial day (so far), in the store time zone."],
    )


def evidence_value(item: dict[str, Any], info: TemplateInfo) -> str:
    """An evidence value for display: timestamps in the store time zone, units appended."""
    value = item.get("value")
    if isinstance(value, str) and _TIMESTAMP.match(value):
        return when(value, info)
    unit = f" {item['unit']}" if item.get("unit") else ""
    return f"{value}{unit}"


def _evidence_facts(
    rec: dict[str, Any], info: TemplateInfo, limit: int = 6
) -> list[dict[str, Any]]:
    facts = []
    for item in rec.get("evidence") or []:
        if item.get("is_estimate") or item.get("value") in (None, ""):
            continue
        source = item.get("source")
        facts.append(
            fact(
                f"{item.get('label')}: {evidence_value(item, info)}.",
                key(rec),
                f"{source['type']}:{source['id']}" if isinstance(source, dict) else None,
            )
        )
    return facts[:limit]


def _history_facts(
    history: dict[str, Any] | None, rec: dict[str, Any], info: TemplateInfo
) -> list[dict[str, Any]]:
    if not history:
        return []
    facts = []
    if history.get("reopen_count"):
        facts.append(fact(f"Reopened {history['reopen_count']} times.", key(rec)))
    for event in history.get("events") or []:
        payload = event.get("payload_summary") or {}
        if event["event_type"] == "SEVERITY_CHANGED" and payload.get("from"):
            facts.append(
                fact(
                    f"Severity changed from {payload['from']} to {payload.get('to')} on "
                    f"{when(event['occurred_at'], info)}.",
                    key(rec),
                )
            )
        elif event["event_type"] == "REOPENED":
            facts.append(
                fact(
                    f"Reopened on {when(event['occurred_at'], info)} "
                    f"({payload.get('reason', 'no reason recorded')}).",
                    key(rec),
                )
            )
    notes = history.get("notes") or []
    if notes:
        latest = notes[0]
        facts.append(
            fact(
                f"Latest note by {latest.get('author_display_name') or 'a former user'} on "
                f"{when(latest.get('created_at'), info)} ({latest.get('source')}).",
                key(rec),
            )
        )
    return facts[:3]


def _order_facts(orders: list[dict[str, Any]], info: TemplateInfo) -> list[dict[str, Any]]:
    facts = []
    for o in orders[:3]:
        overdue = f", {o['hours_overdue']} hours past ship-by" if o.get("is_overdue") else ""
        mismatch = (
            f", total {o['total']} vs expected {o['expected_total']}"
            if o.get("has_total_mismatch")
            else ""
        )
        facts.append(
            fact(
                f"Order {o['order_number']}: {o['status']}, payment {o['payment_status']}, "
                f"fulfillment {o['fulfillment_status']}, ship-by {when(o.get('ship_by'), info)}"
                f"{overdue}{mismatch}.",
                key(o),
            )
        )
    return facts


def _position_parts(
    position: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not position:
        return [], [], []
    facts = [
        fact(
            f"{position['ref']['label']}: on hand {position['on_hand']}, reserved "
            f"{position['reserved']}, available {position['available']}, incoming "
            f"{position['incoming']}, pending demand {position['pending_demand']}, health "
            f"{position['health']}.",
            key(position),
        )
    ]
    metrics = [
        metric(
            "Available",
            position["available"],
            "units",
            key(position),
            formula="available = on_hand − reserved (BR-101)",
        )
    ]
    estimates = []
    velocity = position.get("avg_daily_units") or {}
    if velocity.get("value") is not None:
        estimates.append(
            {"text": f"Average daily units sold: {velocity['value']}.", "basis": velocity["basis"]}
        )
    cover = position.get("days_of_cover") or {}
    if cover.get("value") is not None:
        estimates.append({"text": f"Days of cover: {cover['value']}.", "basis": cover["basis"]})
    return facts, metrics, estimates


def exception_answer(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    """Explain an exception (EXPLAIN_EXCEPTION) or summarise its investigation
    (INVESTIGATION_SUMMARY): severity rule, evidence, priority breakdown, next step."""
    found = records(res, "exception")
    if not found:
        detail = "it does not exist in this store" if r.exception_ids or "find" in res else ""
        return answer(
            "I could not identify the exception you mean"
            + (f": {detail}." if detail else ".")
            + " Name it by its reference (as shown in the exception inbox) or ask from the "
            "exception view.",
            limitations=["Exceptions are looked up by reference, id or exact title text."],
        )
    rec = found[0]
    owner = (rec.get("assignee") or {}).get("display_name") or "unassigned"
    criteria = rec.get("severity_criteria") or ""
    summary = (
        f"{rec['reference']} ({clip(rec.get('title', ''), 120)}) is {rec['severity']} with "
        f"priority score {rec['priority_score']} ({rec['priority_band']}). Severity rule: "
        f"{criteria} It is {rec['status']}, {owner}, due {when(rec.get('due_at'), info)}"
        + (", past due." if rec.get("is_past_due") else ".")
    )
    history = first(res, "history")
    position = first(res, "position")
    pos_facts, pos_metrics, estimates = _position_parts(position)
    facts = _evidence_facts(rec, info) + pos_facts + _history_facts(history, rec, info)
    facts += _order_facts(records(res, "orders"), info)
    for move in (first(res, "movements") or {}).get("movements", [])[:2]:
        facts.append(
            fact(
                f"Ledger: {move['movement_type']} {move['on_hand_delta']:+d} on hand on "
                f"{when(move['occurred_at'], info)} ({move['source']}).",
                key(records(res, "movements")[0]),
            )
        )
    breakdown = rec.get("priority_breakdown") or {}
    exc = key(rec)
    metrics = [
        metric(
            "Priority score",
            rec["priority_score"],
            "points",
            exc,
            formula="S + A + E + D + T, capped at 100 (PRIORITY_MODEL)",
        )
    ]
    for letter, label in (
        ("S", "Severity points (S)"),
        ("A", "Affected-order points (A)"),
        ("E", "Value-at-risk points (E)"),
        ("D", "Deadline points (D)"),
        ("T", "Time-open points (T)"),
    ):
        if breakdown.get(letter) is not None:
            metrics.append(metric(label, breakdown[letter], "points", exc))
    has_exposure = rec.get("exposure_amount") not in (None, "0", "0.00")
    if has_exposure:
        metrics.append(
            metric(
                "Value at risk (exposure)",
                rec["exposure_amount"],
                info.currency,
                exc,
                formula="gross order-line value at risk (BR-404)",
            )
        )
    metrics += pos_metrics
    for item in rec.get("evidence") or []:
        if item.get("unit") == "hours" and item.get("value") not in (None, ""):
            metrics.append(metric(str(item.get("label")), item["value"], "hours", exc))
            break
    recs = [
        recommend(
            str(rec.get("recommended_action") or "Review the evidence in the exception view."),
            f"Rule-authored recommended action for {rec.get('rule_id')}.",
        )
    ]
    if owner == "unassigned" and rec["status"] in ("OPEN", "ACKNOWLEDGED", "REOPENED"):
        recs.append(
            recommend(
                "Assign an owner in the exception view.",
                "The exception has no assignee, so nobody is working on it.",
            )
        )
    if rec.get("is_past_due"):
        recs.append(
            recommend(
                "Treat it as overdue work.",
                f"Its due time ({when(rec.get('due_at'), info)}) has passed.",
            )
        )
    limitations = [PRIORITY_CAVEAT]
    if has_exposure:
        limitations.append(EXPOSURE_CAVEAT)
    if estimates:
        limitations.append(ESTIMATE_CAVEAT)
    if rec.get("suspicious_text") or (history or {}).get("suspicious_text"):
        limitations.append(
            "A record contains unusual text that looks like an instruction; it was treated as "
            "data only."
        )
    return answer(
        summary,
        facts=facts,
        metrics=metrics,
        estimates=estimates,
        recommendations=recs,
        limitations=limitations,
    )


def team_priorities(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    active = records(res, "active")
    board = first(res, "summary") or {}
    count = board.get("active_exceptions", {}).get("total", total(res, "active"))
    soon = info.as_of + timedelta(hours=24)

    def deadline_soon(rec: dict[str, Any]) -> bool:
        deadline = rec.get("deadline_at")
        return bool(deadline) and info.as_of <= datetime.fromisoformat(str(deadline)) <= soon

    buckets: list[tuple[str, list[dict[str, Any]]]] = []
    seen: set[str] = set()
    for name, test in (
        ("P1 without an owner", lambda e: e["priority_band"] == "P1" and not e.get("assignee")),
        ("past their due time", lambda e: bool(e.get("is_past_due"))),
        ("with a business deadline within a day", deadline_soon),
        ("remaining by priority score", lambda e: True),
    ):
        group = [e for e in active if key(e) not in seen and test(e)]
        seen.update(key(e) for e in group)
        buckets.append((name, group))
    ordered = [e for _, group in buckets for e in group]
    summary = (
        f"Suggested order of work for the {count} active exceptions: first P1 exceptions without "
        "an owner, then those past their due time, then those with a business deadline within a "
        "day, then the rest by priority score."
        if active
        else "There are no active exceptions to prioritise."
    )
    recs = [
        recommend(f"Next: the exceptions {name}: {refs_list(group)}.", "Order-of-work heuristic.")
        for name, group in buckets[:3]
        if group
    ]
    return answer(
        summary,
        facts=[fact(exception_line(rec, info), key(rec)) for rec in ordered[:12]],
        metrics=[
            metric(
                "Active exceptions",
                count,
                "exceptions",
                key(board) if board else result_key(res, "active"),
            )
        ],
        recommendations=recs,
        limitations=[
            "This order of work is an MVP heuristic (P1 without owner, past due, deadline within "
            "24 hours, then score). The copilot does not assign anyone.",
            PRIORITY_CAVEAT,
        ],
    )


def product_lookup(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    matched: list[dict[str, Any]] = []
    for index, _ in enumerate(product_candidates(r)):
        matched = records(res, f"product{index}")
        if matched:
            break
    if not matched:
        return answer(
            "No product in this store matches that SKU or name.",
            limitations=["SKUs are matched exactly and names by substring, in this store only."],
        )
    if len(matched) > 1:
        return answer(
            "Several products match your search; ask again with the exact SKU for stock details.",
            facts=[
                fact(f"{p['ref']['label']}: {p['status']}, available {p['available']}.", key(p))
                for p in matched
            ],
        )
    product = matched[0]
    position = first(res, "position")
    pos_facts, pos_metrics, estimates = _position_parts(position)
    supplier = product.get("supplier") or {}
    summary = f"{product['ref']['label']} is {product['status']}."
    metrics = list(pos_metrics)
    if position:
        summary += (
            f" Health {position['health']}: {position['available']} available "
            f"({position['on_hand']} on hand, {position['reserved']} reserved) and "
            f"{position['incoming']} incoming."
        )
        metrics += [
            metric("On hand", position["on_hand"], "units", key(position)),
            metric("Reserved", position["reserved"], "units", key(position)),
            metric(
                "Incoming",
                position["incoming"],
                "units",
                key(position),
                formula="not counted in available (BR-103)",
            ),
            metric("Pending demand", position["pending_demand"], "units", key(position)),
        ]
    facts = list(pos_facts)
    if supplier:
        lead = supplier.get("lead_time_days")
        facts.append(
            fact(
                f"Supplier {supplier.get('name')}"
                + (f", lead time {lead} days." if lead is not None else "."),
                key(product),
            )
        )
    facts += [
        fact(
            f"Active exception {e['ref']['label']} ({e['severity']}, {e['priority_band']}).",
            key(product),
            key(e),
        )
        for e in product.get("active_exceptions") or []
    ][:4]
    movements = records(res, "movements")
    for move in (movements[0].get("movements", []) if movements else [])[:3]:
        facts.append(
            fact(
                f"Ledger: {move['movement_type']} {move['on_hand_delta']:+d} on hand on "
                f"{when(move['occurred_at'], info)} ({move['source']}).",
                key(movements[0]),
            )
        )
    return answer(
        summary,
        facts=facts,
        metrics=metrics,
        estimates=estimates,
        limitations=[ESTIMATE_CAVEAT] if estimates else [],
    )


def order_lookup(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    orders = records(res, "orders")
    missing = (res.get("orders") or {}).get("not_found") or []
    if not orders:
        text = (
            "No order with that number exists in this store."
            if r.identifiers
            else "Name the order number exactly as it appears in the orders list."
        )
        return answer(text, limitations=["Order numbers are matched exactly, in this store only."])
    first = orders[0]
    overdue = (
        f", {first['hours_overdue']} hours past its ship-by" if first.get("is_overdue") else ""
    )
    summary = (
        f"Order {first['order_number']} is {first['status']} (payment {first['payment_status']}, "
        f"fulfillment {first['fulfillment_status']}){overdue}."
    )
    facts, metrics = [], []
    for o in orders[:3]:
        facts.append(
            fact(
                f"Order {o['order_number']}: placed {when(o.get('placed_at'), info)}, paid "
                f"{when(o.get('paid_at'), info)}, ship-by {when(o.get('ship_by'), info)} "
                f"({o.get('ship_by_source') or 'no source'}), shipped "
                f"{when(o.get('shipped_at'), info)}.",
                key(o),
            )
        )
        for line in (o.get("lines") or [])[:4]:
            facts.append(
                fact(
                    f"Order {o['order_number']} line {line['line_number']}: {line['sku']} × "
                    f"{line['quantity']} at {line['unit_price']} {o['currency']}.",
                    key(o),
                )
            )
        for e in o.get("active_exceptions") or []:
            facts.append(fact(f"Active exception {e['ref']['label']}.", key(o), key(e)))
        metrics.append(
            metric(f"Order total {o['order_number']}", o["total"], o["currency"], key(o))
        )
    limitations = []
    if missing:
        limitations.append("Not found in this store: " + ", ".join(missing) + ".")
    return answer(summary, facts=facts, metrics=metrics, limitations=limitations)


def import_issues(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    imports = records(res, "imports")
    if not imports:
        return answer("No imports have been recorded for this store yet.")
    latest = imports[0]
    summ = latest.get("summary", {})
    summary = (
        f"The latest import is {latest['ref']['label']} with status {latest['status']}: "
        f"{summ.get('rows_with_errors', 0)} rows with errors and "
        f"{summ.get('rows_with_warnings', 0)} with warnings."
    )
    facts = []
    for item in imports[:5]:
        codes = ", ".join(
            f"{c['code']} ({c['count']})" for c in (item.get("code_counts") or [])[:3]
        )
        facts.append(
            fact(
                f"{item['ref']['label']}: {item['status']}, created "
                f"{when(item.get('created_at'), info)}"
                + (f"; issue codes {codes}" if codes else "")
                + ".",
                key(item),
            )
        )
    issues_rec = first(res, "issues")
    for issue in (issues_rec or {}).get("issues", [])[:6]:
        facts.append(
            fact(
                f"Row {issue.get('row_number')}, column {issue.get('column') or '-'}: "
                f"{issue['code']} ({issue['severity']}): {issue['message']}.",
                key(issues_rec) if issues_rec else None,
            )
        )
    return answer(
        summary,
        facts=facts,
        metrics=[
            metric(
                "Rows with errors (latest import)",
                summ.get("rows_with_errors", 0),
                "rows",
                key(latest),
            )
        ],
        recommendations=[
            recommend(
                "Fix the listed rows in the source file, download the issue report from the import "
                "page if needed, and upload the corrected file.",
                "Rows with errors are not applied.",
            )
        ]
        if summ.get("rows_with_errors")
        else [],
        limitations=["Only the 10 most recent imports are considered."],
    )


_TREND_LABELS = (
    ("orders_placed", "Orders placed", "orders"),
    ("units", "Units sold", "units"),
    ("gmv", "Gross merchandise value", None),
    ("exceptions_detected", "Exceptions detected", "exceptions"),
    ("exceptions_resolved", "Exceptions resolved", "exceptions"),
    ("shipped_on_time", "Shipped on time", "orders"),
    ("shipped_late", "Shipped late", "orders"),
)


def trends(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    rec = first(res, "trends")
    if not rec or not rec.get("days"):
        return answer("No trend data is available for this store.")
    days, series, totals = rec["days"], rec.get("series", {}), rec.get("totals", {})
    summary = (
        f"From {days[0]} to {days[-1]} (today so far), {totals.get('orders_placed')} orders were "
        f"placed and {totals.get('units')} units sold; {totals.get('exceptions_detected')} "
        f"exceptions were detected and {totals.get('exceptions_resolved')} resolved."
    )
    agg = key(rec)
    facts = []
    for name, label, _ in _TREND_LABELS[:4]:
        values = series.get(name) or []
        if len(values) >= 2:
            facts.append(
                fact(
                    f"{label}: {values[0]} on {days[0]}, {values[-1]} on {days[-1]} (partial day).",
                    agg,
                )
            )
    metrics = [
        metric(f"{label} (total)", totals[name], unit or info.currency, agg)
        for name, label, unit in _TREND_LABELS
        if name in totals
    ]
    return answer(
        summary,
        facts=facts,
        metrics=metrics,
        limitations=[
            "Counts only: no projection, and the copilot does not infer causes from these counts.",
            "The last day is partial (today so far), in the store time zone.",
        ],
    )


_WRITE_SCREENS = {
    "resolve": "open the exception and use Resolve (the assignee, or a person with "
    "exceptions.manage)",
    "assign": "open the exception and use Assign (needs exceptions.assign)",
    "reassign": "open the exception and use Assign (needs exceptions.assign)",
    "unassign": "open the exception and use Assign to clear the assignee (needs exceptions.assign)",
    "dismiss": "open the exception and use Dismiss (needs exceptions.manage)",
    "close": "open the exception and use Resolve or Dismiss",
    "acknowledge": "open the exception and use Acknowledge (needs exceptions.work)",
    "ack": "open the exception and use Acknowledge (needs exceptions.work)",
    "reopen": "open the closed exception and use Reopen (needs exceptions.manage)",
    "import": "go to Imports, upload the CSV, review the preview and Apply (needs imports.run)",
    "upload": "go to Imports, upload the CSV, review the preview and Apply (needs imports.run)",
    "apply": "go to Imports, open the validated import and Apply it (needs imports.run)",
    "add a note": "open the exception and add the note there, or use Draft note (needs "
    "exceptions.work)",
}


def unsupported(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    reason = r.unsupported or Unsupported.OUT_OF_SCOPE
    help_rec = recommend(
        "Ask, for example: What needs attention today?",
        f"Supported questions: {SUPPORTED_QUESTIONS}.",
    )
    if reason is Unsupported.WRITE_REQUEST:
        screen = _WRITE_SCREENS.get(
            r.action or "", "use the matching action on the exception, order or import page"
        )
        return answer(
            "I cannot change data: the copilot only reads this store's data and never resolves, "
            "assigns, dismisses, imports or edits anything. A person with the right permission "
            "does this in the product.",
            recommendations=[
                recommend(
                    f"To do this yourself, {screen}.",
                    "Every change needs a person's action, permission check and audit entry.",
                )
            ],
            limitations=["The copilot has no write access."],
        )
    texts = {
        Unsupported.PERSONAL_DATA: "The product stores no customer personal data (no names, email "
        "addresses, postal addresses or phone numbers), so I cannot provide it.",
        Unsupported.OTHER_STORE: "I can only read data of the store you are working in. To see "
        "another store, switch store in the app if your account has access to it.",
        Unsupported.FORECAST: "I cannot forecast sales or demand: the product has no forecasting "
        "model. The only forward-looking values are the labelled estimates of sales velocity and "
        "days of cover on a product's stock position.",
        Unsupported.OUT_OF_SCOPE: "I can only help with this store's operations data.",
    }
    return answer(
        texts.get(reason, texts[Unsupported.OUT_OF_SCOPE]),
        recommendations=[help_rec],
        limitations=["This question is outside what the copilot can answer."],
    )


def help_answer(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    return answer(
        f"I can answer questions about this store's operations: {SUPPORTED_QUESTIONS}.",
        recommendations=[
            recommend(
                "Ask, for example: What needs attention today?",
                "It is one of the supported questions.",
            )
        ],
        limitations=[
            "The rule-based assistant recognises the supported questions in English phrasings only."
        ],
    )


TEMPLATES: dict[Intent, Callable[[RoutedIntent, Results, TemplateInfo], dict[str, Any]]] = {
    Intent.ATTENTION_TODAY: attention_today,
    Intent.TOP_PRIORITY_EXCEPTIONS: top_priority,
    Intent.OVERDUE_ORDERS: overdue_orders,
    Intent.OVERSELL_RISK_SKUS: oversell_risk,
    Intent.CHANGES_SINCE_YESTERDAY: changes_since_yesterday,
    Intent.EXPLAIN_EXCEPTION: exception_answer,
    Intent.TEAM_PRIORITIES: team_priorities,
    Intent.INVESTIGATION_SUMMARY: exception_answer,
    Intent.PRODUCT_LOOKUP: product_lookup,
    Intent.ORDER_LOOKUP: order_lookup,
    Intent.IMPORT_ISSUES: import_issues,
    Intent.TRENDS: trends,
    Intent.HELP: help_answer,
    Intent.UNSUPPORTED: unsupported,
}


def render(r: RoutedIntent, res: Results, info: TemplateInfo) -> dict[str, Any]:
    return TEMPLATES[r.intent](r, res, info)


def render_note(
    r: RoutedIntent, res: Results, info: TemplateInfo, user_hint: str | None
) -> dict[str, Any]:
    """Template ``note_draft@1``: current state, key evidence, owner, next step, optional hint."""
    found = records(res, "exception")
    if not found:
        return {
            "body": "The exception could not be found in this store.",
            "refs": [],
            "limitations": [],
        }
    rec = found[0]
    owner = (rec.get("assignee") or {}).get("display_name")
    evidence = [
        f"{item.get('label')} {evidence_value(item, info)}"
        for item in rec.get("evidence") or []
        if not item.get("is_estimate") and item.get("value") not in (None, "")
    ][:3]
    parts = [
        f"As of {when(info.as_of, info)}: {rec['reference']} ({clip(rec.get('title', ''), 120)}) "
        f"is {rec['status']}, severity {rec['severity']}, priority {rec['priority_score']} "
        f"({rec['priority_band']}).",
    ]
    if evidence:
        parts.append("Key evidence: " + "; ".join(evidence) + ".")
    parts.append(f"Assigned to {owner}." if owner else "Not assigned yet.")
    history = first(res, "history") or {}
    if history.get("reopen_count"):
        parts.append(f"Reopened {history['reopen_count']} times.")
    notes = history.get("notes") or []
    if notes:
        parts.append(
            f"Latest note by {notes[0].get('author_display_name') or 'a former user'} on "
            f"{when(notes[0].get('created_at'), info)}."
        )
    parts.append(f"Next step: {rec.get('recommended_action')}")
    if user_hint:
        parts.append(f"Reported: {user_hint}")
    refs = [key(rec)] + [
        f"{item['source']['type']}:{item['source']['id']}"
        for item in rec.get("evidence") or []
        if isinstance(item.get("source"), dict)
    ]
    return {
        "body": clip(" ".join(parts), 1500),
        "refs": list(dict.fromkeys(refs)),
        "limitations": [
            "Review and edit the draft before saving; nothing is saved until you accept it."
        ],
    }
