"""Product master data: suppliers and products (one row per sellable SKU)."""

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ARCHIVED = "ARCHIVED"


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier"
    __table_args__ = (
        UniqueConstraint("store_id", "name"),
        CheckConstraint("lead_time_days BETWEEN 0 AND 365", name="lead_time_range"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    contact_ref: Mapped[str | None] = mapped_column(String(200))


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("store_id", "sku"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="unit_cost_non_negative"),
        CheckConstraint("reorder_point >= 0", name="reorder_point_non_negative"),
        CheckConstraint(
            "reorder_quantity IS NULL OR reorder_quantity >= 0", name="reorder_qty_non_negative"
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ProductStatus] = mapped_column(str_enum(ProductStatus, length=16))
    unit_price: Mapped[Decimal]
    unit_cost: Mapped[Decimal | None]
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    reorder_quantity: Mapped[int | None] = mapped_column(Integer)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("supplier.id", ondelete="SET NULL"), index=True
    )

    supplier: Mapped[Supplier | None] = relationship()
