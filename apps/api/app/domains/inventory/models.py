"""Inventory ledger, cached balances and stock reservations (BUSINESS_RULES.md §2)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class MovementType(StrEnum):
    CYCLE_COUNT = "CYCLE_COUNT"
    RECEIPT = "RECEIPT"
    INCOMING_EXPECTED = "INCOMING_EXPECTED"
    INCOMING_CANCELLED = "INCOMING_CANCELLED"
    DAMAGE = "DAMAGE"
    SHRINKAGE = "SHRINKAGE"
    RETURN_RESTOCK = "RETURN_RESTOCK"
    CORRECTION = "CORRECTION"
    SHIPMENT = "SHIPMENT"


class MovementSource(StrEnum):
    IMPORT = "IMPORT"
    ORDER = "ORDER"
    SYSTEM = "SYSTEM"


class ReservationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"


class InventoryBalance(TimestampMixin, Base):
    """Cached projection of the ledger and reservations (BR-104). ``available`` is computed."""

    __tablename__ = "inventory_balance"
    __table_args__ = (
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("incoming >= 0", name="incoming_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), primary_key=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store.id", ondelete="CASCADE"), index=True
    )
    # on_hand may go negative; that is reported as DATA_NEGATIVE_ON_HAND, never clamped.
    on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    incoming: Mapped[int] = mapped_column(Integer, default=0)
    incoming_eta: Mapped[datetime | None]
    last_cycle_count_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}

    @property
    def available(self) -> int:
        """BR-101: available = on_hand − reserved."""
        return self.on_hand - self.reserved


class InventoryMovement(UUIDPrimaryKeyMixin, Base):
    """Append-only ledger row (BR-110). No update or delete path exists."""

    __tablename__ = "inventory_movement"
    __table_args__ = (
        Index("ix_inventory_movement_product_time", "store_id", "product_id", "recorded_at"),
        Index(
            "uq_inventory_movement_store_reference",
            "store_id",
            "reference",
            unique=True,
            postgresql_where=text("reference IS NOT NULL"),
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"))
    movement_type: Mapped[MovementType] = mapped_column(str_enum(MovementType, length=24))
    on_hand_delta: Mapped[int] = mapped_column(Integer, default=0)
    incoming_delta: Mapped[int] = mapped_column(Integer, default=0)
    on_hand_after: Mapped[int] = mapped_column(Integer)
    incoming_after: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    source: Mapped[MovementSource] = mapped_column(str_enum(MovementSource, length=16))
    reference: Mapped[str | None] = mapped_column(String(120))
    import_id: Mapped[uuid.UUID | None]
    note: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None]


class StockReservation(UUIDPrimaryKeyMixin, Base):
    """One reservation per order line (BR-120..123)."""

    __tablename__ = "stock_reservation"
    __table_args__ = (
        Index("ix_stock_reservation_product_status", "store_id", "product_id", "status"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="CASCADE"))
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order.id", ondelete="CASCADE"), index=True
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_item.id", ondelete="CASCADE"), unique=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[ReservationStatus] = mapped_column(str_enum(ReservationStatus, length=16))
    activated_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
