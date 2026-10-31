"""Operational exceptions, history and evaluation runs (EXCEPTION_CATALOG, STATE_MACHINES §3)."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ExceptionType(StrEnum):
    INVENTORY_OVERSOLD = "INVENTORY_OVERSOLD"
    INVENTORY_OVERSELL_RISK = "INVENTORY_OVERSELL_RISK"
    INVENTORY_OUT_OF_STOCK = "INVENTORY_OUT_OF_STOCK"
    INVENTORY_BELOW_REORDER_POINT = "INVENTORY_BELOW_REORDER_POINT"
    ORDER_FULFILLMENT_OVERDUE = "ORDER_FULFILLMENT_OVERDUE"
    ORDER_STALLED_AFTER_PAYMENT = "ORDER_STALLED_AFTER_PAYMENT"
    ORDER_REFUND_PENDING = "ORDER_REFUND_PENDING"
    DATA_ORDER_TOTAL_MISMATCH = "DATA_ORDER_TOTAL_MISMATCH"
    DATA_NEGATIVE_ON_HAND = "DATA_NEGATIVE_ON_HAND"


class ExceptionCategory(StrEnum):
    INVENTORY = "INVENTORY"
    FULFILLMENT = "FULFILLMENT"
    PAYMENT = "PAYMENT"
    DATA_QUALITY = "DATA_QUALITY"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    REOPENED = "REOPENED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


ACTIVE_STATUSES = frozenset(
    {
        ExceptionStatus.OPEN,
        ExceptionStatus.ACKNOWLEDGED,
        ExceptionStatus.IN_PROGRESS,
        ExceptionStatus.REOPENED,
    }
)


class PriorityBand(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ResolutionCode(StrEnum):
    STOCK_REPLENISHED = "STOCK_REPLENISHED"
    ORDER_FULFILLED = "ORDER_FULFILLED"
    REFUND_ISSUED = "REFUND_ISSUED"
    DATA_CORRECTED = "DATA_CORRECTED"
    CUSTOMER_CONTACTED = "CUSTOMER_CONTACTED"
    FIXED_IN_SOURCE_SYSTEM = "FIXED_IN_SOURCE_SYSTEM"
    OTHER = "OTHER"
    # System-only codes
    CONDITION_CLEARED = "CONDITION_CLEARED"
    SUPERSEDED = "SUPERSEDED"


MANUAL_RESOLUTION_CODES = frozenset(ResolutionCode) - {
    ResolutionCode.CONDITION_CLEARED,
    ResolutionCode.SUPERSEDED,
}


class DismissalReason(StrEnum):
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    DUPLICATE = "DUPLICATE"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class EntityType(StrEnum):
    PRODUCT = "product"
    ORDER = "order"


class LinkRole(StrEnum):
    PRIMARY = "PRIMARY"
    AFFECTED = "AFFECTED"


class ExceptionEventType(StrEnum):
    DETECTED = "DETECTED"
    EVIDENCE_UPDATED = "EVIDENCE_UPDATED"
    SEVERITY_CHANGED = "SEVERITY_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    UNASSIGNED = "UNASSIGNED"
    NOTE_ADDED = "NOTE_ADDED"
    DUE_DATE_CHANGED = "DUE_DATE_CHANGED"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    VERIFIED = "VERIFIED"
    REOPENED = "REOPENED"
    SUPERSEDED = "SUPERSEDED"


class EvaluationTrigger(StrEnum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    SCHEDULED = "SCHEDULED"


class EvaluationStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class NoteSource(StrEnum):
    USER = "USER"
    AI_DRAFT_ACCEPTED = "AI_DRAFT_ACCEPTED"


class EvaluationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evaluation_run"
    __table_args__ = (Index("ix_evaluation_run_store_started", "store_id", "started_at"),)

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    trigger: Mapped[EvaluationTrigger] = mapped_column(str_enum(EvaluationTrigger, length=16))
    status: Mapped[EvaluationStatus] = mapped_column(str_enum(EvaluationStatus, length=16))
    as_of: Mapped[datetime]
    rules: Mapped[list[str]] = mapped_column(JSONB, default=list)
    counts: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    import_id: Mapped[uuid.UUID | None]
    error: Mapped[str | None] = mapped_column(String(500))


class OperationalException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_exception"
    __table_args__ = (
        # At most one active exception per detected condition (invariant 5).
        Index(
            "uq_operational_exception_active_dedup",
            "store_id",
            "dedup_key",
            unique=True,
            postgresql_where=text("status IN ('OPEN','ACKNOWLEDGED','IN_PROGRESS','REOPENED')"),
        ),
        Index("ix_operational_exception_store_status", "store_id", "status"),
        Index("ix_operational_exception_store_priority", "store_id", "priority_score"),
        Index("ix_operational_exception_dedup", "store_id", "dedup_key", "first_detected_at"),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    reference: Mapped[str] = mapped_column(String(16))  # human-friendly id, e.g. EXC-1042
    exception_type: Mapped[ExceptionType] = mapped_column(str_enum(ExceptionType, length=40))
    category: Mapped[ExceptionCategory] = mapped_column(str_enum(ExceptionCategory, length=16))
    rule_id: Mapped[str] = mapped_column(String(40))
    dedup_key: Mapped[str] = mapped_column(String(120))
    primary_entity_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, length=16))
    primary_entity_id: Mapped[uuid.UUID]

    status: Mapped[ExceptionStatus] = mapped_column(str_enum(ExceptionStatus, length=16))
    severity: Mapped[Severity] = mapped_column(str_enum(Severity, length=16))
    priority_score: Mapped[int] = mapped_column(Integer)
    priority_band: Mapped[PriorityBand] = mapped_column(str_enum(PriorityBand, length=4))
    priority_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    title: Mapped[str] = mapped_column(String(200))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    recommended_action: Mapped[str] = mapped_column(String(500))
    exposure_amount: Mapped[Decimal] = mapped_column(default=Decimal("0"))
    affected_order_count: Mapped[int] = mapped_column(Integer, default=0)
    deadline_at: Mapped[datetime | None]
    due_at: Mapped[datetime]
    due_at_overridden: Mapped[bool] = mapped_column(default=False)

    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    first_detected_at: Mapped[datetime]
    last_detected_at: Mapped[datetime]
    detection_count: Mapped[int] = mapped_column(Integer, default=1)

    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    resolution_actor: Mapped[ActorType | None] = mapped_column(str_enum(ActorType, length=16))
    resolution_code: Mapped[ResolutionCode | None] = mapped_column(
        str_enum(ResolutionCode, length=32)
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None]
    dismissed_reason: Mapped[DismissalReason | None] = mapped_column(
        str_enum(DismissalReason, length=24)
    )
    condition_cleared_at: Mapped[datetime | None]
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="SET NULL")
    )
    previous_occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="SET NULL")
    )
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class ExceptionEntityLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exception_entity_link"
    __table_args__ = (
        UniqueConstraint("exception_id", "entity_type", "entity_id"),
        Index("ix_exception_entity_link_entity", "store_id", "entity_type", "entity_id"),
    )

    exception_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="CASCADE")
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    entity_type: Mapped[EntityType] = mapped_column(str_enum(EntityType, length=16))
    entity_id: Mapped[uuid.UUID]
    role: Mapped[LinkRole] = mapped_column(str_enum(LinkRole, length=16))


class ExceptionEvent(UUIDPrimaryKeyMixin, Base):
    """Immutable exception history. No update or delete path exists in code."""

    __tablename__ = "exception_event"
    __table_args__ = (Index("ix_exception_event_exception_time", "exception_id", "occurred_at"),)

    exception_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="CASCADE")
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    event_type: Mapped[ExceptionEventType] = mapped_column(str_enum(ExceptionEventType, length=24))
    actor_type: Mapped[ActorType] = mapped_column(str_enum(ActorType, length=16))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    evaluation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_run.id", ondelete="SET NULL")
    )
    from_status: Mapped[ExceptionStatus | None] = mapped_column(
        str_enum(ExceptionStatus, length=16, name="from_status")
    )
    to_status: Mapped[ExceptionStatus | None] = mapped_column(
        str_enum(ExceptionStatus, length=16, name="to_status")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime]


class ExceptionAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exception_assignment"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="CASCADE"), index=True
    )
    assignee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime]
    unassigned_at: Mapped[datetime | None]


class ExceptionNote(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exception_note"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("operational_exception.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)
    source: Mapped[NoteSource] = mapped_column(str_enum(NoteSource, length=24))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ExceptionSequence(Base):
    """Per-store counter for human-friendly exception references (EXC-1001, EXC-1002, ...)."""

    __tablename__ = "exception_sequence"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store.id", ondelete="CASCADE"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(Integer, default=1001)
