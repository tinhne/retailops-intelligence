"""Tool plans per intent (AI_ARCHITECTURE.md §7.2) and the investigation ContextBuilder plans
(§7.3).

A plan is a pure function ``(routed, results so far, context) → calls``. It may be staged: a later
stage reads earlier results (for example the product ids of the top oversell-risk exceptions). The
engine executes the calls whose key has no result yet and asks again, until nothing new is
planned. Every call goes through the tool registry like a model's call would.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.domains.ai.providers.deterministic.router import Intent, RoutedIntent
from app.domains.exceptions.models import ExceptionStatus, ExceptionType

Results = dict[str, dict[str, Any]]
ALL_STATUSES = [s.value for s in ExceptionStatus]
MAX_STAGES = 5


@dataclass(frozen=True)
class PlannedCall:
    key: str
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class PlanContext:
    as_of: datetime
    timezone: str


def records(results: Results, key: str) -> list[dict[str, Any]]:
    envelope = results.get(key) or {}
    if envelope.get("status") != "SUCCESS":
        return []
    return list(envelope.get("records") or [])


def start_of_yesterday(ctx: PlanContext) -> datetime:
    zone = ZoneInfo(ctx.timezone)
    day = ctx.as_of.astimezone(zone).date() - timedelta(days=1)
    return datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _attention(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return [
        PlannedCall("summary", "get_dashboard_summary", {}),
        PlannedCall("active", "list_exceptions", {"limit": 10}),
        PlannedCall("overdue", "get_overdue_orders", {"limit": 5}),
    ]


def _top(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    args: dict[str, Any] = {"limit": r.limit or 10}
    if r.severities:
        args["severity"] = [s.value for s in r.severities]
    if r.exception_types:
        args["exception_type"] = [t.value for t in r.exception_types]
    return [PlannedCall("top", "list_exceptions", args)]


def _overdue(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return [PlannedCall("overdue", "get_overdue_orders", {"limit": r.limit or 20})]


def _oversell(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    stage1 = [
        PlannedCall(
            "risk",
            "list_exceptions",
            {"exception_type": [ExceptionType.INVENTORY_OVERSELL_RISK.value], "limit": 20},
        ),
        PlannedCall(
            "oversold",
            "list_exceptions",
            {"exception_type": [ExceptionType.INVENTORY_OVERSOLD.value], "limit": 20},
        ),
    ]
    if "risk" not in res:
        return stage1
    product_ids = [
        rec["primary_entity"]["ref"]["id"]
        for rec in records(res, "risk")
        if rec.get("primary_entity", {}).get("ref", {}).get("type") == "product"
    ][:5]
    return [
        PlannedCall(f"position:{pid}", "get_inventory_position", {"product_id": pid})
        for pid in product_ids
    ]


def _changes(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    since = _iso(start_of_yesterday(ctx))
    return [
        PlannedCall("trends", "get_operational_trends", {"window_days": 2}),
        PlannedCall(
            "new", "list_exceptions", {"status": ALL_STATUSES, "detected_since": since, "limit": 20}
        ),
        PlannedCall(
            "resolved",
            "list_exceptions",
            {"status": [ExceptionStatus.RESOLVED.value], "resolved_since": since, "limit": 20},
        ),
        PlannedCall("imports", "get_import_errors", {"since": since, "limit": 10}),
    ]


def target_exception_id(r: RoutedIntent, res: Results) -> str | None:
    """The exception a question is about: an explicit id, else the best match of the reference or
    quoted title looked up in stage 1."""
    if r.exception_ids:
        return str(r.exception_ids[0])
    found = records(res, "find")
    return str(found[0]["ref"]["id"]) if found else None


def _explain(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    if not r.exception_ids:
        query = (r.exception_refs or r.quoted or ("",))[0][:100]
        if len(query) < 2:
            return []
        if "find" not in res:
            return [
                PlannedCall(
                    "find", "list_exceptions", {"query": query, "status": ALL_STATUSES, "limit": 5}
                )
            ]
    exception_id = target_exception_id(r, res)
    if exception_id is None:
        return []
    calls = [
        PlannedCall("exception", "get_exception", {"exception_id": exception_id}),
        PlannedCall(
            "history", "get_exception_history", {"exception_id": exception_id, "limit": 20}
        ),
    ]
    found = records(res, "exception")
    if found and (
        found[0].get("affected_order_count")
        or found[0].get("primary_entity", {}).get("ref", {}).get("type") == "order"
    ):
        calls.append(
            PlannedCall(
                "orders",
                "get_related_orders",
                {"exception_id": exception_id, "limit": 10, "include_lines": False},
            )
        )
    return calls


def _team(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return [
        PlannedCall("active", "list_exceptions", {"limit": 30}),
        PlannedCall("summary", "get_dashboard_summary", {}),
    ]


# ContextBuilder: extra calls per exception type after get_exception + get_exception_history.
CONTEXT_PLANS: dict[str, tuple[str, ...]] = {
    ExceptionType.INVENTORY_OVERSOLD: ("position", "orders", "movements"),
    ExceptionType.INVENTORY_OVERSELL_RISK: ("position", "orders"),
    ExceptionType.INVENTORY_OUT_OF_STOCK: ("position", "product", "movements"),
    ExceptionType.INVENTORY_BELOW_REORDER_POINT: ("position", "product"),
    ExceptionType.ORDER_FULFILLMENT_OVERDUE: ("orders",),
    ExceptionType.ORDER_STALLED_AFTER_PAYMENT: ("orders",),
    ExceptionType.ORDER_REFUND_PENDING: ("orders",),
    ExceptionType.DATA_ORDER_TOTAL_MISMATCH: ("orders",),
    ExceptionType.DATA_NEGATIVE_ON_HAND: ("position", "movements"),
}


def context_builder(exception_id: str, res: Results) -> list[PlannedCall]:
    """The fixed investigation plan for one exception (summary and note draft share stage 1)."""
    calls = [
        PlannedCall("exception", "get_exception", {"exception_id": exception_id}),
        PlannedCall(
            "history", "get_exception_history", {"exception_id": exception_id, "limit": 20}
        ),
    ]
    found = records(res, "exception")
    if not found:
        return calls
    entity = found[0].get("primary_entity", {}).get("ref", {})
    product_id = entity.get("id") if entity.get("type") == "product" else None
    for part in CONTEXT_PLANS.get(str(found[0].get("exception_type")), ()):
        if part == "orders":
            calls.append(
                PlannedCall(
                    "orders", "get_related_orders", {"exception_id": exception_id, "limit": 10}
                )
            )
        elif product_id is None:
            continue
        elif part == "position":
            calls.append(
                PlannedCall("position", "get_inventory_position", {"product_id": product_id})
            )
        elif part == "product":
            calls.append(PlannedCall("product", "get_product", {"product_id": product_id}))
        elif part == "movements":
            calls.append(
                PlannedCall(
                    "movements",
                    "get_inventory_movements",
                    {"product_id": product_id, "limit": 10},
                )
            )
    return calls


def _investigation(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return context_builder(str(r.exception_ids[0]), res) if r.exception_ids else []


def _note(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    if not r.exception_ids:
        return []
    exception_id = str(r.exception_ids[0])
    return [
        PlannedCall("exception", "get_exception", {"exception_id": exception_id}),
        PlannedCall(
            "history", "get_exception_history", {"exception_id": exception_id, "limit": 10}
        ),
    ]


def product_candidates(r: RoutedIntent) -> list[tuple[str, str]]:
    return [("sku", i) for i in r.identifiers[:3]] + [("search", t) for t in r.search_terms[:2]]


def _product(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    for index, (kind, value) in enumerate(product_candidates(r)):
        key = f"product{index}"
        if key not in res:
            return [PlannedCall(key, "get_product", {kind: value})]
        found = records(res, key)
        if not found:
            continue
        if len(found) > 1:
            return []
        product_id = found[0]["ref"]["id"]
        return [
            PlannedCall("position", "get_inventory_position", {"product_id": product_id}),
            PlannedCall(
                "movements", "get_inventory_movements", {"product_id": product_id, "limit": 10}
            ),
        ]
    return []


def _order(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    numbers = list(r.identifiers[:5])
    if not numbers:
        return []
    return [PlannedCall("orders", "get_related_orders", {"order_numbers": numbers})]


def _imports(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    if "imports" not in res:
        return [PlannedCall("imports", "get_import_errors", {"limit": 25})]
    for item in records(res, "imports"):
        has_errors = item.get("summary", {}).get("rows_with_errors") or any(
            c.get("severity") == "ERROR" for c in item.get("code_counts") or []
        )
        if has_errors:
            return [
                PlannedCall(
                    "issues", "get_import_errors", {"import_id": item["ref"]["id"], "limit": 10}
                )
            ]
    return []


def _trends(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return [PlannedCall("trends", "get_operational_trends", {"window_days": r.window_days or 14})]


def _none(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    return []


PLANS: dict[Intent, Callable[[RoutedIntent, Results, PlanContext], list[PlannedCall]]] = {
    Intent.ATTENTION_TODAY: _attention,
    Intent.TOP_PRIORITY_EXCEPTIONS: _top,
    Intent.OVERDUE_ORDERS: _overdue,
    Intent.OVERSELL_RISK_SKUS: _oversell,
    Intent.CHANGES_SINCE_YESTERDAY: _changes,
    Intent.EXPLAIN_EXCEPTION: _explain,
    Intent.TEAM_PRIORITIES: _team,
    Intent.INVESTIGATION_SUMMARY: _investigation,
    Intent.NOTE_DRAFT: _note,
    Intent.PRODUCT_LOOKUP: _product,
    Intent.ORDER_LOOKUP: _order,
    Intent.IMPORT_ISSUES: _imports,
    Intent.TRENDS: _trends,
    Intent.HELP: _none,
    Intent.UNSUPPORTED: _none,
}


def next_calls(r: RoutedIntent, res: Results, ctx: PlanContext) -> list[PlannedCall]:
    """Calls of the plan that have no result yet (empty when the plan is complete)."""
    return [call for call in PLANS[r.intent](r, res, ctx) if call.key not in res]
