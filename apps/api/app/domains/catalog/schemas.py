"""Response schemas for catalog reads: products, suppliers and categories."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domains.catalog.models import ProductStatus
from app.domains.inventory.calculations import StockHealth
from app.domains.inventory.schemas import HEALTH_DESCRIPTION, StockSnapshot

ProductSort = Literal[
    "sku", "-sku", "name", "-name", "updated_at", "-updated_at", "available", "-available"
]
SupplierSort = Literal["name", "-name", "lead_time_days", "-lead_time_days"]


class SupplierRef(BaseModel):
    id: uuid.UUID
    name: str


class ProductListItem(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    category: str | None
    status: ProductStatus
    unit_price: Decimal
    unit_cost: Decimal | None
    reorder_point: int
    reorder_quantity: int | None
    supplier: SupplierRef | None
    on_hand: int
    reserved: int
    available: int = Field(description="BR-101: on_hand − reserved.")
    health: StockHealth | None = Field(description=HEALTH_DESCRIPTION)
    updated_at: datetime


class SupplierDetail(BaseModel):
    id: uuid.UUID
    name: str
    lead_time_days: int | None


class Estimate(BaseModel):
    """A value that is an estimate, never a fact (BR-152). The UI and AI must label it so."""

    value: Decimal | None
    is_estimate: Literal[True] = True
    basis: str
    window_days: int
    note: str | None = None


class ProductDetail(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    category: str | None
    status: ProductStatus
    unit_price: Decimal
    unit_cost: Decimal | None
    reorder_point: int
    reorder_quantity: int | None
    created_at: datetime
    updated_at: datetime
    supplier: SupplierDetail | None
    stock: StockSnapshot
    health: StockHealth | None = Field(description=HEALTH_DESCRIPTION)
    approaching_threshold: int | None = Field(
        description="ceil(reorder_point × approaching_reorder_factor); null if reorder_point is 0."
    )
    avg_daily_units: Estimate
    days_of_cover: Estimate
    active_exception_count: int = Field(
        description="Active exceptions linked to the product as PRIMARY or AFFECTED entity."
    )


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    lead_time_days: int | None
    contact_ref: str | None
    product_count: int


class CategoryList(BaseModel):
    items: list[str]
