"""CSV import records and row-level issues (IMPORT_PIPELINE.md, STATE_MACHINES.md §4)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ImportType(StrEnum):
    PRODUCTS = "products"
    ORDERS = "orders"
    ORDER_ITEMS = "order_items"
    INVENTORY_ADJUSTMENTS = "inventory_adjustments"


class ImportStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    APPLYING = "APPLYING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    DISCARDED = "DISCARDED"


class ImportMode(StrEnum):
    STRICT = "STRICT"
    VALID_ROWS_ONLY = "VALID_ROWS_ONLY"


class IssueSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class DataImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_import"
    __table_args__ = (Index("ix_data_import_store_created", "store_id", "created_at"),)

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    import_type: Mapped[ImportType] = mapped_column(str_enum(ImportType, length=32))
    status: Mapped[ImportStatus] = mapped_column(str_enum(ImportStatus, length=24))
    mode: Mapped[ImportMode | None] = mapped_column(str_enum(ImportMode, length=16))
    original_filename: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    row_count: Mapped[int | None] = mapped_column(Integer)
    # Raw bytes are kept only between validation and apply, then purged (set to NULL).
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    validated_at: Mapped[datetime | None]
    applied_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    evaluation_run_id: Mapped[uuid.UUID | None]
    failure_reason: Mapped[str | None] = mapped_column(String(500))


class ImportRowIssue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "import_row_issue"
    __table_args__ = (Index("ix_import_row_issue_import_row", "import_id", "row_number"),)

    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_import.id", ondelete="CASCADE"))
    row_number: Mapped[int | None] = mapped_column(Integer)  # None = file-level issue
    column: Mapped[str | None] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[IssueSeverity] = mapped_column(str_enum(IssueSeverity, length=16))
    message: Mapped[str] = mapped_column(String(500))
    raw_value: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
