"""Read-only aggregate SQL over other modules' tables (SYSTEM_ARCHITECTURE.md §10.1).

SELECT only, never a locking clause, and every query carries a ``store_id`` predicate. Business
formulas are not re-implemented here: overdue (BR-202) comes from ``orders.queries``, health
(§2.5) from ``inventory.queries``. This module only counts, sums and buckets by store-local day.
All windows are half-open: ``start <= ts < end``.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    MANUAL_RESOLUTION_CODES,
    EvaluationRun,
    ExceptionCategory,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    OperationalException,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.identity.models import User
from app.domains.imports.models import DataImport, ImportStatus, ImportType
from app.domains.inventory import queries as inventory_queries
from app.domains.orders.models import Order, OrderItem, PaymentStatus
from app.domains.orders.queries import overdue_condition
from app.domains.orders.sql import counts_as_sale
from app.domains.orders.state import COMMITTED_STATUSES

APPLIED_IMPORT_STATUSES = (ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS)
GMV_PAYMENT_STATUSES = (PaymentStatus.PAID, PaymentStatus.REFUNDED)
# A resolution counts as "resolved" when manual or automatic; SUPERSEDED work continues elsewhere.
COUNTED_RESOLUTION_CODES = MANUAL_RESOLUTION_CODES | {ResolutionCode.CONDITION_CLEARED}


def gmv_condition() -> Any:
    """The GMV population: the order was paid (``paid_at`` set, payment PAID or REFUNDED).

    Unpaid orders (PENDING, FAILED, cancelled before payment) never count. Orders cancelled or
    refunded after payment still count: GMV is gross and refunds are not subtracted.
    """
    return and_(Order.paid_at.is_not(None), Order.payment_status.in_(GMV_PAYMENT_STATUSES))


def _local_day(column: Any, timezone: str) -> Any:
    """Calendar date of a timestamptz in the store time zone (BR-501)."""
    return cast(func.timezone(timezone, column), Date)


def _in_window(column: Any, start: datetime, end: datetime) -> Any:
    return and_(column >= start, column < end)


# ---------------------------------------------------------------------------------------------
# Data freshness (M-05)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestImport:
    import_type: ImportType
    import_id: uuid.UUID
    status: ImportStatus
    applied_at: datetime


def latest_applied_imports(db: Session, store_id: uuid.UUID) -> dict[ImportType, LatestImport]:
    rows = db.execute(
        select(DataImport.import_type, DataImport.id, DataImport.status, DataImport.applied_at)
        .where(
            DataImport.store_id == store_id,
            DataImport.status.in_(APPLIED_IMPORT_STATUSES),
            DataImport.applied_at.is_not(None),
        )
        .ext(distinct_on(DataImport.import_type))
        .order_by(DataImport.import_type, DataImport.applied_at.desc(), DataImport.id)
    ).all()
    return {
        import_type: LatestImport(import_type, import_id, status, applied_at)
        for import_type, import_id, status, applied_at in rows
        if applied_at is not None
    }


def latest_evaluation_run(db: Session, store_id: uuid.UUID) -> EvaluationRun | None:
    return db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.store_id == store_id)
        .order_by(EvaluationRun.started_at.desc(), EvaluationRun.id)
        .limit(1)
    )


# ---------------------------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveExceptionGroup:
    severity: Severity
    band: PriorityBand
    category: ExceptionCategory
    unassigned: bool
    past_due: bool
    reopened: bool
    count: int
    exposure: Decimal


def active_exception_groups(
    db: Session, store_id: uuid.UUID, *, as_of: datetime
) -> list[ActiveExceptionGroup]:
    e = OperationalException
    unassigned = e.assignee_id.is_(None)
    past_due = e.due_at < as_of
    reopened = e.status == ExceptionStatus.REOPENED
    rows = db.execute(
        select(
            e.severity,
            e.priority_band,
            e.category,
            unassigned,
            past_due,
            reopened,
            func.count(),
            func.coalesce(func.sum(e.exposure_amount), 0),
        )
        .where(e.store_id == store_id, e.status.in_(ACTIVE_STATUSES))
        .group_by(e.severity, e.priority_band, e.category, unassigned, past_due, reopened)
    ).all()
    return [ActiveExceptionGroup(*row) for row in rows]


def attention_items(
    db: Session, store_id: uuid.UUID, *, limit: int
) -> list[tuple[OperationalException, str | None]]:
    """Active exceptions by priority (score desc, then earliest due, then oldest)."""
    e = OperationalException
    rows = db.execute(
        select(e, User.full_name)
        .outerjoin(User, User.id == e.assignee_id)
        .where(e.store_id == store_id, e.status.in_(ACTIVE_STATUSES))
        .order_by(e.priority_score.desc(), e.due_at, e.first_detected_at, e.reference, e.id)
        .limit(limit)
    ).all()
    return [(exc, name) for exc, name in rows]


def active_by_type(db: Session, store_id: uuid.UUID) -> dict[ExceptionType, int]:
    e = OperationalException
    rows = db.execute(
        select(e.exception_type, func.count())
        .where(e.store_id == store_id, e.status.in_(ACTIVE_STATUSES))
        .group_by(e.exception_type)
    ).all()
    return {t: int(n) for t, n in rows}


def detected_by_type(
    db: Session, store_id: uuid.UUID, *, start: datetime, end: datetime
) -> dict[ExceptionType, int]:
    e = OperationalException
    rows = db.execute(
        select(e.exception_type, func.count())
        .where(e.store_id == store_id, _in_window(e.first_detected_at, start, end))
        .group_by(e.exception_type)
    ).all()
    return {t: int(n) for t, n in rows}


@dataclass(frozen=True)
class ResolvedException:
    exception_type: ExceptionType
    resolution_code: ResolutionCode | None
    first_detected_at: datetime
    resolved_at: datetime


def resolved_in_window(
    db: Session, store_id: uuid.UUID, *, start: datetime, end: datetime
) -> list[ResolvedException]:
    """Exceptions currently RESOLVED whose (latest) resolved_at falls in the window (M-10)."""
    e = OperationalException
    rows = db.execute(
        select(e.exception_type, e.resolution_code, e.first_detected_at, e.resolved_at).where(
            e.store_id == store_id,
            e.status == ExceptionStatus.RESOLVED,
            e.resolved_at.is_not(None),
            _in_window(e.resolved_at, start, end),
        )
    ).all()
    return [
        ResolvedException(t, code, first, resolved)
        for t, code, first, resolved in rows
        if resolved is not None
    ]


def reopened_by_type(
    db: Session, store_id: uuid.UUID, *, start: datetime, end: datetime
) -> dict[ExceptionType, int]:
    e = OperationalException
    ev = ExceptionEvent
    rows = db.execute(
        select(e.exception_type, func.count(ev.id))
        .join(ev, ev.exception_id == e.id)
        .where(
            e.store_id == store_id,
            ev.store_id == store_id,
            ev.event_type == ExceptionEventType.REOPENED,
            _in_window(ev.occurred_at, start, end),
        )
        .group_by(e.exception_type)
    ).all()
    return {t: int(n) for t, n in rows}


# ---------------------------------------------------------------------------------------------
# Orders and inventory snapshots
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderSnapshotCounts:
    overdue_count: int
    overdue_value: Decimal
    awaiting_shipment: int


def order_snapshot(db: Session, store_id: uuid.UUID, *, as_of: datetime) -> OrderSnapshotCounts:
    overdue = overdue_condition(as_of)
    row = db.execute(
        select(
            func.count().filter(overdue),
            func.coalesce(func.sum(Order.total).filter(overdue), 0),
            func.count().filter(Order.status.in_(COMMITTED_STATUSES)),
        ).where(Order.store_id == store_id)
    ).one()
    return OrderSnapshotCounts(int(row[0]), Decimal(row[1]), int(row[2]))


def active_product_health_counts(
    db: Session, store_id: uuid.UUID, *, factor: Decimal
) -> dict[str, int]:
    """ACTIVE products grouped by health computed from current balances (§2.5)."""
    balance = inventory_queries.balance_subquery(store_id)
    _, _, available = inventory_queries.stock_columns(balance)
    health = inventory_queries.health_sql(available, Product.reorder_point, Product.status, factor)
    rows = db.execute(
        select(health, func.count())
        .select_from(Product)
        .outerjoin(balance, balance.c.product_id == Product.id)
        .where(Product.store_id == store_id, Product.status == ProductStatus.ACTIVE)
        .group_by(health)
    ).all()
    return {str(h): int(n) for h, n in rows}


# ---------------------------------------------------------------------------------------------
# Sales and fulfillment over windows
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SalesCounts:
    orders_placed: int
    paid_orders: int
    gmv: Decimal


def sales(db: Session, store_id: uuid.UUID, *, start: datetime, end: datetime) -> SalesCounts:
    paid = gmv_condition()
    row = db.execute(
        select(
            func.count(),
            func.count().filter(paid),
            func.coalesce(func.sum(Order.total).filter(paid), 0),
        ).where(Order.store_id == store_id, _in_window(Order.placed_at, start, end))
    ).one()
    return SalesCounts(int(row[0]), int(row[1]), Decimal(row[2]))


@dataclass(frozen=True)
class ShipmentCounts:
    on_time: int
    late: int
    without_deadline: int


def shipments(
    db: Session, store_id: uuid.UUID, *, start: datetime, end: datetime
) -> ShipmentCounts:
    """Orders with shipped_at in the window: on time when ``shipped_at ≤ ship_by`` (M-19)."""
    row = db.execute(
        select(
            func.count().filter(Order.ship_by.is_not(None), Order.shipped_at <= Order.ship_by),
            func.count().filter(Order.ship_by.is_not(None), Order.shipped_at > Order.ship_by),
            func.count().filter(Order.ship_by.is_(None)),
        ).where(Order.store_id == store_id, _in_window(Order.shipped_at, start, end))
    ).one()
    return ShipmentCounts(int(row[0]), int(row[1]), int(row[2]))


# ---------------------------------------------------------------------------------------------
# Daily series (store-local days)
# ---------------------------------------------------------------------------------------------


@dataclass
class DailyRow:
    orders_placed: int = 0
    units: int = 0
    gmv: Decimal = Decimal("0")
    exceptions_detected: int = 0
    exceptions_resolved: int = 0
    shipped_on_time: int = 0
    shipped_late: int = 0


def daily_series(
    db: Session,
    store_id: uuid.UUID,
    *,
    timezone: str,
    start: datetime,
    end: datetime,
    days: Iterable[date],
) -> dict[date, DailyRow]:
    """Per store-local day: orders, units, GMV, exceptions detected/resolved, shipments."""
    series = {d: DailyRow() for d in days}

    def bucket(day: date) -> DailyRow:
        # A timestamp inside [start, end) always maps to one of the requested local days.
        return series.setdefault(day, DailyRow())

    placed_day = _local_day(Order.placed_at, timezone)
    paid = gmv_condition()
    for day, placed, gmv in db.execute(
        select(
            placed_day,
            func.count(),
            func.coalesce(func.sum(Order.total).filter(paid), 0),
        )
        .where(Order.store_id == store_id, _in_window(Order.placed_at, start, end))
        .group_by(placed_day)
    ).all():
        row = bucket(day)
        row.orders_placed = int(placed)
        row.gmv = Decimal(gmv)

    for day, units in db.execute(
        select(placed_day, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.store_id == store_id,
            OrderItem.store_id == store_id,
            _in_window(Order.placed_at, start, end),
            counts_as_sale(),
        )
        .group_by(placed_day)
    ).all():
        bucket(day).units = int(units)

    shipped_day = _local_day(Order.shipped_at, timezone)
    for day, on_time, late in db.execute(
        select(
            shipped_day,
            func.count().filter(Order.shipped_at <= Order.ship_by),
            func.count().filter(Order.shipped_at > Order.ship_by),
        )
        .where(
            Order.store_id == store_id,
            Order.ship_by.is_not(None),
            _in_window(Order.shipped_at, start, end),
        )
        .group_by(shipped_day)
    ).all():
        row = bucket(day)
        row.shipped_on_time = int(on_time)
        row.shipped_late = int(late)

    e = OperationalException
    detected_day = _local_day(e.first_detected_at, timezone)
    for day, count in db.execute(
        select(detected_day, func.count())
        .where(e.store_id == store_id, _in_window(e.first_detected_at, start, end))
        .group_by(detected_day)
    ).all():
        bucket(day).exceptions_detected = int(count)

    resolved_day = _local_day(e.resolved_at, timezone)
    for day, count in db.execute(
        select(resolved_day, func.count())
        .where(
            e.store_id == store_id,
            e.status == ExceptionStatus.RESOLVED,
            e.resolution_code.in_(COUNTED_RESOLUTION_CODES),
            _in_window(e.resolved_at, start, end),
        )
        .group_by(resolved_day)
    ).all():
        bucket(day).exceptions_resolved = int(count)

    return series
