"""Orders with three independent status axes (STATE_MACHINES.md §1)."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    READY_TO_SHIP = "READY_TO_SHIP"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class FulfillmentStatus(StrEnum):
    UNFULFILLED = "UNFULFILLED"
    IN_PROGRESS = "IN_PROGRESS"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"


class SalesChannel(StrEnum):
    WEB = "WEB"
    MARKETPLACE = "MARKETPLACE"
    POS = "POS"
    OTHER = "OTHER"


class ShipBySource(StrEnum):
    IMPORTED = "IMPORTED"
    STORE_SLA = "STORE_SLA"


class ChangeSource(StrEnum):
    IMPORT = "IMPORT"
    USER = "USER"
    SYSTEM = "SYSTEM"


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_order"
    __table_args__ = (
        UniqueConstraint("store_id", "order_number"),
        Index("ix_sales_order_store_status", "store_id", "status"),
        Index("ix_sales_order_store_placed", "store_id", "placed_at"),
        CheckConstraint(
            "subtotal >= 0 AND discount_total >= 0 AND shipping_total >= 0 "
            "AND tax_total >= 0 AND total >= 0",
            name="amounts_non_negative",
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    order_number: Mapped[str] = mapped_column(String(64))
    channel: Mapped[SalesChannel] = mapped_column(str_enum(SalesChannel, length=16))
    customer_ref: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus, length=24))
    payment_status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus, length=16))
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        str_enum(FulfillmentStatus, length=16)
    )

    placed_at: Mapped[datetime]
    paid_at: Mapped[datetime | None]
    ship_by: Mapped[datetime | None]
    ship_by_source: Mapped[ShipBySource | None] = mapped_column(str_enum(ShipBySource, length=16))
    shipped_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]

    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal]
    discount_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    shipping_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    total: Mapped[Decimal]

    carrier: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    last_import_id: Mapped[uuid.UUID | None]

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", order_by="OrderItem.line_number", cascade="all, delete-orphan"
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_item"
    __table_args__ = (
        UniqueConstraint("order_id", "line_number"),
        Index("ix_order_item_store_product", "store_id", "product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("unit_price >= 0 AND line_discount >= 0", name="amounts_non_negative"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product.id", ondelete="RESTRICT"))
    sku: Mapped[str] = mapped_column(String(64))
    line_number: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal]
    line_discount: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price - self.line_discount


class OrderEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable status history of an order."""

    __tablename__ = "order_event"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_order.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    from_status: Mapped[OrderStatus | None] = mapped_column(
        str_enum(OrderStatus, length=24, name="from_status")
    )
    to_status: Mapped[OrderStatus] = mapped_column(
        str_enum(OrderStatus, length=24, name="to_status")
    )
    skipped_statuses: Mapped[list[str]] = mapped_column(JSONB, default=list)
    payment_status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus, length=16))
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        str_enum(FulfillmentStatus, length=16)
    )
    source: Mapped[ChangeSource] = mapped_column(str_enum(ChangeSource, length=16))
    import_id: Mapped[uuid.UUID | None]
    actor_user_id: Mapped[uuid.UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
