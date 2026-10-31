"""Response schemas for order reads (STATE_MACHINES.md §1, BR-201..206)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.exceptions.models import (
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.inventory.models import ReservationStatus
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
    ShipBySource,
)

OrderSort = Literal[
    "-placed_at",
    "placed_at",
    "-total",
    "total",
    "ship_by",
    "-ship_by",
    "order_number",
    "-order_number",
]


class OrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    channel: SalesChannel
    customer_ref: str | None
    status: OrderStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    placed_at: datetime
    paid_at: datetime | None
    ship_by: datetime | None
    ship_by_source: ShipBySource | None
    shipped_at: datetime | None
    currency: str
    total: Decimal
    line_count: int
    is_overdue: bool = Field(description="BR-202 evaluated at the request time.")


class OrderAmounts(BaseModel):
    """Recorded amounts and the BR-205 reconciliation."""

    currency: str
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    lines_total: Decimal = Field(description="Σ (quantity × unit_price − line_discount).")
    expected_total: Decimal | None = Field(
        description="lines_total − discount_total + shipping_total + tax_total; null without lines."
    )
    difference: Decimal | None = Field(description="total − expected_total.")
    has_total_mismatch: bool = Field(description="|difference| > 0.01 and at least one line.")


class ReservationRef(BaseModel):
    status: ReservationStatus
    quantity: int


class OrderLineOut(BaseModel):
    id: uuid.UUID
    line_number: int
    product_id: uuid.UUID
    sku: str = Field(description="SKU as imported on the line.")
    product_sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_discount: Decimal
    line_total: Decimal
    reservation: ReservationRef | None


class OrderEventOut(BaseModel):
    id: uuid.UUID
    from_status: OrderStatus | None
    to_status: OrderStatus
    skipped_statuses: list[str]
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    source: ChangeSource
    import_id: uuid.UUID | None
    import_filename: str | None = Field(
        description="original_filename of the import that made the change, if any."
    )
    actor_user_id: uuid.UUID | None
    occurred_at: datetime


class LinkedException(BaseModel):
    id: uuid.UUID
    reference: str
    title: str
    exception_type: ExceptionType
    severity: Severity
    status: ExceptionStatus
    priority_band: PriorityBand
    link_role: LinkRole
    is_active: bool
    resolution_code: ResolutionCode | None = Field(
        description="RESOLVED only. With verified_at it decides how the resolution is shown."
    )
    verified_at: datetime | None


class OrderDetail(BaseModel):
    id: uuid.UUID
    order_number: str
    channel: SalesChannel
    customer_ref: str | None
    status: OrderStatus
    payment_status: PaymentStatus
    fulfillment_status: FulfillmentStatus
    placed_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    ship_by: datetime | None
    ship_by_source: ShipBySource | None = Field(
        description="IMPORTED (from the source system) or STORE_SLA (paid_at + SLA), BR-201."
    )
    is_overdue: bool = Field(description="BR-202 evaluated at the request time.")
    hours_overdue: Decimal | None
    carrier: str | None
    tracking_number: str | None
    amounts: OrderAmounts
    lines: list[OrderLineOut]
    events: list[OrderEventOut] = Field(description="Status history, oldest first.")
    exceptions: list[LinkedException] = Field(description="Active first, then newest first.")
    last_import_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
