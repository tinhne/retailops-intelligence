"""Identity and tenancy tables: organization, store, settings, users, memberships, sessions."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum
from app.domains.identity.permissions import Role


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    stores: Mapped[list["Store"]] = relationship(back_populates="organization")


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "store"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))

    organization: Mapped[Organization] = relationship(back_populates="stores")
    settings: Mapped["StoreSettings"] = relationship(back_populates="store", uselist=False)


DEFAULT_PRIORITY_WEIGHTS: dict[str, Any] = {
    "severity": {"CRITICAL": 50, "HIGH": 35, "MEDIUM": 20, "LOW": 8},
    "affected_orders_per_order": 3,
    "affected_orders_cap": 15,
    "exposure_cap_points": 15,
    "deadline": {"overdue": 12, "within_24h": 8, "within_72h": 4},
    "age_points_per_day": 2,
    "age_cap": 8,
}


class StoreSettings(TimestampMixin, Base):
    """Per-store operational thresholds (BUSINESS_RULES.md §7)."""

    __tablename__ = "store_settings"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store.id", ondelete="CASCADE"), primary_key=True
    )
    fulfillment_sla_hours: Mapped[int] = mapped_column(Integer, default=48)
    stall_threshold_hours: Mapped[int] = mapped_column(Integer, default=12)
    refund_overdue_hours: Mapped[int] = mapped_column(Integer, default=24)
    approaching_reorder_factor: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), default=Decimal("1.25")
    )
    velocity_window_days: Mapped[int] = mapped_column(Integer, default=28)
    reopen_window_hours: Mapped[int] = mapped_column(Integer, default=72)
    exposure_cap: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("5000.00"))
    priority_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=lambda: dict(DEFAULT_PRIORITY_WEIGHTS)
    )
    evaluation_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)

    store: Mapped[Store] = relationship(back_populates="settings")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_user"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_login_at: Mapped[datetime | None]

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(str_enum(Role, length=16))

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship()


class UserSession(UUIDPrimaryKeyMixin, Base):
    """Server-side session. Only the SHA-256 of the opaque token is stored (ADR-0004)."""

    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_seen_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship()
