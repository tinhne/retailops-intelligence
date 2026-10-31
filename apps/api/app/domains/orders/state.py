"""Order lifecycle rules (STATE_MACHINES.md §1). Pure functions, no I/O."""

import itertools
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domains.orders.models import FulfillmentStatus, OrderStatus, PaymentStatus

S = OrderStatus
P = PaymentStatus
F = FulfillmentStatus

TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    S.CREATED: frozenset({S.PAYMENT_PENDING, S.CANCELLED}),
    S.PAYMENT_PENDING: frozenset({S.PAID, S.PAYMENT_FAILED, S.CANCELLED}),
    S.PAYMENT_FAILED: frozenset({S.PAYMENT_PENDING, S.CANCELLED}),
    S.PAID: frozenset({S.PROCESSING, S.CANCELLED}),
    S.PROCESSING: frozenset({S.READY_TO_SHIP, S.CANCELLED}),
    S.READY_TO_SHIP: frozenset({S.SHIPPED, S.CANCELLED}),
    S.SHIPPED: frozenset({S.DELIVERED, S.RETURNED}),
    S.DELIVERED: frozenset({S.RETURN_REQUESTED, S.REFUNDED}),
    S.RETURN_REQUESTED: frozenset({S.RETURNED, S.DELIVERED}),
    S.RETURNED: frozenset({S.REFUNDED}),
    S.CANCELLED: frozenset({S.REFUNDED}),
    S.REFUNDED: frozenset(),
}

# Axis compatibility matrix (§1.3): status → (allowed payment, allowed fulfillment).
# The first fulfillment value listed is the default used when an import omits the column.
AXES: dict[OrderStatus, tuple[tuple[PaymentStatus, ...], tuple[FulfillmentStatus, ...]]] = {
    S.CREATED: ((P.PENDING,), (F.UNFULFILLED,)),
    S.PAYMENT_PENDING: ((P.PENDING,), (F.UNFULFILLED,)),
    S.PAYMENT_FAILED: ((P.FAILED,), (F.UNFULFILLED,)),
    S.PAID: ((P.PAID,), (F.UNFULFILLED,)),
    S.PROCESSING: ((P.PAID,), (F.IN_PROGRESS,)),
    S.READY_TO_SHIP: ((P.PAID,), (F.IN_PROGRESS,)),
    S.SHIPPED: ((P.PAID,), (F.SHIPPED,)),
    S.DELIVERED: ((P.PAID,), (F.DELIVERED,)),
    S.RETURN_REQUESTED: ((P.PAID,), (F.DELIVERED,)),
    S.RETURNED: ((P.PAID,), (F.RETURNED,)),
    S.CANCELLED: ((P.PENDING, P.FAILED, P.PAID), (F.UNFULFILLED,)),
    S.REFUNDED: ((P.REFUNDED,), (F.UNFULFILLED, F.DELIVERED, F.RETURNED)),
}

COMMITTED_STATUSES = frozenset({S.PAID, S.PROCESSING, S.READY_TO_SHIP})
PENDING_DEMAND_STATUSES = frozenset({S.CREATED, S.PAYMENT_PENDING})
SHIPPED_FULFILLMENT = frozenset({F.SHIPPED, F.DELIVERED, F.RETURNED})
# Statuses whose orders count as sales for velocity (BR-150).
SALES_EXCLUDED_STATUSES = frozenset({S.CANCELLED, S.PAYMENT_FAILED, S.CREATED, S.PAYMENT_PENDING})


class DemandClass(StrEnum):
    PENDING = "PENDING"  # not reserved (CREATED, PAYMENT_PENDING)
    COMMITTED = "COMMITTED"  # reserved (PAID, PROCESSING, READY_TO_SHIP)
    FULFILLED = "FULFILLED"  # goods left the warehouse; reservation consumed
    NONE = "NONE"  # no demand; any reservation is released


def can_transition(current: OrderStatus, target: OrderStatus) -> bool:
    return target in TRANSITIONS[current]


