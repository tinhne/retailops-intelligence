"""Read-side inventory queries: stock positions, movements, velocity and reconciliation.

SELECT only; every write goes through ``inventory.service``. Health is computed on read (BR-141).
``health_sql`` mirrors ``calculations.classify_health`` so lists can be filtered and paginated in
the database; a parity test keeps the two identical, and displayed values always come from
``classify_health`` itself. The building blocks here (balance subquery, health and velocity) are
reused by the catalog and analytics queries so the formulas exist once.
"""

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Numeric,
    Select,
    Subquery,
    and_,
    case,
    cast,
    func,
    literal,
    null,
    or_,
    select,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import SQLCoreOperations

from app.core.pagination import Page, PageParams
from app.domains.catalog.models import Product, ProductStatus
from app.domains.imports import service as imports_service
from app.domains.inventory import service as inventory_service
from app.domains.inventory.calculations import (
    StockHealth,
    avg_daily_units,
    classify_health,
    days_of_cover,
)
from app.domains.inventory.models import (
    InventoryBalance,
    InventoryMovement,
    MovementSource,
    MovementType,
    ReservationStatus,
    StockReservation,
)
from app.domains.inventory.schemas import (
    DriftOut,
    InventoryPositionOut,
    MovementOut,
    MovementSort,
    PositionSort,
    ReconciliationOut,
    StockSnapshot,
)
from app.domains.orders.models import Order, OrderItem
from app.domains.orders.sql import counts_as_sale

SHIPMENT_REFERENCE_PREFIX = "order_item:"  # inventory.service._ensure_shipment_movement

# ---------------------------------------------------------------------------------------------
# Building blocks shared with catalog and analytics queries
# ---------------------------------------------------------------------------------------------


def balance_subquery(store_id: uuid.UUID) -> Subquery:
    """Cached balances of one store, to be outer-joined on product id (no row = all zero)."""
    return (
        select(
            InventoryBalance.product_id,
            InventoryBalance.on_hand,
            InventoryBalance.reserved,
            InventoryBalance.incoming,
            InventoryBalance.incoming_eta,
            InventoryBalance.last_cycle_count_at,
        )
        .where(InventoryBalance.store_id == store_id)
        .subquery("balance")
    )


def stock_columns(
    balance: Subquery,
) -> tuple[ColumnElement[int], ColumnElement[int], ColumnElement[int]]:
    """(on_hand, reserved, available) over an outer-joined balance subquery (BR-101)."""
    on_hand: ColumnElement[int] = func.coalesce(balance.c.on_hand, 0)
    reserved: ColumnElement[int] = func.coalesce(balance.c.reserved, 0)
    return on_hand, reserved, on_hand - reserved


def health_sql(
    available: ColumnElement[int],
    reorder_point: SQLCoreOperations[int],
    status: SQLCoreOperations[Any],
    factor: Decimal,
) -> ColumnElement[Any]:
    """SQL twin of ``classify_health`` (§2.5, BR-140). NULL for products that are not ACTIVE."""
    threshold = func.ceil(cast(reorder_point, Numeric) * literal(factor, Numeric(4, 2)))
    return case(
        (status != ProductStatus.ACTIVE, null()),
        (available < 0, StockHealth.OVERSOLD.value),
        (available == 0, StockHealth.OUT_OF_STOCK.value),
        (
            and_(reorder_point > 0, available <= reorder_point),
            StockHealth.BELOW_REORDER_POINT.value,
        ),
        (
            and_(reorder_point > 0, available <= threshold),
            StockHealth.APPROACHING_REORDER_POINT.value,
        ),
        else_=StockHealth.HEALTHY.value,
    )


def product_health(
    status: ProductStatus, available_qty: int, reorder_point: int, factor: Decimal
) -> StockHealth | None:
    """Health shown to users: §2.5 applies to ACTIVE products only."""
    if status is not ProductStatus.ACTIVE:
        return None
    return classify_health(available_qty, reorder_point, factor)


