"""Read-only analytics: dashboard summary, daily trends and the exception breakdown (T-057).

Every number is computed from the tables at an explicit ``as_of`` (BR-504), so two calls with the
same data and ``as_of`` return the same result. Days are calendar days in the store time zone
(BR-501): a window of ``n`` days starts at local midnight ``n − 1`` days before ``as_of`` and ends
at ``as_of`` (the last day is partial). Windows are half-open, ``[start, as_of)``.

Definitions used throughout:

- **Orders placed**: orders whose ``placed_at`` falls in the window, whatever their status.
- **GMV** (gross merchandise value): Σ ``total`` of orders placed in the window that were paid,
  meaning ``paid_at`` is set and ``payment_status`` is ``PAID`` or ``REFUNDED``. Unpaid orders
  (``PENDING``, ``FAILED``, cancelled before payment) are excluded. Orders cancelled or refunded
  after payment are included: GMV is gross, refunds are not subtracted. Bucketed by ``placed_at``.
- **Units**: units on lines of orders placed in the window that count as sales under BR-150
  (``orders.sql.counts_as_sale``, BR-150), the same population as the velocity estimate.
- **On-time shipment**: among orders with ``shipped_at`` in the window and a ``ship_by``, on time
  when ``shipped_at ≤ ship_by`` (M-19). Orders without ``ship_by`` are reported separately.
- **Overdue orders**: BR-202 at ``as_of`` (committed status and ``ship_by < as_of``).
- **Exceptions detected**: exceptions whose ``first_detected_at`` is in the window. A recurrence
  after the reopen window is a new exception and counts again.
- **Exceptions resolved**: exceptions currently ``RESOLVED`` with ``resolved_at`` in the window,
  excluding ``SUPERSEDED`` (the work continues in the superseding exception). Manual means a
  manual resolution code, automatic means ``CONDITION_CLEARED`` (M-10).
- **Reopened**: ``REOPENED`` events in the window.
"""

