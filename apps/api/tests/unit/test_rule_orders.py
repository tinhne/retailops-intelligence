"""Order rules (EXCEPTION_CATALOG.md: ORD-OVERDUE@1, ORD-STALLED@1, PAY-REFUND-PENDING@1)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domains.exceptions.models import ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.rules import (
    order_fulfillment_overdue,
    order_refund_pending,
    order_stalled_after_payment,
)
from app.domains.exceptions.rules.base import Finding, material_view
from app.domains.exceptions.snapshot import RuleSettings
from app.domains.orders.models import OrderStatus, PaymentStatus, ShipBySource
from tests.factories_exceptions import (
    SETTINGS,
    T0,
    facts_line,
    facts_order,
    facts_product,
    snapshot,
)

SHIP_BY = T0 + timedelta(hours=48)


def _overdue(as_of_offset: timedelta, status: OrderStatus = OrderStatus.PAID) -> list[Finding]:
    order = facts_order("KHK-1001", status=status, paid_at=T0, ship_by=SHIP_BY)
    snap = snapshot(orders_=[order])
    return list(order_fulfillment_overdue.evaluate(snap, SETTINGS, SHIP_BY + as_of_offset))


# --- ORD-OVERDUE@1 -----------------------------------------------------------------------------


def test_exactly_at_ship_by_is_not_overdue() -> None:
    """BR-202: the comparison is strict."""
    assert _overdue(timedelta(0)) == []
    assert len(_overdue(timedelta(seconds=1))) == 1


@pytest.mark.parametrize(
    ("overdue_by", "severity"),
    [
        (timedelta(seconds=1), Severity.MEDIUM),
        (timedelta(hours=24), Severity.MEDIUM),
        (timedelta(hours=24, seconds=1), Severity.HIGH),
        (timedelta(hours=72), Severity.HIGH),
        (timedelta(hours=72, seconds=1), Severity.CRITICAL),
    ],
)
def test_overdue_severity_thresholds_at_24h_and_72h(
    overdue_by: timedelta, severity: Severity
) -> None:
    (finding,) = _overdue(overdue_by)
    assert finding.severity is severity


@pytest.mark.parametrize(
    ("status", "action"),
    [
        (OrderStatus.PAID, "Start picking: the order has not entered processing."),
        (OrderStatus.PROCESSING, "Check the picking/packing queue for blockers."),
        (OrderStatus.READY_TO_SHIP, "Hand over to the carrier and record tracking."),
    ],
)
def test_overdue_recommended_action_depends_on_status(status: OrderStatus, action: str) -> None:
    (finding,) = _overdue(timedelta(hours=2), status)
    assert finding.recommended_action == action


@pytest.mark.parametrize(
    "status", [OrderStatus.SHIPPED, OrderStatus.CANCELLED, OrderStatus.CREATED]
)
def test_orders_outside_committed_statuses_are_never_overdue(status: OrderStatus) -> None:
    order = facts_order("KHK-1001", status=status, paid_at=T0, ship_by=SHIP_BY)
    snap = snapshot(orders_=[order])
    assert order_fulfillment_overdue.evaluate(snap, SETTINGS, SHIP_BY + timedelta(days=5)) == []


def test_overdue_finding_structure_exposure_and_volatile_hours() -> None:
    order = facts_order("KHK-1001", total="120.00", ship_by=SHIP_BY)
    snap = snapshot(orders_=[order])

    first = order_fulfillment_overdue.evaluate(snap, SETTINGS, SHIP_BY + timedelta(hours=30))[0]
    later = order_fulfillment_overdue.evaluate(snap, SETTINGS, SHIP_BY + timedelta(hours=31))[0]

    assert first.rule_id == "ORD-OVERDUE@1"
    assert first.category is ExceptionCategory.FULFILLMENT
    assert first.dedup_key == f"ORDER_FULFILLMENT_OVERDUE:order:{order.id}"
    assert first.exposure_amount == Decimal("120.00")
    assert first.deadline_at == SHIP_BY
    assert first.affected_order_ids == (order.id,)
    hours = next(f for f in first.evidence["facts"] if f["key"] == "hours_overdue")
    assert hours["value"] == "30.0"
    assert hours["volatile"] is True
    # "hours overdue" moves every run but is not a material evidence change.
    assert material_view(first.evidence) == material_view(later.evidence)
    assert first.title == later.title == "Order KHK-1001 is past its ship-by deadline"


def test_overdue_uses_paid_at_plus_sla_when_ship_by_is_missing() -> None:
    """BR-201 fallback: paid_at + fulfillment_sla_hours."""
    order = facts_order("KHK-1001", paid_at=T0, ship_by=None, ship_by_source=None)
    order = order.__class__(**{**order.__dict__, "ship_by": None})
    settings = RuleSettings(fulfillment_sla_hours=24)
    snap = snapshot(orders_=[order])

    assert order_fulfillment_overdue.evaluate(snap, settings, T0 + timedelta(hours=24)) == []
    (finding,) = order_fulfillment_overdue.evaluate(snap, settings, T0 + timedelta(hours=25))
    sla = next(f for f in finding.evidence["facts"] if f["key"] == "sla_source")
    assert sla["value"] == ShipBySource.STORE_SLA.value


def test_overdue_order_blocked_by_shortage_links_the_inventory_condition() -> None:
    """Only orders left uncovered by the FIFO allocation (BR-402) are blocked by the shortage."""
    p = facts_product("SKU-A", on_hand=1, reserved=2)
    first_paid = facts_line(p, "KHK-1001", 1, paid_at=T0 - timedelta(hours=2))
    second_paid = facts_line(p, "KHK-1002", 1, paid_at=T0 - timedelta(hours=1))
    orders_ = [
        facts_order("KHK-1001", paid_at=T0 - timedelta(hours=2), ship_by=SHIP_BY),
        facts_order("KHK-1002", paid_at=T0 - timedelta(hours=1), ship_by=SHIP_BY),
    ]
    snap = snapshot(products=[p], committed=[first_paid, second_paid], orders_=orders_)

    covered, blocked = order_fulfillment_overdue.evaluate(
        snap, SETTINGS, SHIP_BY + timedelta(hours=1)
    )

    assert covered.recommended_action.startswith("Start picking")
    assert blocked.recommended_action == (
        "Stock shortage blocks this order. See the linked inventory exception."
    )
    condition = blocked.evidence["records"]["inventory_conditions"][0]
    assert condition["exception_type"] == "INVENTORY_OVERSOLD"
    assert condition["dedup_key"] == f"INVENTORY_OVERSOLD:product:{p.id}"
    assert condition["blocks_this_order"] is True
    assert [e.label for e in blocked.related_entities] == ["SKU-A"]


# --- ORD-STALLED@1 -----------------------------------------------------------------------------


def _stalled(as_of: timedelta, *, ship_by: timedelta = timedelta(hours=48)) -> list[Finding]:
    order = facts_order("KHK-1001", paid_at=T0, ship_by=T0 + ship_by)
    return list(
        order_stalled_after_payment.evaluate(snapshot(orders_=[order]), SETTINGS, T0 + as_of)
    )


def test_stalled_threshold_is_strict() -> None:
    """BR-203: as_of − paid_at > stall_threshold_hours (12)."""
    assert _stalled(timedelta(hours=12)) == []
    assert len(_stalled(timedelta(hours=12, seconds=1))) == 1


@pytest.mark.parametrize(
    ("as_of", "severity"),
    [
        (timedelta(hours=13), Severity.MEDIUM),  # ship_by in 35 h
        (timedelta(hours=36), Severity.HIGH),  # ship_by in exactly 12 h
        (timedelta(hours=48), Severity.HIGH),  # at ship_by: still stalled, not overdue
    ],
)
def test_stalled_severity_high_within_12h_of_ship_by(as_of: timedelta, severity: Severity) -> None:
    (finding,) = _stalled(as_of)
    assert finding.severity is severity


def test_overdue_supersedes_stalled_for_the_same_order() -> None:
    """BR-203: once overdue the order is no longer stalled; ORD-OVERDUE@1 takes over."""
    order = facts_order("KHK-1001", paid_at=T0, ship_by=T0 + timedelta(hours=20))
    snap = snapshot(orders_=[order])
    as_of = T0 + timedelta(hours=21)

    assert order_stalled_after_payment.evaluate(snap, SETTINGS, as_of) == []
    assert len(order_fulfillment_overdue.evaluate(snap, SETTINGS, as_of)) == 1


def test_stalled_applies_only_to_paid_orders_and_names_the_deadline_in_store_time() -> None:
    processing = facts_order("KHK-1002", status=OrderStatus.PROCESSING, paid_at=T0)
    paid = facts_order("KHK-1001", paid_at=T0, ship_by=T0 + timedelta(hours=48))
    snap = snapshot(orders_=[processing, paid])

    findings = order_stalled_after_payment.evaluate(snap, SETTINGS, T0 + timedelta(hours=13))

    assert [f.primary_entity.label for f in findings] == ["KHK-1001"]
    finding = findings[0]
    assert finding.exception_type is ExceptionType.ORDER_STALLED_AFTER_PAYMENT
    assert finding.deadline_at == T0 + timedelta(hours=48)
    # 2026-11-04 12:00 UTC is 07:00 EST in the store time zone (BR-501).
    assert (
        finding.recommended_action == "Move the order into processing before 2026-11-04 07:00 EST."
    )


# --- PAY-REFUND-PENDING@1 ----------------------------------------------------------------------


def _refund(elapsed: timedelta, payment: PaymentStatus = PaymentStatus.PAID) -> list[Finding]:
    order = facts_order(
        "KHK-1001",
        status=OrderStatus.CANCELLED,
        payment_status=payment,
        total="89.90",
        paid_at=T0 - timedelta(hours=2),
        cancelled_at=T0,
    )
    return list(order_refund_pending.evaluate(snapshot(orders_=[order]), SETTINGS, T0 + elapsed))


@pytest.mark.parametrize(
    ("elapsed", "severity"),
    [
        (timedelta(hours=24), None),  # exactly 1 × refund_overdue_hours: not yet
        (timedelta(hours=24, seconds=1), Severity.HIGH),
        (timedelta(hours=72), Severity.HIGH),  # exactly 3 ×: still HIGH
        (timedelta(hours=72, seconds=1), Severity.CRITICAL),
    ],
)
def test_refund_pending_thresholds_at_1x_and_3x(
    elapsed: timedelta, severity: Severity | None
) -> None:
    """BR-206: both clocks start at cancelled_at."""
    findings = _refund(elapsed)
    if severity is None:
        assert findings == []
    else:
        (finding,) = findings
        assert finding.severity is severity


def test_refund_pending_exposure_deadline_and_action() -> None:
    (finding,) = _refund(timedelta(hours=26))
    assert finding.exposure_amount == Decimal("89.90")
    assert finding.deadline_at == T0 + timedelta(hours=24)
    assert finding.category is ExceptionCategory.PAYMENT
    assert finding.recommended_action.startswith("Issue the refund in the payment system.")


def test_refunded_or_unpaid_cancellations_have_no_refund_pending() -> None:
    assert _refund(timedelta(days=5), PaymentStatus.PENDING) == []
    refunded = facts_order(
        "KHK-1001",
        status=OrderStatus.REFUNDED,
        payment_status=PaymentStatus.REFUNDED,
        cancelled_at=T0,
    )
    snap = snapshot(orders_=[refunded])
    assert order_refund_pending.evaluate(snap, SETTINGS, T0 + timedelta(days=5)) == []
