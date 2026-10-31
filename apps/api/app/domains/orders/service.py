"""Order write path used by imports (and later by manual actions).

Callers validate row shape first; this module enforces the lifecycle rules (STATE_MACHINES.md §1)
and records an immutable OrderEvent for every status change. It never commits.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolationError
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
    ShipBySource,
)
from app.domains.orders.state import SHIPPED_FULFILLMENT, path_to, transition_error


class ChangeKind(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True)
class OrderSnapshot:
    """A validated order row from a source system export."""

    order_number: str
    channel: SalesChannel
    customer_ref: str | None
    status: OrderStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    placed_at: datetime
    paid_at: datetime | None
    ship_by: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    carrier: str | None
    tracking_number: str | None


_COPIED_FIELDS = (
    "channel",
    "customer_ref",
    "payment_status",
    "fulfillment_status",
    "placed_at",
    "paid_at",
    "shipped_at",
    "delivered_at",
    "cancelled_at",
    "currency",
    "subtotal",
    "discount_total",
    "shipping_total",
    "tax_total",
    "total",
    "carrier",
    "tracking_number",
)


def find_by_number(db: Session, store_id: uuid.UUID, order_number: str) -> Order | None:
    return db.scalar(
        select(Order).where(Order.store_id == store_id, Order.order_number == order_number)
    )


def compute_ship_by(
    snapshot_ship_by: datetime | None, paid_at: datetime | None, sla_hours: int
) -> tuple[datetime | None, ShipBySource | None]:
    """BR-201: imported ship_by wins; otherwise paid_at + fulfillment SLA."""
    if snapshot_ship_by is not None:
        return snapshot_ship_by, ShipBySource.IMPORTED
    if paid_at is not None:
        return paid_at + timedelta(hours=sla_hours), ShipBySource.STORE_SLA
    return None, None


def check_transition(existing: Order | None, snapshot: OrderSnapshot) -> str | None:
    """Return a human-readable reason if the snapshot cannot be applied to the existing order."""
    if existing is None:
        return None
    return transition_error(existing.status, existing.payment_status, snapshot.status)


def upsert_order(
    db: Session,
    *,
    store_id: uuid.UUID,
    snapshot: OrderSnapshot,
    fulfillment_sla_hours: int,
    source: ChangeSource,
    import_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> tuple[Order, ChangeKind]:
    existing = find_by_number(db, store_id, snapshot.order_number)
    reason = check_transition(existing, snapshot)
    if reason:
        raise BusinessRuleViolationError(reason, code="ORDER_TRANSITION_NOT_ALLOWED")

    ship_by, ship_by_source = compute_ship_by(
        snapshot.ship_by, snapshot.paid_at, fulfillment_sla_hours
    )

    if existing is None:
        order = Order(
            store_id=store_id,
            order_number=snapshot.order_number,
            status=snapshot.status,
            ship_by=ship_by,
            ship_by_source=ship_by_source,
            last_import_id=import_id,
            **{field: getattr(snapshot, field) for field in _COPIED_FIELDS},
        )
        db.add(order)
        db.flush()
        _record_event(db, order, None, [], source, import_id, actor_user_id)
        return order, ChangeKind.CREATED

    order = existing
    previous_status = order.status
    changed = previous_status != snapshot.status
    for field in _COPIED_FIELDS:
        if getattr(order, field) != getattr(snapshot, field):
            setattr(order, field, getattr(snapshot, field))
            changed = True
    if (order.ship_by, order.ship_by_source) != (ship_by, ship_by_source):
        order.ship_by, order.ship_by_source = ship_by, ship_by_source
        changed = True
    if not changed:
        return order, ChangeKind.UNCHANGED

    order.last_import_id = import_id
    if previous_status != snapshot.status:
        path = path_to(previous_status, snapshot.status) or [previous_status, snapshot.status]
        order.status = snapshot.status
        skipped = [s.value for s in path[1:-1]]
        db.flush()
        _record_event(db, order, previous_status, skipped, source, import_id, actor_user_id)
    db.flush()
    return order, ChangeKind.UPDATED


def _record_event(
    db: Session,
    order: Order,
    from_status: OrderStatus | None,
    skipped: list[str],
    source: ChangeSource,
    import_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
) -> None:
    db.add(
        OrderEvent(
            order_id=order.id,
            store_id=order.store_id,
            from_status=from_status,
            to_status=order.status,
            skipped_statuses=skipped,
            payment_status=order.payment_status,
            fulfillment_status=order.fulfillment_status,
            source=source,
            import_id=import_id,
            actor_user_id=actor_user_id,
        )
    )


@dataclass(frozen=True)
class OrderLineSnapshot:
    line_number: int
    product_id: uuid.UUID
    sku: str
    quantity: int
    unit_price: Decimal
    line_discount: Decimal


def line_lock_reason(
    order: Order, existing: OrderItem | None, line: OrderLineSnapshot
) -> str | None:
    """Recorded lines of orders that already shipped are immutable (ORDER_LINE_LOCKED).

    Adding a line that was never recorded is allowed: historical shipped orders arrive via
    orders.csv first and their lines via order_items.csv afterwards.
    """
    if order.fulfillment_status not in SHIPPED_FULFILLMENT or existing is None:
        return None
    if (existing.product_id, existing.quantity, existing.unit_price, existing.line_discount) != (
        line.product_id,
        line.quantity,
        line.unit_price,
        line.line_discount,
    ):
        return "Cannot change a line of an order that has already shipped"
    return None


def upsert_order_item(
    db: Session, *, order: Order, line: OrderLineSnapshot
) -> tuple[OrderItem, ChangeKind]:
    existing = db.scalar(
        select(OrderItem).where(
            OrderItem.order_id == order.id, OrderItem.line_number == line.line_number
        )
    )
    reason = line_lock_reason(order, existing, line)
    if reason:
        raise BusinessRuleViolationError(reason, code="ORDER_LINE_LOCKED")
    if existing is None:
        item = OrderItem(
            order_id=order.id,
            store_id=order.store_id,
            product_id=line.product_id,
            sku=line.sku,
            line_number=line.line_number,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_discount=line.line_discount,
        )
        db.add(item)
        db.flush()
        return item, ChangeKind.CREATED
    values = {
        "product_id": line.product_id,
        "sku": line.sku,
        "quantity": line.quantity,
        "unit_price": line.unit_price,
        "line_discount": line.line_discount,
    }
    changed = False
    for field, value in values.items():
        if getattr(existing, field) != value:
            setattr(existing, field, value)
            changed = True
    db.flush()
    return existing, ChangeKind.UPDATED if changed else ChangeKind.UNCHANGED
