"""Response schemas for inventory reads (BUSINESS_RULES.md §2)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.catalog.models import ProductStatus
from app.domains.inventory.calculations import StockHealth
from app.domains.inventory.models import MovementSource, MovementType

PositionSort = Literal["available", "-available", "days_of_cover", "-days_of_cover", "sku", "-sku"]
MovementSort = Literal["-recorded_at", "recorded_at", "-occurred_at", "occurred_at"]

HEALTH_DESCRIPTION = (
    "§2.5. DATA_ISSUE when on_hand < 0, whatever the product status: the stock figure is invalid, "
    "so no availability class applies (BR-402a). Otherwise null for products that are not ACTIVE."
)


class InventoryPositionOut(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    category: str | None
    status: ProductStatus
    on_hand: int
    reserved: int
    available: int = Field(description="BR-101: on_hand − reserved. May be negative (BR-102).")
    incoming: int = Field(description="Never counted in available (BR-103).")
    incoming_eta: datetime | None
    reorder_point: int
    health: StockHealth | None = Field(description=HEALTH_DESCRIPTION)
    avg_daily_units: Decimal = Field(description="Estimate (BR-150, BR-152).")
    days_of_cover: Decimal | None = Field(
        description="Estimate (BR-151, BR-152); null means not enough sales history."
    )
    last_cycle_count_at: datetime | None


class MovementOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    product_name: str
    movement_type: MovementType
    on_hand_delta: int
    incoming_delta: int
    on_hand_after: int
    incoming_after: int
    occurred_at: datetime
    recorded_at: datetime
    source: MovementSource
    reference: str | None
    import_id: uuid.UUID | None
    import_filename: str | None = Field(description="original_filename of the import, if any.")
    order_id: uuid.UUID | None = Field(
        description="The order a SHIPMENT belongs to, from its order_item:{id} reference (BR-131)."
    )
    note: str | None
    created_by: uuid.UUID | None


class DriftOut(BaseModel):
    product_id: uuid.UUID
    sku: str | None
    field: str
    stored: int
    computed: int


class ReconciliationOut(BaseModel):
    """BR-104: cached balances compared with the ledger and reservations. Drift is a defect."""

    checked_at: datetime
    is_consistent: bool
    drift_count: int
    items: list[DriftOut]


class StockSnapshot(BaseModel):
    on_hand: int
    reserved: int
    available: int
    incoming: int
    incoming_eta: datetime | None
    last_cycle_count_at: datetime | None
