"""Response schemas for read-only analytics (T-057).

Every aggregate carries ``as_of`` and the window it covers. Rates are always returned together with
their numerator and denominator, never as a bare percentage.
"""

import datetime as dt
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domains.exceptions.models import (
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionCategory,
    ExceptionStatus,
    ExceptionType,
    PriorityBand,
    Severity,
)
from app.domains.imports.models import ImportStatus, ImportType


class TimeWindow(BaseModel):
    """Half-open window ``[start, end)`` in UTC. ``start`` is midnight in the store time zone."""

    start: datetime
    end: datetime
    days: int = Field(description="Number of store-local calendar days; the last one is partial.")
    timezone: str


class ImportFreshness(BaseModel):
    import_type: ImportType
    import_id: uuid.UUID | None
    status: ImportStatus | None
    applied_at: datetime | None = Field(
        description="Latest applied_at of a COMPLETED or COMPLETED_WITH_ERRORS import (M-05)."
    )


class EvaluationRunFreshness(BaseModel):
    id: uuid.UUID
    trigger: EvaluationTrigger
    status: EvaluationStatus
    as_of: datetime
    started_at: datetime
    finished_at: datetime | None


class DataFreshness(BaseModel):
    imports: list[ImportFreshness] = Field(description="One entry per import type.")
    last_evaluation_run: EvaluationRunFreshness | None = Field(
        description="The most recently started evaluation run, whatever its status."
    )


class ActiveExceptionSummary(BaseModel):
    total: int
    by_severity: dict[Severity, int]
    by_band: dict[PriorityBand, int]
    by_category: dict[ExceptionCategory, int]
    exposure_by_category: dict[ExceptionCategory, Decimal] = Field(
        description=(
            "Σ exposure_amount of active exceptions per category: gross order-line value at risk "
            "(BR-404), not loss. Not additive across categories, because one order can count in "
            "several exceptions, so no total is provided."
        )
    )
    unassigned: int
    past_due: int = Field(description="Active exceptions with due_at < as_of.")
    reopened: int = Field(description="Active exceptions currently in REOPENED.")


class AttentionItem(BaseModel):
    id: uuid.UUID
    reference: str
    title: str
    exception_type: ExceptionType
    category: ExceptionCategory
    severity: Severity
    status: ExceptionStatus
    priority_band: PriorityBand
    priority_score: int
    due_at: datetime
    is_past_due: bool
    assignee_id: uuid.UUID | None
    assignee_name: str | None


class OrderHealthSummary(BaseModel):
    overdue_count: int = Field(description="BR-202 at as_of: committed status and ship_by < as_of.")
    overdue_value: Decimal = Field(description="Σ total of the overdue orders (gross).")
    awaiting_shipment: int = Field(description="Orders in PAID, PROCESSING or READY_TO_SHIP.")


class InventoryHealthSummary(BaseModel):
    """ACTIVE products by health from current balances (§2.5), not from exceptions."""

    active_products: int
    oversold: int
    out_of_stock: int
    below_reorder_point: int
    approaching_reorder_point: int
    healthy: int


class SalesSummary(BaseModel):
    window: TimeWindow
    orders_placed: int = Field(description="Orders with placed_at in the window, any status.")
    paid_orders: int = Field(description="The GMV population: placed in the window and paid.")
    gmv: Decimal = Field(description="Σ total of paid_orders (gross; refunds not subtracted).")


class OnTimeShipment(BaseModel):
    window: TimeWindow
    shipped_with_deadline: int = Field(description="Denominator: shipped in window with ship_by.")
    on_time: int = Field(description="Numerator: shipped_at ≤ ship_by.")
    late: int
    shipped_without_deadline: int = Field(description="Shipped in window without ship_by.")
    on_time_rate_pct: Decimal | None = Field(
        description="100 × on_time / shipped_with_deadline, 1 dp; null when the denominator is 0."
    )


class DashboardOut(BaseModel):
    as_of: datetime
    timezone: str
    currency: str
    active_exceptions: ActiveExceptionSummary
    attention: list[AttentionItem] = Field(description="Top 8 active exceptions by priority.")
    orders: OrderHealthSummary
    inventory: InventoryHealthSummary
    sales_today: SalesSummary
    sales_last_7_days: SalesSummary
    on_time_shipment_30_days: OnTimeShipment
    data_freshness: DataFreshness


class TrendMetrics(BaseModel):
    orders_placed: int
    units: int = Field(description="Units on lines of orders placed (BR-150 status filter).")
    gmv: Decimal
    exceptions_detected: int = Field(description="Exceptions with first_detected_at in the day.")
    exceptions_resolved: int = Field(
        description="RESOLVED exceptions (excluding SUPERSEDED) with resolved_at in the day."
    )
    shipped_on_time: int
    shipped_late: int


class TrendDay(TrendMetrics):
    date: dt.date


class TrendsOut(BaseModel):
    as_of: datetime
    window: TimeWindow
    currency: str
    partial_last_day: bool = True
    days: list[TrendDay]
    totals: TrendMetrics


class ExceptionTypeBreakdown(BaseModel):
    exception_type: ExceptionType
    category: ExceptionCategory
    active: int = Field(description="Active right now (snapshot, not windowed).")
    detected_in_window: int
    resolved_in_window: int = Field(description="Manual + automatic; SUPERSEDED excluded.")
    resolved_manually: int
    auto_resolved: int
    superseded_in_window: int
    median_hours_to_resolve_manual: Decimal | None = Field(
        description="Median of resolved_at − first_detected_at, manual resolution codes (M-10)."
    )
    median_hours_to_resolve_auto: Decimal | None = Field(
        description="Median of resolved_at − first_detected_at, CONDITION_CLEARED (M-10)."
    )
    reopened_in_window: int = Field(description="REOPENED events in the window.")


class ExceptionBreakdownOut(BaseModel):
    as_of: datetime
    window: TimeWindow
    items: list[ExceptionTypeBreakdown]
