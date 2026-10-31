"""ORDER_REFUND_PENDING (``PAY-REFUND-PENDING@1``): a cancelled order still paid (BR-206)."""

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
    hours,
    money,
)
from app.domains.exceptions.rules.order_common import order_ref, order_src
from app.domains.exceptions.snapshot import EvaluationSnapshot, OrderFacts, RuleSettings
from app.domains.orders.models import OrderStatus, PaymentStatus

RULE_ID = "PAY-REFUND-PENDING@1"
EXCEPTION_TYPE = ExceptionType.ORDER_REFUND_PENDING
CATEGORY = ExceptionCategory.PAYMENT
RECOMMENDED_ACTION = (
    "Issue the refund in the payment system. The next orders import that shows "
    "payment_status = REFUNDED resolves this exception automatically."
)
CRITICAL_MULTIPLIER = 3


def is_refund_overdue(order: OrderFacts, settings: RuleSettings, as_of: datetime) -> bool:
    """BR-206: CANCELLED, payment still PAID, and more than refund_overdue_hours since cancel."""
    return (
        order.status is OrderStatus.CANCELLED
        and order.payment_status is PaymentStatus.PAID
        and order.cancelled_at is not None
        and as_of - order.cancelled_at > timedelta(hours=settings.refund_overdue_hours)
    )


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(order, settings, as_of)
        for order in snapshot.orders_in_order
        if is_refund_overdue(order, settings, as_of)
    ]


def _finding(order: OrderFacts, settings: RuleSettings, as_of: datetime) -> Finding:
    assert order.cancelled_at is not None  # guarded by is_refund_overdue
    window = timedelta(hours=settings.refund_overdue_hours)
    elapsed = as_of - order.cancelled_at
    critical = elapsed > window * CRITICAL_MULTIPLIER
    deadline = order.cancelled_at + window
    src = order_src(order)
    exposure = money(order.total)
    facts = [
        fact("status", "Order status", order.status, src=src),
        fact("payment_status", "Payment status", order.payment_status, src=src),
        fact("cancelled_at", "Cancelled at", order.cancelled_at, src=src),
        fact("refund_due_at", "Refund due by", deadline, src=None),
        fact(
            "hours_since_cancellation",
            "Hours since cancellation",
            hours(elapsed),
            src=None,
            unit="hours",
            volatile=True,
        ),
        fact(
            "refund_overdue_hours",
            "Refund window",
            settings.refund_overdue_hours,
            src=None,
            unit="hours",
        ),
        fact(
            "order_total",
            "Customer money held (order total)",
            exposure,
            src=src,
            unit=order.currency,
        ),
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=order_ref(order),
        severity=Severity.CRITICAL if critical else Severity.HIGH,
        title=clip(f"Refund pending for cancelled order {order.order_number}", TITLE_MAX),
        evidence=evidence(facts),
        calculation=calculation(
            formulas=[
                "refund pending when status = CANCELLED and payment_status = PAID (BR-206)",
                "overdue when as_of − cancelled_at > refund_overdue_hours",
                "severity = CRITICAL when as_of − cancelled_at > 3 × refund_overdue_hours, "
                "else HIGH",
                "deadline = cancelled_at + refund_overdue_hours; exposure = order total",
            ],
            inputs={
                "cancelled_at": order.cancelled_at,
                "as_of": as_of,
                "refund_overdue_hours": settings.refund_overdue_hours,
            },
            outputs={
                "hours_since_cancellation": hours(elapsed),
                "deadline_at": deadline,
                "exposure_amount": exposure,
            },
        ),
        recommended_action=clip(RECOMMENDED_ACTION, ACTION_MAX),
        detected_at=as_of,
        affected_order_ids=(order.id,),
        exposure_amount=exposure,
        deadline_at=deadline,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
