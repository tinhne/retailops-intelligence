"""Read-only evaluation snapshot: everything the rules need for one store, as plain dataclasses.

This is the documented exception to module ownership for the rule engine (SYSTEM_ARCHITECTURE.md
§10): it SELECTs from catalog, inventory, orders, imports and identity tables, never writes, and
filters every query by ``store_id``. No ORM object leaves this module, so the rules stay pure and
can be unit-tested with hand-built snapshots.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from functools import cached_property
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.identity.models import DEFAULT_PRIORITY_WEIGHTS, Store, StoreSettings
from app.domains.imports.models import (
    DataImport,
    ImportRowIssue,
    ImportStatus,
    ImportType,
    IssueSeverity,
)
from app.domains.inventory.models import InventoryBalance, InventoryMovement, MovementType
from app.domains.orders.models import (
    FulfillmentStatus,
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    ShipBySource,
)
from app.domains.orders.sql import counts_as_sale
from app.domains.orders.state import COMMITTED_STATUSES, PENDING_DEMAND_STATUSES

NEGATIVE_ON_HAND_MOVEMENT_LIMIT = 10


@dataclass(frozen=True)
class RuleSettings:
    """Store thresholds used by rules, reconciliation and priority (BUSINESS_RULES.md §7)."""

    fulfillment_sla_hours: int = 48
    stall_threshold_hours: int = 12
    refund_overdue_hours: int = 24
    velocity_window_days: int = 28
    reopen_window_hours: int = 72
    exposure_cap: Decimal = Decimal("5000.00")
    priority_weights: Mapping[str, Any] = field(
        default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS)
    )


@dataclass(frozen=True)
class ProductFacts:
    id: uuid.UUID
    sku: str
    name: str
    status: ProductStatus
    unit_price: Decimal
    reorder_point: int
    reorder_quantity: int | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    lead_time_days: int | None
    on_hand: int = 0
    reserved: int = 0
    incoming: int = 0
    incoming_eta: datetime | None = None
    last_cycle_count_at: datetime | None = None
    units_sold_in_window: int = 0

    @property
    def available(self) -> int:
        """BR-101: available = on_hand − reserved."""
        return self.on_hand - self.reserved


@dataclass(frozen=True)
class DemandLine:
    """An order line of a committed or pending order, with the order context rules need."""

    order_id: uuid.UUID
    order_number: str
    order_status: OrderStatus
    placed_at: datetime
    paid_at: datetime | None
    ship_by: datetime | None
    order_item_id: uuid.UUID
    line_number: int
    product_id: uuid.UUID
    sku: str
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class OrderFacts:
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    placed_at: datetime
    paid_at: datetime | None
    ship_by: datetime | None
    ship_by_source: ShipBySource | None
    cancelled_at: datetime | None
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    line_count: int = 0
    # Σ(quantity × unit_price − line_discount) over the order's lines (BR-205).
    line_sum: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class MovementFacts:
    id: uuid.UUID
    product_id: uuid.UUID
    movement_type: MovementType
    on_hand_delta: int
    incoming_delta: int
    on_hand_after: int
    occurred_at: datetime
    reference: str | None


@dataclass(frozen=True)
class RejectedImportRows:
    """Rejected import rows that name an order number (evidence for DQ-ORDER-TOTAL@1)."""

    count: int
    import_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class EvaluationSnapshot:
    store_id: uuid.UUID
    as_of: datetime
    currency: str = "USD"
    timezone: str = "UTC"
    products: Mapping[uuid.UUID, ProductFacts] = field(default_factory=dict)
    committed_lines: tuple[DemandLine, ...] = ()
    pending_lines: tuple[DemandLine, ...] = ()
    orders: Mapping[uuid.UUID, OrderFacts] = field(default_factory=dict)
    # Last movements and the latest cycle count, only for products with on_hand < 0.
    recent_movements: Mapping[uuid.UUID, tuple[MovementFacts, ...]] = field(default_factory=dict)
    last_cycle_counts: Mapping[uuid.UUID, MovementFacts] = field(default_factory=dict)
    rejected_import_rows: Mapping[str, RejectedImportRows] = field(default_factory=dict)
    # Latest applied_at of a completed import (manual-resolution verification grace rule).
    last_import_applied_at: datetime | None = None

    @cached_property
    def products_in_order(self) -> tuple[ProductFacts, ...]:
        """Products sorted by SKU so rules emit findings in a deterministic order."""
        return tuple(sorted(self.products.values(), key=lambda p: (p.sku, str(p.id))))

    @cached_property
    def orders_in_order(self) -> tuple[OrderFacts, ...]:
        return tuple(sorted(self.orders.values(), key=lambda o: (o.order_number, str(o.id))))

    @cached_property
    def _committed_by_product(self) -> Mapping[uuid.UUID, tuple[DemandLine, ...]]:
        return _group(self.committed_lines, lambda line: line.product_id)

    @cached_property
    def _pending_by_product(self) -> Mapping[uuid.UUID, tuple[DemandLine, ...]]:
        return _group(self.pending_lines, lambda line: line.product_id)

    @cached_property
    def _committed_by_order(self) -> Mapping[uuid.UUID, tuple[DemandLine, ...]]:
        return _group(self.committed_lines, lambda line: line.order_id)

    def committed_lines_for(self, product_id: uuid.UUID) -> tuple[DemandLine, ...]:
        return self._committed_by_product.get(product_id, ())

    def pending_lines_for(self, product_id: uuid.UUID) -> tuple[DemandLine, ...]:
        return self._pending_by_product.get(product_id, ())

    def pending_demand(self, product_id: uuid.UUID) -> int:
        """Units on CREATED / PAYMENT_PENDING orders (BUSINESS_RULES.md §2.1)."""
        return sum(line.quantity for line in self.pending_lines_for(product_id))

    def lines_for_order(self, order_id: uuid.UUID) -> tuple[DemandLine, ...]:
        """Lines of a committed order (the only orders whose lines rules need)."""
        return tuple(
            sorted(self._committed_by_order.get(order_id, ()), key=lambda line: line.line_number)
        )


def _group[K, V](items: tuple[V, ...], key: Callable[[V], K]) -> dict[K, tuple[V, ...]]:
    grouped: dict[K, list[V]] = defaultdict(list)
    for item in items:
        grouped[key(item)].append(item)
    return {k: tuple(v) for k, v in grouped.items()}


# --- Loading -------------------------------------------------------------------------------------


def load_settings(db: Session, store_id: uuid.UUID) -> RuleSettings:
    row = db.scalar(select(StoreSettings).where(StoreSettings.store_id == store_id))
    if row is None:
        return RuleSettings()
    weights = row.priority_weights if isinstance(row.priority_weights, dict) else {}
    return RuleSettings(
        fulfillment_sla_hours=row.fulfillment_sla_hours,
        stall_threshold_hours=row.stall_threshold_hours,
        refund_overdue_hours=row.refund_overdue_hours,
        velocity_window_days=row.velocity_window_days,
        reopen_window_hours=row.reopen_window_hours,
        exposure_cap=row.exposure_cap,
        priority_weights={**DEFAULT_PRIORITY_WEIGHTS, **weights},
    )


def load_snapshot(
    db: Session, store_id: uuid.UUID, as_of: datetime, settings: RuleSettings
) -> EvaluationSnapshot:
    """Load the evaluation snapshot for one store as of ``as_of``. SELECT only."""
    store = db.execute(select(Store.currency, Store.timezone).where(Store.id == store_id)).one()
    units_sold = _units_sold(db, store_id, as_of, settings.velocity_window_days)
    products = _products(db, store_id, units_sold)
    committed = _demand_lines(db, store_id, COMMITTED_STATUSES)
    pending = _demand_lines(db, store_id, PENDING_DEMAND_STATUSES)
    negative_ids = [p.id for p in products.values() if p.on_hand < 0]
    return EvaluationSnapshot(
        store_id=store_id,
        as_of=as_of,
        currency=store.currency,
        timezone=store.timezone,
        products=products,
        committed_lines=committed,
        pending_lines=pending,
        orders=_orders(db, store_id),
        recent_movements=_recent_movements(db, store_id, negative_ids),
        last_cycle_counts=_last_cycle_counts(db, store_id, negative_ids),
        rejected_import_rows=_rejected_import_rows(db, store_id),
        last_import_applied_at=db.scalar(
            select(func.max(DataImport.applied_at)).where(
                DataImport.store_id == store_id,
                DataImport.status.in_([ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS]),
            )
        ),
    )


def _units_sold(
    db: Session, store_id: uuid.UUID, as_of: datetime, window_days: int
) -> dict[uuid.UUID, int]:
    """BR-150: units on lines placed in (as_of − window, as_of] that count as sales.

    Excluded: CANCELLED, PAYMENT_FAILED, CREATED, PAYMENT_PENDING, and orders refunded before
    they shipped (REFUNDED with fulfillment UNFULFILLED).
    """
    window_start = as_of - timedelta(days=max(window_days, 1))
    rows = db.execute(
        select(OrderItem.product_id, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.store_id == store_id,
            OrderItem.store_id == store_id,
            Order.placed_at > window_start,
            Order.placed_at <= as_of,
            counts_as_sale(),
        )
        .group_by(OrderItem.product_id)
    ).all()
    return {product_id: int(qty or 0) for product_id, qty in rows}


def _products(
    db: Session, store_id: uuid.UUID, units_sold: Mapping[uuid.UUID, int]
) -> dict[uuid.UUID, ProductFacts]:
    rows = db.execute(
        select(Product, Supplier.name, Supplier.lead_time_days, InventoryBalance)
        .outerjoin(
            Supplier, and_(Supplier.id == Product.supplier_id, Supplier.store_id == store_id)
        )
        .outerjoin(
            InventoryBalance,
            and_(InventoryBalance.product_id == Product.id, InventoryBalance.store_id == store_id),
        )
        .where(Product.store_id == store_id)
    ).all()
    products: dict[uuid.UUID, ProductFacts] = {}
    for product, supplier_name, lead_time, balance in rows:
        products[product.id] = ProductFacts(
            id=product.id,
            sku=product.sku,
            name=product.name,
            status=product.status,
            unit_price=product.unit_price,
            reorder_point=product.reorder_point,
            reorder_quantity=product.reorder_quantity,
            supplier_id=product.supplier_id,
            supplier_name=supplier_name,
            lead_time_days=lead_time,
            on_hand=balance.on_hand if balance else 0,
            reserved=balance.reserved if balance else 0,
            incoming=balance.incoming if balance else 0,
            incoming_eta=balance.incoming_eta if balance else None,
            last_cycle_count_at=balance.last_cycle_count_at if balance else None,
            units_sold_in_window=units_sold.get(product.id, 0),
        )
    return products


def _demand_lines(
    db: Session, store_id: uuid.UUID, statuses: frozenset[OrderStatus]
) -> tuple[DemandLine, ...]:
    rows = db.execute(
        select(
            Order.id,
            Order.order_number,
            Order.status,
            Order.placed_at,
            Order.paid_at,
            Order.ship_by,
            OrderItem.id,
            OrderItem.line_number,
            OrderItem.product_id,
            OrderItem.sku,
            OrderItem.quantity,
            OrderItem.unit_price,
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(
            Order.store_id == store_id,
            OrderItem.store_id == store_id,
            Order.status.in_(statuses),
        )
        .order_by(Order.order_number, OrderItem.line_number)
    ).all()
    return tuple(
        DemandLine(
            order_id=r[0],
            order_number=r[1],
            order_status=r[2],
            placed_at=r[3],
            paid_at=r[4],
            ship_by=r[5],
            order_item_id=r[6],
            line_number=r[7],
            product_id=r[8],
            sku=r[9],
            quantity=r[10],
            unit_price=r[11],
        )
        for r in rows
    )


def _orders(db: Session, store_id: uuid.UUID) -> dict[uuid.UUID, OrderFacts]:
    """Orders needing order-level checks: committed (overdue/stalled), cancelled while paid
    (refund pending), and every order with at least one line (total reconciliation)."""
    line_totals = (
        select(
            OrderItem.order_id.label("order_id"),
            func.count(OrderItem.id).label("line_count"),
            func.sum(OrderItem.quantity * OrderItem.unit_price - OrderItem.line_discount).label(
                "line_sum"
            ),
        )
        .where(OrderItem.store_id == store_id)
        .group_by(OrderItem.order_id)
        .subquery()
    )
    rows = db.execute(
        select(Order, line_totals.c.line_count, line_totals.c.line_sum)
        .outerjoin(line_totals, line_totals.c.order_id == Order.id)
        .where(
            Order.store_id == store_id,
            or_(
                Order.status.in_(COMMITTED_STATUSES),
                and_(
                    Order.status == OrderStatus.CANCELLED,
                    Order.payment_status == PaymentStatus.PAID,
                ),
                line_totals.c.line_count > 0,
            ),
        )
    ).all()
    orders: dict[uuid.UUID, OrderFacts] = {}
    for order, line_count, line_sum in rows:
        orders[order.id] = OrderFacts(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            payment_status=order.payment_status,
            fulfillment_status=order.fulfillment_status,
            placed_at=order.placed_at,
            paid_at=order.paid_at,
            ship_by=order.ship_by,
            ship_by_source=order.ship_by_source,
            cancelled_at=order.cancelled_at,
            currency=order.currency,
            subtotal=order.subtotal,
            discount_total=order.discount_total,
            shipping_total=order.shipping_total,
            tax_total=order.tax_total,
            total=order.total,
            line_count=int(line_count or 0),
            line_sum=Decimal(line_sum or 0),
        )
    return orders


def _movement(m: InventoryMovement) -> MovementFacts:
    return MovementFacts(
        id=m.id,
        product_id=m.product_id,
        movement_type=m.movement_type,
        on_hand_delta=m.on_hand_delta,
        incoming_delta=m.incoming_delta,
        on_hand_after=m.on_hand_after,
        occurred_at=m.occurred_at,
        reference=m.reference,
    )


def _recent_movements(
    db: Session, store_id: uuid.UUID, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[MovementFacts, ...]]:
    if not product_ids:
        return {}
    ranked = (
        select(
            InventoryMovement.id.label("id"),
            func.row_number()
            .over(
                partition_by=InventoryMovement.product_id,
                order_by=(
                    InventoryMovement.occurred_at.desc(),
                    InventoryMovement.recorded_at.desc(),
                    InventoryMovement.id.desc(),
                ),
            )
            .label("rank"),
        )
        .where(
            InventoryMovement.store_id == store_id,
            InventoryMovement.product_id.in_(product_ids),
        )
        .subquery()
    )
    movements = db.scalars(
        select(InventoryMovement)
        .join(ranked, ranked.c.id == InventoryMovement.id)
        .where(ranked.c.rank <= NEGATIVE_ON_HAND_MOVEMENT_LIMIT)
        .order_by(
            InventoryMovement.product_id,
            InventoryMovement.occurred_at.desc(),
            InventoryMovement.recorded_at.desc(),
            InventoryMovement.id.desc(),
        )
    ).all()
    result: dict[uuid.UUID, list[MovementFacts]] = defaultdict(list)
    for movement in movements:
        result[movement.product_id].append(_movement(movement))
    return {k: tuple(v) for k, v in result.items()}


def _last_cycle_counts(
    db: Session, store_id: uuid.UUID, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, MovementFacts]:
    if not product_ids:
        return {}
    movements = db.scalars(
        select(InventoryMovement)
        .where(
            InventoryMovement.store_id == store_id,
            InventoryMovement.product_id.in_(product_ids),
            InventoryMovement.movement_type == MovementType.CYCLE_COUNT,
        )
        .order_by(
            InventoryMovement.product_id,
            InventoryMovement.occurred_at.desc(),
            InventoryMovement.id.desc(),
        )
        .ext(distinct_on(InventoryMovement.product_id))
    ).all()
    return {m.product_id: _movement(m) for m in movements}


def _rejected_import_rows(db: Session, store_id: uuid.UUID) -> dict[str, RejectedImportRows]:
    """Rejected order / order-line import rows keyed by the order number they name.

    Limitation: ``import_row_issue`` stores the offending column and value, not the row's natural
    key, so only issues raised on the ``order_number`` column can be attributed to an order.
    """
    rows = db.execute(
        select(ImportRowIssue.raw_value, ImportRowIssue.import_id)
        .join(DataImport, DataImport.id == ImportRowIssue.import_id)
        .where(
            DataImport.store_id == store_id,
            DataImport.import_type.in_([ImportType.ORDERS, ImportType.ORDER_ITEMS]),
            ImportRowIssue.severity == IssueSeverity.ERROR,
            ImportRowIssue.column == "order_number",
            ImportRowIssue.raw_value.is_not(None),
        )
    ).all()
    counts: dict[str, int] = defaultdict(int)
    imports: dict[str, set[uuid.UUID]] = defaultdict(set)
    for raw_value, import_id in rows:
        key = str(raw_value).strip()
        counts[key] += 1
        imports[key].add(import_id)
    return {
        key: RejectedImportRows(count=counts[key], import_ids=tuple(sorted(imports[key], key=str)))
        for key in counts
    }
