"""Read-side order queries: filtered lists and the order detail with its reconciliation.

SELECT only; writes go through ``orders.service``. The overdue predicate (BR-202) and the total
reconciliation (BR-205) are defined here once and reused by the analytics queries.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, not_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams
from app.domains.catalog.models import Product
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    EntityType,
    ExceptionEntityLink,
    ExceptionStatus,
    OperationalException,
)
from app.domains.inventory import queries as inventory_queries
from app.domains.orders.models import (
    FulfillmentStatus,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
)
from app.domains.orders.schemas import (
    LinkedException,
    OrderAmounts,
    OrderDetail,
    OrderEventOut,
    OrderLineOut,
    OrderListItem,
    OrderSort,
    ReservationRef,
)
from app.domains.orders.state import COMMITTED_STATUSES

CENT = Decimal("0.01")
MISMATCH_TOLERANCE = Decimal("0.01")


# ---------------------------------------------------------------------------------------------
# Shared rules
# ---------------------------------------------------------------------------------------------


def is_overdue(status: OrderStatus, ship_by: datetime | None, as_of: datetime) -> bool:
    """BR-202: committed status and ``as_of > ship_by`` (exactly at the deadline is not overdue)."""
    return status in COMMITTED_STATUSES and ship_by is not None and as_of > ship_by


def overdue_condition(as_of: datetime) -> ColumnElement[bool]:
    """SQL twin of ``is_overdue`` for filters and aggregates."""
    return and_(
        Order.status.in_(COMMITTED_STATUSES),
        Order.ship_by.is_not(None),
        Order.ship_by < as_of,
    )


@dataclass(frozen=True)
class TotalReconciliation:
    lines_total: Decimal
    expected_total: Decimal | None
    difference: Decimal | None
    has_mismatch: bool


def reconcile_total(
    lines: Sequence[tuple[int, Decimal, Decimal]],
    *,
    discount_total: Decimal,
    shipping_total: Decimal,
    tax_total: Decimal,
    total: Decimal,
) -> TotalReconciliation:
    """BR-205: ``expected = Σ(qty × unit_price − line_discount) − discount + shipping + tax``.

    ``lines`` holds ``(quantity, unit_price, line_discount)``. A mismatch needs at least one line
    and ``|total − expected| > 0.01``. Without lines there is nothing to reconcile against.
    """
    lines_total = sum((qty * price - disc for qty, price, disc in lines), Decimal("0")).quantize(
        CENT
    )
    if not lines:
        return TotalReconciliation(lines_total, None, None, False)
    expected = (lines_total - discount_total + shipping_total + tax_total).quantize(CENT)
    difference = (total - expected).quantize(CENT)
    return TotalReconciliation(
        lines_total, expected, difference, abs(difference) > MISMATCH_TOLERANCE
    )


def _count(db: Session, stmt: Select[*tuple[Any, ...]]) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)


# ---------------------------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderFilters:
    q: str | None = None
    statuses: Sequence[OrderStatus] | None = None
    payment_status: PaymentStatus | None = None
    fulfillment_status: FulfillmentStatus | None = None
    channel: SalesChannel | None = None
    placed_from: datetime | None = None
    placed_to: datetime | None = None
    overdue: bool | None = None
    product_id: uuid.UUID | None = None


def list_orders(
    db: Session,
    store_id: uuid.UUID,
    *,
    filters: OrderFilters,
    sort: OrderSort,
    paging: PageParams,
    as_of: datetime,
) -> Page[OrderListItem]:
    """Orders matching every given filter. ``placed_to`` is exclusive; ``overdue`` uses BR-202."""
    line_count = (
        select(func.count(OrderItem.id))
        .where(OrderItem.order_id == Order.id, OrderItem.store_id == store_id)
        .correlate(Order)
        .scalar_subquery()
    )
    stmt = select(Order, line_count).where(Order.store_id == store_id)
    if filters.q:
        stmt = stmt.where(
            or_(
                Order.order_number.icontains(filters.q, autoescape=True),
                Order.customer_ref.icontains(filters.q, autoescape=True),
            )
        )
    if filters.statuses:
        stmt = stmt.where(Order.status.in_(list(filters.statuses)))
    if filters.payment_status is not None:
        stmt = stmt.where(Order.payment_status == filters.payment_status)
    if filters.fulfillment_status is not None:
        stmt = stmt.where(Order.fulfillment_status == filters.fulfillment_status)
    if filters.channel is not None:
        stmt = stmt.where(Order.channel == filters.channel)
    if filters.placed_from is not None:
        stmt = stmt.where(Order.placed_at >= filters.placed_from)
    if filters.placed_to is not None:
        stmt = stmt.where(Order.placed_at < filters.placed_to)
    if filters.overdue is not None:
        condition = overdue_condition(as_of)
        stmt = stmt.where(condition if filters.overdue else not_(condition))
    if filters.product_id is not None:
        stmt = stmt.where(
            select(OrderItem.id)
            .where(
                OrderItem.order_id == Order.id,
                OrderItem.store_id == store_id,
                OrderItem.product_id == filters.product_id,
            )
            .correlate(Order)
            .exists()
        )

    total = _count(db, stmt)
    column = {
        "placed_at": Order.placed_at,
        "total": Order.total,
        "ship_by": Order.ship_by,
        "order_number": Order.order_number,
    }[sort.lstrip("-")]
    primary = (column.desc() if sort.startswith("-") else column.asc()).nulls_last()
    rows = db.execute(
        stmt.order_by(primary, Order.order_number, Order.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[OrderListItem](
        items=[
            OrderListItem(
                id=o.id,
                order_number=o.order_number,
                channel=o.channel,
                customer_ref=o.customer_ref,
                status=o.status,
                payment_status=o.payment_status,
                fulfillment_status=o.fulfillment_status,
                placed_at=o.placed_at,
                paid_at=o.paid_at,
                ship_by=o.ship_by,
                ship_by_source=o.ship_by_source,
                shipped_at=o.shipped_at,
                currency=o.currency,
                total=o.total,
                line_count=int(lines),
                is_overdue=is_overdue(o.status, o.ship_by, as_of),
            )
            for o, lines in rows
        ],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


def linked_exceptions(
    db: Session, store_id: uuid.UUID, entity_type: EntityType, entity_id: uuid.UUID
) -> list[LinkedException]:
    """Exceptions linked to an entity in any role. Active first, then most recently detected."""
    rows = db.execute(
        select(OperationalException, ExceptionEntityLink.role)
        .join(ExceptionEntityLink, ExceptionEntityLink.exception_id == OperationalException.id)
        .where(
            OperationalException.store_id == store_id,
            ExceptionEntityLink.store_id == store_id,
            ExceptionEntityLink.entity_type == entity_type,
            ExceptionEntityLink.entity_id == entity_id,
        )
        .order_by(OperationalException.first_detected_at.desc(), OperationalException.id)
    ).all()
    items = [
        LinkedException(
            id=exc.id,
            reference=exc.reference,
            title=exc.title,
            exception_type=exc.exception_type,
            severity=exc.severity,
            status=exc.status,
            priority_band=exc.priority_band,
            link_role=role,
            is_active=exc.status in ACTIVE_STATUSES,
            resolution_code=exc.resolution_code if exc.status is ExceptionStatus.RESOLVED else None,
            verified_at=exc.verified_at if exc.status is ExceptionStatus.RESOLVED else None,
        )
        for exc, role in rows
    ]
    return sorted(items, key=lambda e: not e.is_active)  # stable: keeps recency within groups


def get_order(
    db: Session, store_id: uuid.UUID, order_id: uuid.UUID, *, as_of: datetime
) -> OrderDetail:
    """One order with its three status axes, lines, history and linked exceptions."""
    order = db.scalar(select(Order).where(Order.store_id == store_id, Order.id == order_id))
    if order is None:
        raise NotFoundError("Order not found.")

    line_rows = db.execute(
        select(OrderItem, Product.sku, Product.name)
        .join(Product, Product.id == OrderItem.product_id)
        .where(
            OrderItem.store_id == store_id,
            Product.store_id == store_id,
            OrderItem.order_id == order.id,
        )
        .order_by(OrderItem.line_number)
    ).all()
    reservations = inventory_queries.reservations_for_order(db, store_id, order.id)
    lines = [
        OrderLineOut(
            id=item.id,
            line_number=item.line_number,
            product_id=item.product_id,
            sku=item.sku,
            product_sku=product_sku,
            product_name=product_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_discount=item.line_discount,
            line_total=item.line_total,
            reservation=(
                ReservationRef(status=reservations[item.id][0], quantity=reservations[item.id][1])
                if item.id in reservations
                else None
            ),
        )
        for item, product_sku, product_name in line_rows
    ]
    reconciliation = reconcile_total(
        [(line.quantity, line.unit_price, line.line_discount) for line in lines],
        discount_total=order.discount_total,
        shipping_total=order.shipping_total,
        tax_total=order.tax_total,
        total=order.total,
    )

    events = db.scalars(
        select(OrderEvent)
        .where(OrderEvent.store_id == store_id, OrderEvent.order_id == order.id)
        # Events of one transaction share occurred_at; the creation event (no from_status) first.
        .order_by(OrderEvent.occurred_at, OrderEvent.from_status.is_not(None), OrderEvent.id)
    ).all()

    overdue = is_overdue(order.status, order.ship_by, as_of)
    hours_overdue = None
    if overdue and order.ship_by is not None:
        micros = (as_of - order.ship_by) // timedelta(microseconds=1)
        hours_overdue = (Decimal(micros) / Decimal(3_600_000_000)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    return OrderDetail(
        id=order.id,
        order_number=order.order_number,
        channel=order.channel,
        customer_ref=order.customer_ref,
        status=order.status,
        payment_status=order.payment_status,
        fulfillment_status=order.fulfillment_status,
        placed_at=order.placed_at,
        paid_at=order.paid_at,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        cancelled_at=order.cancelled_at,
        ship_by=order.ship_by,
        ship_by_source=order.ship_by_source,
        is_overdue=overdue,
        hours_overdue=hours_overdue,
        carrier=order.carrier,
        tracking_number=order.tracking_number,
        amounts=OrderAmounts(
            currency=order.currency,
            subtotal=order.subtotal,
            discount_total=order.discount_total,
            shipping_total=order.shipping_total,
            tax_total=order.tax_total,
            total=order.total,
            lines_total=reconciliation.lines_total,
            expected_total=reconciliation.expected_total,
            difference=reconciliation.difference,
            has_total_mismatch=reconciliation.has_mismatch,
        ),
        lines=lines,
        events=[
            OrderEventOut(
                id=e.id,
                from_status=e.from_status,
                to_status=e.to_status,
                skipped_statuses=list(e.skipped_statuses or []),
                payment_status=e.payment_status,
                fulfillment_status=e.fulfillment_status,
                source=e.source,
                import_id=e.import_id,
                actor_user_id=e.actor_user_id,
                occurred_at=e.occurred_at,
            )
            for e in events
        ],
        exceptions=linked_exceptions(db, store_id, EntityType.ORDER, order.id),
        last_import_id=order.last_import_id,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
