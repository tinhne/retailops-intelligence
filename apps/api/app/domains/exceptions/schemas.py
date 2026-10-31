"""Request and response schemas for the exceptions API."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field

from app.domains.exceptions.lifecycle import (
    CLOSING_NOTE_MIN_CHARS,
    NOTE_MAX_CHARS,
    ExceptionAction,
    non_whitespace_length,
)
from app.domains.exceptions.models import (
    ActorType,
    DismissalReason,
    EntityType,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionCategory,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    NoteSource,
    PriorityBand,
    ResolutionCode,
    Severity,
)


class ManualResolutionCode(StrEnum):
    """Resolution codes a person may choose (STATE_MACHINES.md §3.2)."""

    STOCK_REPLENISHED = ResolutionCode.STOCK_REPLENISHED.value
    ORDER_FULFILLED = ResolutionCode.ORDER_FULFILLED.value
    REFUND_ISSUED = ResolutionCode.REFUND_ISSUED.value
    DATA_CORRECTED = ResolutionCode.DATA_CORRECTED.value
    CUSTOMER_CONTACTED = ResolutionCode.CUSTOMER_CONTACTED.value
    FIXED_IN_SOURCE_SYSTEM = ResolutionCode.FIXED_IN_SOURCE_SYSTEM.value
    OTHER = ResolutionCode.OTHER.value


def _closing_note(value: str) -> str:
    text = value.strip()
    if non_whitespace_length(text) < CLOSING_NOTE_MIN_CHARS:
        raise ValueError(
            f"must contain at least {CLOSING_NOTE_MIN_CHARS} non-whitespace characters"
        )
    return text


def _required_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


ClosingNote = Annotated[str, Field(max_length=NOTE_MAX_CHARS), AfterValidator(_closing_note)]
RequiredText = Annotated[str, Field(max_length=NOTE_MAX_CHARS), AfterValidator(_required_text)]


# --- shared output pieces ------------------------------------------------------------------------


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


class EntityRefOut(BaseModel):
    type: EntityType
    id: uuid.UUID
    label: str  # SKU for a product, order number for an order
    name: str | None = None  # product name


class ExceptionRef(BaseModel):
    id: uuid.UUID
    reference: str
    exception_type: ExceptionType
    status: ExceptionStatus
    title: str


class EntityLinkOut(BaseModel):
    entity_type: EntityType
    entity_id: uuid.UUID
    role: LinkRole
    label: str
    name: str | None = None


class ResolutionOut(BaseModel):
    resolved_at: datetime | None
    resolved_by: UserRef | None
    resolution_actor: ActorType | None
    resolution_code: ResolutionCode | None
    resolution_note: str | None
    verified_at: datetime | None


class DismissalOut(BaseModel):
    dismissed_reason: DismissalReason | None
    note: str | None
    dismissed_at: datetime | None
    dismissed_by: UserRef | None
    condition_cleared_at: datetime | None


class BlockedActionOut(BaseModel):
    action: ExceptionAction
    code: str
    reason: str


# --- exceptions ---------------------------------------------------------------------------------


class ExceptionListItem(BaseModel):
    id: uuid.UUID
    reference: str
    exception_type: ExceptionType
    category: ExceptionCategory
    status: ExceptionStatus
    severity: Severity
    priority_score: int
    priority_band: PriorityBand
    title: str
    primary_entity: EntityRefOut
    assignee: UserRef | None
    exposure_amount: Decimal = Field(description="Gross order-line value at risk (BR-404)")
    affected_order_count: int
    deadline_at: datetime | None
    due_at: datetime
    due_at_overridden: bool
    is_past_due: bool
    first_detected_at: datetime
    last_detected_at: datetime
    detection_count: int
    age_hours: int
    reopen_count: int
    version: int
    resolution_code: ResolutionCode | None = Field(
        description="RESOLVED only. With verified_at it decides the four resolved forms."
    )
    verified_at: datetime | None = Field(
        description="Set when the next evaluation confirms a manual resolution."
    )
    dismissed_reason: DismissalReason | None
    closed_at: datetime | None = Field(
        description="When it was resolved or dismissed; null while active or reopened."
    )


class ExceptionDetail(ExceptionListItem):
    rule_id: str
    dedup_key: str
    priority_breakdown: dict[str, Any]
    evidence: dict[str, Any]
    calculation: dict[str, Any]
    recommended_action: str
    links: list[EntityLinkOut]
    resolution: ResolutionOut | None
    dismissal: DismissalOut | None
    superseded_by: ExceptionRef | None
    supersedes: list[ExceptionRef]
    previous_occurrence: ExceptionRef | None
    available_actions: list[ExceptionAction]
    blocked_actions: list[BlockedActionOut]
    created_at: datetime
    updated_at: datetime


class ExceptionEventOut(BaseModel):
    id: uuid.UUID
    event_type: ExceptionEventType
    actor_type: ActorType
    actor: UserRef | None
    evaluation_run_id: uuid.UUID | None
    from_status: ExceptionStatus | None
    to_status: ExceptionStatus | None
    payload: dict[str, Any]
    occurred_at: datetime


class ExceptionNoteOut(BaseModel):
    id: uuid.UUID
    body: str
    source: NoteSource
    author: UserRef | None
    created_at: datetime


# --- requests -----------------------------------------------------------------------------------


class VersionedRequest(BaseModel):
    expected_version: int | None = Field(
        default=None, ge=1, description="Optimistic concurrency: 409 STALE_VERSION on mismatch"
    )


class ResolveRequest(VersionedRequest):
    resolution_code: ManualResolutionCode
    resolution_note: ClosingNote


class DismissRequest(VersionedRequest):
    dismissal_reason: DismissalReason
    note: ClosingNote


class ReopenRequest(VersionedRequest):
    reason: RequiredText = Field(description="Why the exception is reopened")


class NoteCreate(VersionedRequest):
    body: RequiredText


class AssignRequest(VersionedRequest):
    assignee_id: uuid.UUID | None = Field(description="null unassigns")


class DueDateRequest(VersionedRequest):
    due_at: AwareDatetime
    note: str | None = Field(default=None, max_length=NOTE_MAX_CHARS)


# --- evaluation runs ----------------------------------------------------------------------------


class EvaluationCreate(BaseModel):
    rule_ids: list[str] | None = Field(
        default=None, max_length=20, description="Rule ids such as INV-OVERSOLD@1; all if omitted"
    )


class EvaluationRunOut(BaseModel):
    id: uuid.UUID
    trigger: EvaluationTrigger
    status: EvaluationStatus
    as_of: datetime
    rules: list[str]
    counts: dict[str, int]
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    triggered_by: UserRef | None
    import_id: uuid.UUID | None
    error: str | None