def velocity_window(as_of: datetime, window_days: int) -> tuple[datetime, datetime]:
    """BR-150 window: orders placed in ``(as_of − window_days, as_of]``."""
    return as_of - timedelta(days=window_days), as_of


def _sales_conditions(
    store_id: uuid.UUID, since: datetime, until: datetime
) -> list[ColumnElement[bool]]:
    return [
        OrderItem.store_id == store_id,
        Order.store_id == store_id,
        Order.placed_at > since,
        Order.placed_at <= until,
        counts_as_sale(),
    ]


def units_sold_subquery(store_id: uuid.UUID, *, as_of: datetime, window_days: int) -> Subquery:
    """Units sold per product in the velocity window (BR-150), as a joinable subquery."""
    since, until = velocity_window(as_of, window_days)
    return (
        select(OrderItem.product_id, func.sum(OrderItem.quantity).label("units"))
        .join(Order, Order.id == OrderItem.order_id)
        .where(*_sales_conditions(store_id, since, until))
        .group_by(OrderItem.product_id)
        .subquery("units_sold")
    )


def units_sold(
    db: Session,
    store_id: uuid.UUID,
    *,
    as_of: datetime,
    window_days: int,
    product_ids: Collection[uuid.UUID] | None = None,
) -> dict[uuid.UUID, int]:
    """Units on order lines placed in the velocity window whose order counts as a sale (BR-150).

    See ``orders.sql.counts_as_sale`` for which orders count. Products without sales are
    absent from the result.
    """
    since, until = velocity_window(as_of, window_days)
    stmt = (
        select(OrderItem.product_id, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .where(*_sales_conditions(store_id, since, until))
        .group_by(OrderItem.product_id)
    )
    if product_ids is not None:
        stmt = stmt.where(OrderItem.product_id.in_(list(product_ids)))
    return {pid: int(units) for pid, units in db.execute(stmt).all()}


def velocity(
    db: Session,
    store_id: uuid.UUID,
    *,
    as_of: datetime,
    window_days: int,
    product_ids: Collection[uuid.UUID] | None = None,
) -> dict[uuid.UUID, Decimal]:
    """avg_daily_units per product with sales in the window (BR-150; an estimate, BR-152)."""
    sold = units_sold(db, store_id, as_of=as_of, window_days=window_days, product_ids=product_ids)
    return {pid: avg_daily_units(units, window_days) for pid, units in sold.items()}


def days_of_cover_sql(
    available: ColumnElement[int], units: ColumnElement[Any], window_days: int
) -> ColumnElement[Any]:
    """SQL twin of ``days_of_cover(available, avg_daily_units(units, window))`` for sorting.

    Postgres ``round(numeric, n)`` rounds half away from zero, which equals ROUND_HALF_UP for the
    non-negative values involved.
    """
    daily = func.round(cast(func.coalesce(units, 0), Numeric) / window_days, 2)
    cover = func.round(cast(func.greatest(available, 0), Numeric) / daily, 1)
    return case((daily > 0, cover), else_=null())


def get_stock(db: Session, store_id: uuid.UUID, product_id: uuid.UUID) -> StockSnapshot:
    """Current stock of one product without creating a balance row (no row = all zero)."""
    balance = db.scalar(
        select(InventoryBalance).where(
            InventoryBalance.store_id == store_id, InventoryBalance.product_id == product_id
        )
    )
    if balance is None:
        return StockSnapshot(
            on_hand=0,
            reserved=0,
            available=0,
            incoming=0,
            incoming_eta=None,
            last_cycle_count_at=None,
        )
    return StockSnapshot(
        on_hand=balance.on_hand,
        reserved=balance.reserved,
        available=balance.available,
        incoming=balance.incoming,
        incoming_eta=balance.incoming_eta,
        last_cycle_count_at=balance.last_cycle_count_at,
    )


def reservations_for_order(
    db: Session, store_id: uuid.UUID, order_id: uuid.UUID
) -> dict[uuid.UUID, tuple[ReservationStatus, int]]:
    """Reservation status and quantity per order line (order_item id) of one order."""
    rows = db.execute(
        select(
            StockReservation.order_item_id, StockReservation.status, StockReservation.quantity
        ).where(StockReservation.store_id == store_id, StockReservation.order_id == order_id)
    ).all()
    return {item_id: (status, quantity) for item_id, status, quantity in rows}


def _count(db: Session, stmt: Select[*tuple[Any, ...]]) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)


