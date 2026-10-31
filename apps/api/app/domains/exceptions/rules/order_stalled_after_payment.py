"""ORDER_STALLED_AFTER_PAYMENT (``ORD-STALLED@1``): paid but not processed in time (BR-203)."""

from datetime import datetime, timedelta

from app.domains.exceptions.models import ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.rules.base import (
    ACTION_MAX,
    TITLE_MAX,
    Finding,
    Rule,
    calculation,
    clip,
    evidence,
    fact,
    format_local,
    hours,
    money,
)
from app.domains.exceptions.rules.order_common import (
    effective_ship_by,
    line_products,
    order_ref,
    order_src,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, OrderFacts, RuleSettings
from app.domains.orders.models import OrderStatus

RULE_ID = "ORD-STALLED@1"
EXCEPTION_TYPE = ExceptionType.ORDER_STALLED_AFTER_PAYMENT
CATEGORY = ExceptionCategory.FULFILLMENT
HIGH_WHEN_SHIP_BY_WITHIN = timedelta(hours=12)


def is_stalled(order: OrderFacts, settings: RuleSettings, as_of: datetime) -> bool:
    """BR-203: PAID, paid more than stall_threshold_hours ago, and not overdue yet."""
    if order.status is not OrderStatus.PAID or order.paid_at is None:
        return False
    ship_by, _ = effective_ship_by(order, settings)
    overdue = ship_by is not None and as_of > ship_by
    return as_of - order.paid_at > timedelta(hours=settings.stall_threshold_hours) and not overdue


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, order, settings, as_of)
        for order in snapshot.orders_in_order
        if is_stalled(order, settings, as_of)
    ]


def _finding(
    snapshot: EvaluationSnapshot, order: OrderFacts, settings: RuleSettings, as_of: datetime
) -> Finding:
    assert order.paid_at is not None  # guarded by is_stalled
    ship_by, sla_source = effective_ship_by(order, settings)
    since_payment = as_of - order.paid_at
    until_ship_by = (ship_by - as_of) if ship_by is not None else None
    high = until_ship_by is not None and until_ship_by <= HIGH_WHEN_SHIP_BY_WITHIN
    src = order_src(order)
    exposure = money(order.total)
    if ship_by is not None:
        action = (
            f"Move the order into processing before {format_local(ship_by, snapshot.timezone)}."
        )
    else:
        action = "Move the order into processing."
    facts = [
        fact("status", "Order status", order.status, src=src),
        fact("paid_at", "Paid at", order.paid_at, src=src),
        fact(
            "hours_since_payment",
            "Hours since payment",
            hours(since_payment),
            src=None,
            unit="hours",
            volatile=True,
        ),
        fact(
            "stall_threshold_hours",
            "Stall threshold",
            settings.stall_threshold_hours,
            src=None,
            unit="hours",
        ),
        fact("ship_by", "Ship-by deadline", ship_by, src=src),
        fact("sla_source", "Ship-by source", sla_source, src=src),
        fact(
            "hours_until_ship_by",
            "Hours until ship-by",
            hours(until_ship_by) if until_ship_by is not None else None,
            src=None,
            unit="hours",
            volatile=True,
        ),
        fact("order_total", "Order total", exposure, src=src, unit=order.currency),
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=order_ref(order),
        severity=Severity.HIGH if high else Severity.MEDIUM,
        title=clip(
            f"Order {order.order_number} has not moved into processing since payment", TITLE_MAX
        ),
        evidence=evidence(facts),
        calculation=calculation(
            formulas=[
                "stalled when status = PAID, as_of − paid_at > stall_threshold_hours "
                "and as_of ≤ ship_by (BR-203)",
                "severity = HIGH if ship_by − as_of ≤ 12 h else MEDIUM",
                "exposure = order total",
            ],
            inputs={
                "paid_at": order.paid_at,
                "ship_by": ship_by,
                "as_of": as_of,
                "stall_threshold_hours": settings.stall_threshold_hours,
            },
            outputs={
                "hours_since_payment": hours(since_payment),
                "hours_until_ship_by": hours(until_ship_by) if until_ship_by is not None else None,
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
