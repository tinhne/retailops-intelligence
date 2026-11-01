"""Tool framework: specifications, execution context, results and errors (TOOL_CATALOG.md §1).

A tool is a read-only function over one store. Its arguments are a Pydantic model that forbids
unknown fields and never contains ``store_id``, ``as_of`` or a user: those are injected by the
registry from the authenticated request and the turn (``ToolContext``). Each returned record
carries a ``ref`` (``type``, ``id``, ``label``) so the evidence ledger can verify what an answer
cites.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.domains.ai.models import ToolCallStatus
from app.domains.exceptions.rules.base import jsonable
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

RefType = Literal["exception", "order", "product", "import", "evaluation_run", "aggregate"]
REF_TYPES: frozenset[str] = frozenset(
    {"exception", "order", "product", "import", "evaluation_run", "aggregate"}
)
LOOKBACK_LIMIT = timedelta(days=90)  # lower bounds (``*_since``) within [as_of − 90 d, as_of]


def ref(type_: RefType, id_: uuid.UUID | str, label: str) -> dict[str, str]:
    return {"type": type_, "id": str(id_), "label": label}


def ref_key(type_: str, id_: uuid.UUID | str) -> str:
    return f"{type_}:{id_}"


class ToolArgs(BaseModel):
    """Base of every tool's argument model: unknown fields are rejected (INVALID_ARGUMENTS)."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    """Server-side scope of one call. Never derived from model output."""

    store: StoreContext
    as_of: datetime
    call_id: uuid.UUID  # the ``ai_tool_call`` id; aggregate refs point at it
    max_rows: int

    @property
    def store_id(self) -> uuid.UUID:
        return self.store.store_id

    def aggregate_ref(self, label: str) -> dict[str, str]:
        return ref("aggregate", self.call_id, label)


@dataclass
class ToolOutput:
    """What a handler returns; the registry wraps it into the result envelope."""

    records: list[dict[str, Any]]
    total_available: int | None = None  # defaults to len(records)
    truncated: bool = False  # a nested list (lines, events, issues) was capped
    data_window_from: datetime | None = None
    notes: list[str] = field(default_factory=list)
    untrusted_fields: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)  # tool-specific envelope fields


class ToolError(Exception):
    """An expected failure with a safe message (never a stack trace, SQL or foreign ids)."""

    def __init__(self, status: ToolCallStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def invalid(message: str) -> ToolError:
    return ToolError(ToolCallStatus.INVALID_ARGUMENTS, message)


def not_found(what: str) -> ToolError:
    # The same message whether the id is missing or belongs to another store (BR-003).
    return ToolError(
        ToolCallStatus.NOT_FOUND, f"No {what} with this identifier in the current store."
    )


def check_since(value: datetime | None, ctx: ToolContext, field_name: str) -> None:
    """Lower bounds must lie within ``[as_of − 90 days, as_of]`` (TOOL_CATALOG.md §1.1)."""
    if value is None:
        return
    if value > ctx.as_of or value < ctx.as_of - LOOKBACK_LIMIT:
        raise invalid(f"{field_name} must lie within the last 90 days.")


def utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


Handler = Callable[[Session, ToolContext, Any], ToolOutput]


@dataclass(frozen=True)
class ToolSpec:
    """One allowlisted tool. ``description`` is one sentence (compact prompts, §4.3)."""

    name: str
    description: str
    args_model: type[ToolArgs]
    permission: Permission
    row_cap: int
    handler: Handler
    # Further permissions that depend on the arguments (get_related_orders with exception_id).
    extra_permissions: Callable[[Any], tuple[Permission, ...]] = lambda _args: ()

    def required_permissions(self, args: ToolArgs) -> tuple[Permission, ...]:
        return (self.permission, *self.extra_permissions(args))


def as_json(value: Any) -> Any:
    """JSON form used in envelopes: Decimal → string, datetime → ISO-8601 UTC, UUID → string."""
    return jsonable(value)


SinceField = AwareDatetime | None