# ---------------------------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------------------------


def list_positions(
    db: Session,
    store_id: uuid.UUID,
    *,
    q: str | None,
    health: Sequence[StockHealth] | None,
    category: str | None,
    include_inactive: bool,
    sort: PositionSort,
    paging: PageParams,
    as_of: datetime,
    factor: Decimal,
    window_days: int,
) -> Page[InventoryPositionOut]:
    """One row per product with stock, health and velocity estimates (BR-101, §2.5, BR-150)."""
    balance = balance_subquery(store_id)
    sold = units_sold_subquery(store_id, as_of=as_of, window_days=window_days)
    on_hand, reserved, available_col = stock_columns(balance)
    units = func.coalesce(sold.c.units, 0)
    cover = days_of_cover_sql(available_col, sold.c.units, window_days)

    stmt = (
        select(
            Product,
            on_hand,
            reserved,
            func.coalesce(balance.c.incoming, 0),
            balance.c.incoming_eta,
            balance.c.last_cycle_count_at,
            units,
        )
        .outerjoin(balance, balance.c.product_id == Product.id)
        .outerjoin(sold, sold.c.product_id == Product.id)
        .where(Product.store_id == store_id)
    )
    if not include_inactive:
        stmt = stmt.where(Product.status == ProductStatus.ACTIVE)
    if q:
        stmt = stmt.where(
            or_(
                Product.sku.icontains(q, autoescape=True),
                Product.name.icontains(q, autoescape=True),
            )
        )
    if category:
        stmt = stmt.where(Product.category == category)
    if health:
        health_col = health_sql(available_col, Product.reorder_point, Product.status, factor)
        stmt = stmt.where(health_col.in_([h.value for h in health]))

    total = _count(db, stmt)
    descending = sort.startswith("-")
    key = sort.lstrip("-")
    if key == "days_of_cover":
        primary = (cover.desc() if descending else cover.asc()).nulls_last()
    elif key == "available":
        primary = available_col.desc() if descending else available_col.asc()
    else:
        primary = Product.sku.desc() if descending else Product.sku.asc()
    rows = db.execute(
        stmt.order_by(primary, Product.sku, Product.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()

    items: list[InventoryPositionOut] = []
    for product, oh, rsv, incoming, eta, counted_at, sold_units in rows:
        avail = oh - rsv
        daily = avg_daily_units(int(sold_units), window_days)
        items.append(
            InventoryPositionOut(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                status=product.status,
                on_hand=oh,
                reserved=rsv,
                available=avail,
                incoming=incoming,
                incoming_eta=eta,
                reorder_point=product.reorder_point,
                health=product_health(product.status, avail, product.reorder_point, factor),
                avg_daily_units=daily,
                days_of_cover=days_of_cover(avail, daily),
                last_cycle_count_at=counted_at,
            )
        )
    return Page[InventoryPositionOut](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


def list_movements(
    db: Session,
    store_id: uuid.UUID,
    *,
    product_id: uuid.UUID | None,
    movement_types: Sequence[MovementType] | None,
    source: MovementSource | None,
    import_id: uuid.UUID | None = None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    sort: MovementSort,
    paging: PageParams,
) -> Page[MovementOut]:
    """Ledger rows (BR-110), newest recorded first by default. ``occurred_to`` is exclusive.

    Each row carries the file name of the import that wrote it and, for shipments, the order of
    the line its ``order_item:{id}`` reference names. Both are looked up for the page only.
    """
    stmt = (
        select(InventoryMovement, Product.sku, Product.name)
        .join(Product, Product.id == InventoryMovement.product_id)
        .where(InventoryMovement.store_id == store_id, Product.store_id == store_id)
    )
    if product_id is not None:
        stmt = stmt.where(InventoryMovement.product_id == product_id)
    if movement_types:
        stmt = stmt.where(InventoryMovement.movement_type.in_(list(movement_types)))
    if source is not None:
        stmt = stmt.where(InventoryMovement.source == source)
    if import_id is not None:
        stmt = stmt.where(InventoryMovement.import_id == import_id)
    if occurred_from is not None:
        stmt = stmt.where(InventoryMovement.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(InventoryMovement.occurred_at < occurred_to)

    total = _count(db, stmt)
    column = {
        "recorded_at": InventoryMovement.recorded_at,
        "occurred_at": InventoryMovement.occurred_at,
    }[sort.lstrip("-")]
    if sort.startswith("-"):
        order = (column.desc(), InventoryMovement.occurred_at.desc(), InventoryMovement.id.desc())
    else:
        order = (column.asc(), InventoryMovement.occurred_at.asc(), InventoryMovement.id.asc())
    rows = db.execute(stmt.order_by(*order).offset(paging.offset).limit(paging.page_size)).all()
    filenames = imports_service.filenames_by_id(db, store_id, [m.import_id for m, _, _ in rows])
    shipment_orders = _shipment_orders(db, store_id, [m.reference for m, _, _ in rows])
    return Page[MovementOut](
        items=[
            MovementOut(
                id=m.id,
                product_id=m.product_id,
                sku=sku,
                product_name=name,
                movement_type=m.movement_type,
                on_hand_delta=m.on_hand_delta,
                incoming_delta=m.incoming_delta,
                on_hand_after=m.on_hand_after,
                incoming_after=m.incoming_after,
                occurred_at=m.occurred_at,
                recorded_at=m.recorded_at,
                source=m.source,
                reference=m.reference,
                import_id=m.import_id,
                import_filename=filenames.get(m.import_id) if m.import_id else None,
                order_id=shipment_orders.get(m.reference) if m.reference else None,
                note=m.note,
                created_by=m.created_by,
            )
            for m, sku, name in rows
        ],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


def _shipment_orders(
    db: Session, store_id: uuid.UUID, references: Sequence[str | None]
) -> dict[str, uuid.UUID]:
    """``order_item:{id}`` references → the order of that line (derived, nothing stored)."""
    item_ids: dict[uuid.UUID, str] = {}
    for reference in references:
        if reference and reference.startswith(SHIPMENT_REFERENCE_PREFIX):
            try:
                item_ids[uuid.UUID(reference.removeprefix(SHIPMENT_REFERENCE_PREFIX))] = reference
            except ValueError:
                continue
    if not item_ids:
        return {}
    rows = db.execute(
        select(OrderItem.id, OrderItem.order_id).where(
            OrderItem.store_id == store_id, OrderItem.id.in_(item_ids)
        )
    ).all()
    return {item_ids[item_id]: order_id for item_id, order_id in rows}


def reconciliation(db: Session, store_id: uuid.UUID, *, checked_at: datetime) -> ReconciliationOut:
    """BR-104 drift report from ``inventory.service.reconcile``. Reports, never fixes."""
    drifts = inventory_service.reconcile(db, store_id)
    product_ids = {d.product_id for d in drifts}
    skus: dict[uuid.UUID, str] = {}
    if product_ids:
        rows = db.execute(
            select(Product.id, Product.sku).where(
                Product.store_id == store_id, Product.id.in_(product_ids)
            )
        ).all()
        skus = {product_id: sku for product_id, sku in rows}
    items = sorted(
        (
            DriftOut(
                product_id=d.product_id,
                sku=skus.get(d.product_id),
                field=d.field,
                stored=d.stored,
                computed=d.computed,
            )
            for d in drifts
        ),
        key=lambda d: (d.sku or "", d.field),
    )
    return ReconciliationOut(
        checked_at=checked_at, is_consistent=not items, drift_count=len(items), items=items
    )
