"""ORDER_FULFILLMENT_OVERDUE (``ORD-OVERDUE@1``): a committed order past its ship-by (BR-202)."""

from datetime import datetime, timedelta
from typing import Any

from app.domains.exceptions.models import EntityType, ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.rules.base import (
    ACTION_MAX,
    TITLE_MAX,
    Finding,
    Rule,
    calculation,
    clip,
    dedup_key,
    evidence,
    fact,
    hours,
    money,
    source,
)
from app.domains.exceptions.rules.inventory_common import allocate_fifo, inventory_condition
from app.domains.exceptions.rules.order_common import (
    effective_ship_by,
    line_products,
    order_ref,
    order_src,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, OrderFacts, RuleSettings
from app.domains.orders.models import OrderStatus
from app.domains.orders.state import COMMITTED_STATUSES

RULE_ID = "ORD-OVERDUE@1"
EXCEPTION_TYPE = ExceptionType.ORDER_FULFILLMENT_OVERDUE
CATEGORY = ExceptionCategory.FULFILLMENT

STATUS_ACTIONS: dict[OrderStatus, str] = {
    OrderStatus.PAID: "Start picking: the order has not entered processing.",
    OrderStatus.PROCESSING: "Check the picking/packing queue for blockers.",
    OrderStatus.READY_TO_SHIP: "Hand over to the carrier and record tracking.",
}
SHORTAGE_ACTION = "Stock shortage blocks this order. See the linked inventory exception."


def severity_for(overdue: timedelta) -> Severity:
    """≤ 24 h → MEDIUM; > 24 h and ≤ 72 h → HIGH; > 72 h → CRITICAL (calendar hours, BR-204)."""
    if overdue <= timedelta(hours=24):
        return Severity.MEDIUM
    if overdue <= timedelta(hours=72):
        return Severity.HIGH
    return Severity.CRITICAL


def is_overdue(order: OrderFacts, settings: RuleSettings, as_of: datetime) -> bool:
    """BR-202: committed status and as_of strictly after ship_by."""
    ship_by, _ = effective_ship_by(order, settings)
    return order.status in COMMITTED_STATUSES and ship_by is not None and as_of > ship_by


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, order, settings, as_of)
        for order in snapshot.orders_in_order
        if is_overdue(order, settings, as_of)
    ]


def _inventory_context(snapshot: EvaluationSnapshot, order: OrderFacts) -> list[dict[str, Any]]:
    """Inventory conditions on the order's line products, and whether a shortage blocks it.

    An oversold product blocks this order only if FIFO allocation leaves one of the order's lines
    uncovered (BR-402); orders paid earlier are fully covered and are not blocked.
    """
    rows: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for line in snapshot.lines_for_order(order.id):
        if line.product_id in seen:
            continue
        seen.add(line.product_id)
        product = snapshot.products.get(line.product_id)
        if product is None:
            continue
        condition = inventory_condition(product, snapshot.pending_demand(product.id))
        if condition is None:
            continue
        uncovered = 0
        if condition is ExceptionType.INVENTORY_OVERSOLD:
            uncovered = sum(
                a.uncovered
                for a in allocate_fifo(product.on_hand, snapshot.committed_lines_for(product.id))
                if a.line.order_id == order.id
            )
        rows.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "exception_type": condition,
                "dedup_key": dedup_key(condition, EntityType.PRODUCT, product.id),
                "uncovered_quantity": uncovered,
                "blocks_this_order": uncovered > 0,
                "source": source("product", product.id, f"{product.sku} · {product.name}"),
            }
        )
    return rows


def _finding(
    snapshot: EvaluationSnapshot, order: OrderFacts, settings: RuleSettings, as_of: datetime
) -> Finding:
    ship_by, sla_source = effective_ship_by(order, settings)
    assert ship_by is not None  # guarded by is_overdue
    overdue = as_of - ship_by
    severity = severity_for(overdue)
    lines = snapshot.lines_for_order(order.id)
    inventory = _inventory_context(snapshot, order)
    blocked = any(row["blocks_this_order"] for row in inventory)
    action = SHORTAGE_ACTION if blocked else STATUS_ACTIONS[order.status]
    src = order_src(order)
    exposure = money(order.total)
    facts = [
        fact("status", "Order status", order.status, src=src),
        fact("paid_at", "Paid at", order.paid_at, src=src),
        fact("ship_by", "Ship-by deadline", ship_by, src=src),
        fact("sla_source", "Ship-by source", sla_source, src=src),
        fact(
            "hours_overdue",
            "Hours past ship-by",
            hours(overdue),
            src=None,
            unit="hours",
            volatile=True,
        ),
        fact("order_total", "Order total", exposure, src=src, unit=order.currency),
    ]
    line_rows = [
        {
            "order_item_id": line.order_item_id,
            "line_number": line.line_number,
            "product_id": line.product_id,
            "sku": line.sku,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "source": source(
                "order_item", line.order_item_id, f"{order.order_number} line {line.line_number}"
            ),
        }
        for line in lines
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=order_ref(order),
        severity=severity,
        title=clip(f"Order {order.order_number} is past its ship-by deadline", TITLE_MAX),
        evidence=evidence(facts, {"lines": line_rows, "inventory_conditions": inventory}),
        calculation=calculation(
            formulas=[
                "overdue when status ∈ {PAID, PROCESSING, READY_TO_SHIP} "
                "and as_of > ship_by (BR-202)",
                "ship_by = imported ship_by, else paid_at + fulfillment_sla_hours (BR-201)",
                "severity: overdue ≤ 24 h MEDIUM, ≤ 72 h HIGH, > 72 h CRITICAL",
                "exposure = order total",
            ],
            inputs={
                "status": order.status,
                "ship_by": ship_by,
                "as_of": as_of,
                "fulfillment_sla_hours": settings.fulfillment_sla_hours,
            },
            outputs={
                "hours_overdue": hours(overdue),
                "severity": severity,
                "blocked_by_shortage": blocked,
                "exposure_amount": exposure,
            },
        ),
        recommended_action=clip(action, ACTION_MAX),
        detected_at=as_of,
        related_entities=line_products(snapshot, order.id),
        affected_order_ids=(order.id,),
        exposure_amount=exposure,
        deadline_at=ship_by,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