def path_to(current: OrderStatus, target: OrderStatus) -> list[OrderStatus] | None:
    """Shortest transition path from ``current`` to ``target`` (inclusive), or None if unreachable.

    Used by import synchronisation: an import may move an order to any reachable state and the
    intermediate states are recorded as skipped (§1.2).
    """
    if current == target:
        return [current]
    previous: dict[OrderStatus, OrderStatus] = {}
    queue: deque[OrderStatus] = deque([current])
    seen = {current}
    while queue:
        node = queue.popleft()
        for nxt in sorted(TRANSITIONS[node]):
            if nxt in seen:
                continue
            previous[nxt] = node
            if nxt == target:
                path = [target]
                while path[-1] != current:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            seen.add(nxt)
            queue.append(nxt)
    return None


def default_fulfillment(status: OrderStatus) -> FulfillmentStatus | None:
    """Fulfillment status implied by ``status``; None when it must be given explicitly."""
    return None if status is S.REFUNDED else AXES[status][1][0]


def axis_errors(
    status: OrderStatus, payment: PaymentStatus, fulfillment: FulfillmentStatus
) -> list[str]:
    allowed_payment, allowed_fulfillment = AXES[status]
    errors: list[str] = []
    if payment not in allowed_payment:
        errors.append(
            f"payment_status {payment.value} is not valid with status {status.value} "
            f"(allowed: {', '.join(p.value for p in allowed_payment)})"
        )
    if fulfillment not in allowed_fulfillment:
        errors.append(
            f"fulfillment_status {fulfillment.value} is not valid with status {status.value} "
            f"(allowed: {', '.join(f.value for f in allowed_fulfillment)})"
        )
    return errors


@dataclass(frozen=True)
class OrderTimestamps:
    placed_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None


@dataclass(frozen=True)
class TimestampIssue:
    field: str
    code: str  # ORDER_MISSING_TIMESTAMP | ORDER_TIMESTAMP_SEQUENCE
    message: str


def timestamp_issues(
    status: OrderStatus,
    payment: PaymentStatus,
    fulfillment: FulfillmentStatus,
    ts: OrderTimestamps,
) -> list[TimestampIssue]:
    """Required timestamps and their ordering (§1.4)."""
    issues: list[TimestampIssue] = []

    def require(field: str, value: datetime | None, reason: str) -> None:
        if value is None:
            issues.append(
                TimestampIssue(field, "ORDER_MISSING_TIMESTAMP", f"{field} is required {reason}")
            )

    if payment in (P.PAID, P.REFUNDED):
        require("paid_at", ts.paid_at, f"when payment_status is {payment.value}")
    if fulfillment in SHIPPED_FULFILLMENT:
        require("shipped_at", ts.shipped_at, f"when fulfillment_status is {fulfillment.value}")
    if fulfillment is F.DELIVERED or status is S.RETURN_REQUESTED:
        require("delivered_at", ts.delivered_at, "for delivered orders")
    if status is S.CANCELLED:
        require("cancelled_at", ts.cancelled_at, "when status is CANCELLED")

    sequence = [
        ("placed_at", ts.placed_at),
        ("paid_at", ts.paid_at),
        ("shipped_at", ts.shipped_at),
        ("delivered_at", ts.delivered_at),
    ]
    present = [(name, value) for name, value in sequence if value is not None]
    for (earlier_name, earlier), (later_name, later) in itertools.pairwise(present):
        if later < earlier:
            issues.append(
                TimestampIssue(
                    later_name,
                    "ORDER_TIMESTAMP_SEQUENCE",
                    f"{later_name} must not be earlier than {earlier_name}",
                )
            )
    return issues


def transition_error(
    current: OrderStatus, current_payment: PaymentStatus, target: OrderStatus
) -> str | None:
    """Why an existing order cannot move to ``target`` (None if it can, possibly via skips)."""
    if current == target:
        return None
    if path_to(current, target) is None:
        return f"Order cannot move from {current.value} to {target.value}"
    if current is S.CANCELLED and target is S.REFUNDED and current_payment is not P.PAID:
        return "Only a cancelled order that was paid can be refunded"
    return None


def demand_class(status: OrderStatus, fulfillment: FulfillmentStatus) -> DemandClass:
    """How an order's lines affect stock (§1.5)."""
    if status in PENDING_DEMAND_STATUSES:
        return DemandClass.PENDING
    if status in COMMITTED_STATUSES:
        return DemandClass.COMMITTED
    if fulfillment in SHIPPED_FULFILLMENT:
        return DemandClass.FULFILLED
    return DemandClass.NONE