import statistics
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.domains.analytics import queries
from app.domains.analytics.schemas import (
    ActiveExceptionSummary,
    AttentionItem,
    DashboardOut,
    DataFreshness,
    EvaluationRunFreshness,
    ExceptionBreakdownOut,
    ExceptionTypeBreakdown,
    ImportFreshness,
    InventoryHealthSummary,
    OnTimeShipment,
    OrderHealthSummary,
    SalesSummary,
    TimeWindow,
    TrendDay,
    TrendMetrics,
    TrendsOut,
)
from app.domains.exceptions.models import (
    MANUAL_RESOLUTION_CODES,
    ExceptionCategory,
    ExceptionType,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.imports.models import ImportType
from app.domains.inventory.calculations import StockHealth

ATTENTION_LIMIT = 8
CENT = Decimal("0.01")
TENTH = Decimal("0.1")

# EXCEPTION_CATALOG.md: the category of each exception type.
TYPE_CATEGORY: dict[ExceptionType, ExceptionCategory] = {
    ExceptionType.INVENTORY_OVERSOLD: ExceptionCategory.INVENTORY,
    ExceptionType.INVENTORY_OVERSELL_RISK: ExceptionCategory.INVENTORY,
    ExceptionType.INVENTORY_OUT_OF_STOCK: ExceptionCategory.INVENTORY,
    ExceptionType.INVENTORY_BELOW_REORDER_POINT: ExceptionCategory.INVENTORY,
    ExceptionType.ORDER_FULFILLMENT_OVERDUE: ExceptionCategory.FULFILLMENT,
    ExceptionType.ORDER_STALLED_AFTER_PAYMENT: ExceptionCategory.FULFILLMENT,
    ExceptionType.ORDER_REFUND_PENDING: ExceptionCategory.PAYMENT,
    ExceptionType.DATA_ORDER_TOTAL_MISMATCH: ExceptionCategory.DATA_QUALITY,
    ExceptionType.DATA_NEGATIVE_ON_HAND: ExceptionCategory.DATA_QUALITY,
}


# ---------------------------------------------------------------------------------------------
# Time windows
# ---------------------------------------------------------------------------------------------


def local_day_window(as_of: datetime, timezone: str, days: int) -> TimeWindow:
    """``days`` store-local calendar days ending with the (partial) day that contains ``as_of``."""
    zone = ZoneInfo(timezone)
    first_day = as_of.astimezone(zone).date() - timedelta(days=days - 1)
    start = datetime.combine(first_day, time(0), tzinfo=zone).astimezone(UTC)
    return TimeWindow(start=start, end=as_of, days=days, timezone=timezone)


def window_dates(window: TimeWindow) -> list[date]:
    zone = ZoneInfo(window.timezone)
    first = window.start.astimezone(zone).date()
    return [first + timedelta(days=i) for i in range(window.days)]


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _hours(start: datetime, end: datetime) -> Decimal:
    micros = (end - start) // timedelta(microseconds=1)
    return Decimal(micros) / Decimal(3_600_000_000)


def _median_hours(values: Iterable[Decimal]) -> Decimal | None:
    data = list(values)
    if not data:
        return None
    return Decimal(statistics.median(data)).quantize(TENTH, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------------------------
# Data freshness
# ---------------------------------------------------------------------------------------------


def data_freshness(db: Session, store_id: uuid.UUID) -> DataFreshness:
    """Latest applied import per type (M-05) and the most recently started evaluation run."""
    latest = queries.latest_applied_imports(db, store_id)
    imports = []
    for import_type in ImportType:
        item = latest.get(import_type)
        imports.append(
            ImportFreshness(
                import_type=import_type,
                import_id=item.import_id if item else None,
                status=item.status if item else None,
                applied_at=item.applied_at if item else None,
            )
        )
    run = queries.latest_evaluation_run(db, store_id)
    return DataFreshness(
        imports=imports,
        last_evaluation_run=(
            EvaluationRunFreshness(
                id=run.id,
                trigger=run.trigger,
                status=run.status,
                as_of=run.as_of,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            if run is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------------------------


def _active_summary(db: Session, store_id: uuid.UUID, as_of: datetime) -> ActiveExceptionSummary:
    by_severity = dict.fromkeys(Severity, 0)
    by_band = dict.fromkeys(PriorityBand, 0)
    by_category = dict.fromkeys(ExceptionCategory, 0)
    exposure_by_category = dict.fromkeys(ExceptionCategory, Decimal("0"))
    total = unassigned = past_due = reopened = 0
    for group in queries.active_exception_groups(db, store_id, as_of=as_of):
        total += group.count
        by_severity[group.severity] += group.count
        by_band[group.band] += group.count
        by_category[group.category] += group.count
        exposure_by_category[group.category] += group.exposure
        unassigned += group.count if group.unassigned else 0
        past_due += group.count if group.past_due else 0
        reopened += group.count if group.reopened else 0
    return ActiveExceptionSummary(
        total=total,
        by_severity=by_severity,
        by_band=by_band,
        by_category=by_category,
        exposure_by_category={
            category: _money(amount) for category, amount in exposure_by_category.items()
        },
        unassigned=unassigned,
        past_due=past_due,
        reopened=reopened,
    )


def _sales_summary(db: Session, store_id: uuid.UUID, window: TimeWindow) -> SalesSummary:
    counts = queries.sales(db, store_id, start=window.start, end=window.end)
    return SalesSummary(
        window=window,
        orders_placed=counts.orders_placed,
        paid_orders=counts.paid_orders,
        gmv=_money(counts.gmv),
    )


def on_time_shipment(db: Session, store_id: uuid.UUID, window: TimeWindow) -> OnTimeShipment:
    counts = queries.shipments(db, store_id, start=window.start, end=window.end)
    denominator = counts.on_time + counts.late
    rate = None
    if denominator:
        rate = (Decimal(100 * counts.on_time) / Decimal(denominator)).quantize(
            TENTH, rounding=ROUND_HALF_UP
        )
    return OnTimeShipment(
        window=window,
        shipped_with_deadline=denominator,
        on_time=counts.on_time,
        late=counts.late,
        shipped_without_deadline=counts.without_deadline,
        on_time_rate_pct=rate,
    )


def get_dashboard_summary(
    db: Session,
    store_id: uuid.UUID,
    *,
    timezone: str,
    currency: str,
    approaching_factor: Decimal,
    as_of: datetime,
) -> DashboardOut:
    """Operational overview at ``as_of``. Inventory counts come from current balances, not from
    exceptions, so they can be cross-checked against the inventory exceptions."""
    attention = [
        AttentionItem(
            id=exc.id,
            reference=exc.reference,
            title=exc.title,
            exception_type=exc.exception_type,
            category=exc.category,
            severity=exc.severity,
            status=exc.status,
            priority_band=exc.priority_band,
            priority_score=exc.priority_score,
            due_at=exc.due_at,
            is_past_due=exc.due_at < as_of,
            assignee_id=exc.assignee_id,
            assignee_name=assignee_name,
        )
        for exc, assignee_name in queries.attention_items(db, store_id, limit=ATTENTION_LIMIT)
    ]
    orders = queries.order_snapshot(db, store_id, as_of=as_of)
    health = queries.active_product_health_counts(db, store_id, factor=approaching_factor)
    return DashboardOut(
        as_of=as_of,
        timezone=timezone,
        currency=currency,
        active_exceptions=_active_summary(db, store_id, as_of),
        attention=attention,
        orders=OrderHealthSummary(
            overdue_count=orders.overdue_count,
            overdue_value=_money(orders.overdue_value),
            awaiting_shipment=orders.awaiting_shipment,
        ),
        inventory=InventoryHealthSummary(
            active_products=sum(health.values()),
            oversold=health.get(StockHealth.OVERSOLD.value, 0),
            out_of_stock=health.get(StockHealth.OUT_OF_STOCK.value, 0),
            below_reorder_point=health.get(StockHealth.BELOW_REORDER_POINT.value, 0),
            approaching_reorder_point=health.get(StockHealth.APPROACHING_REORDER_POINT.value, 0),
            healthy=health.get(StockHealth.HEALTHY.value, 0),
            data_issue=health.get(StockHealth.DATA_ISSUE.value, 0),
        ),
        sales_today=_sales_summary(db, store_id, local_day_window(as_of, timezone, 1)),
        sales_last_7_days=_sales_summary(db, store_id, local_day_window(as_of, timezone, 7)),
        on_time_shipment_30_days=on_time_shipment(
            db, store_id, local_day_window(as_of, timezone, 30)
        ),
        data_freshness=data_freshness(db, store_id),
    )


# ---------------------------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------------------------


def get_trends(
    db: Session,
    store_id: uuid.UUID,
    *,
    timezone: str,
    currency: str,
    days: int,
    as_of: datetime,
) -> TrendsOut:
    """One row per store-local day over the last ``days`` days, plus window totals."""
    window = local_day_window(as_of, timezone, days)
    dates = window_dates(window)
    series = queries.daily_series(
        db, store_id, timezone=timezone, start=window.start, end=window.end, days=dates
    )
    rows = [
        TrendDay(
            date=day,
            orders_placed=series[day].orders_placed,
            units=series[day].units,
            gmv=_money(series[day].gmv),
            exceptions_detected=series[day].exceptions_detected,
            exceptions_resolved=series[day].exceptions_resolved,
            shipped_on_time=series[day].shipped_on_time,
            shipped_late=series[day].shipped_late,
        )
        for day in dates
    ]
    totals = TrendMetrics(
        orders_placed=sum(r.orders_placed for r in rows),
        units=sum(r.units for r in rows),
        gmv=_money(sum((r.gmv for r in rows), Decimal("0"))),
        exceptions_detected=sum(r.exceptions_detected for r in rows),
        exceptions_resolved=sum(r.exceptions_resolved for r in rows),
        shipped_on_time=sum(r.shipped_on_time for r in rows),
        shipped_late=sum(r.shipped_late for r in rows),
    )
    return TrendsOut(as_of=as_of, window=window, currency=currency, days=rows, totals=totals)


# ---------------------------------------------------------------------------------------------
# Exception breakdown
# ---------------------------------------------------------------------------------------------


def get_exception_breakdown(
    db: Session, store_id: uuid.UUID, *, timezone: str, days: int, as_of: datetime
) -> ExceptionBreakdownOut:
    """Per exception type: active now, detected/resolved/reopened in the window, and median
    time to resolve split into manual and automatic resolutions (M-10)."""
    window = local_day_window(as_of, timezone, days)
    active = queries.active_by_type(db, store_id)
    detected = queries.detected_by_type(db, store_id, start=window.start, end=window.end)
    reopened = queries.reopened_by_type(db, store_id, start=window.start, end=window.end)
    resolved = queries.resolved_in_window(db, store_id, start=window.start, end=window.end)

    items = []
    for exception_type in ExceptionType:
        rows = [r for r in resolved if r.exception_type is exception_type]
        manual = [r for r in rows if r.resolution_code in MANUAL_RESOLUTION_CODES]
        auto = [r for r in rows if r.resolution_code is ResolutionCode.CONDITION_CLEARED]
        superseded = [r for r in rows if r.resolution_code is ResolutionCode.SUPERSEDED]
        items.append(
            ExceptionTypeBreakdown(
                exception_type=exception_type,
                category=TYPE_CATEGORY[exception_type],
                active=active.get(exception_type, 0),
                detected_in_window=detected.get(exception_type, 0),
                resolved_in_window=len(manual) + len(auto),
                resolved_manually=len(manual),
                auto_resolved=len(auto),
                superseded_in_window=len(superseded),
                median_hours_to_resolve_manual=_median_hours(
                    _hours(r.first_detected_at, r.resolved_at) for r in manual
                ),
                median_hours_to_resolve_auto=_median_hours(
                    _hours(r.first_detected_at, r.resolved_at) for r in auto
                ),
                reopened_in_window=reopened.get(exception_type, 0),
            )
        )
    return ExceptionBreakdownOut(as_of=as_of, window=window, items=items)
