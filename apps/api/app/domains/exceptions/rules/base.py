"""Shared building blocks for detection rules (EXCEPTION_CATALOG.md "Finding structure").

A rule is a pure function ``(snapshot, settings, as_of) → list[Finding]``. It performs no I/O and
never reads the wall clock (BR-504). Everything a finding stores (evidence, calculation) is plain
JSON so it can be persisted as-is and compared between runs.
"""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domains.exceptions.models import EntityType, ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.snapshot import EvaluationSnapshot, RuleSettings

CENT = Decimal("0.01")
ZERO_MONEY = Decimal("0.00")
TITLE_MAX = 200
ACTION_MAX = 500


def money(value: Decimal) -> Decimal:
    """Round a money amount to cents (BR-503)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def jsonable(value: Any) -> Any:
    """Convert a value to its JSON form: Decimal → string, datetime → ISO-8601 UTC, UUID → str."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def source(type_: str, id_: uuid.UUID | str, label: str) -> dict[str, str]:
    """A source reference ``{type, id, label}`` pointing at the record a fact came from."""
    return {"type": type_, "id": str(id_), "label": label}


def fact(
    key: str,
    label: str,
    value: Any,
    *,
    src: dict[str, str] | None,
    unit: str | None = None,
    estimate: bool = False,
    volatile: bool = False,
) -> dict[str, Any]:
    """One typed fact of the evidence.

    ``estimate`` marks values that are estimates and must be labelled as such (BR-152).
    ``volatile`` marks values that change with the passage of time alone (hours overdue, sales
    velocity over a sliding window). Volatile facts are refreshed on every run but never count as a
    material evidence change, so they do not produce ``EVIDENCE_UPDATED`` events.
    """
    return {
        "key": key,
        "label": label,
        "value": jsonable(value),
        "unit": unit,
        "estimate": estimate,
        "volatile": volatile,
        "source": src,
    }


def evidence(
    facts: list[dict[str, Any]],
    records: Mapping[str, list[dict[str, Any]]] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble an evidence document. ``records`` rows must hold no volatile values."""
    return {
        "facts": facts,
        "records": jsonable(dict(records or {})),
        "notes": list(notes or []),
    }


def calculation(
    formulas: list[str],
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "formulas": formulas,
        "inputs": jsonable(dict(inputs)),
        "outputs": jsonable(dict(outputs)),
    }
    if steps is not None:
        body["steps"] = jsonable(steps)
    return body


def material_view(evidence_doc: Mapping[str, Any]) -> dict[str, Any]:
    """The part of an evidence document whose change is *material* (EVIDENCE_UPDATED).

    Non-volatile fact values plus the record lists. Labels, sources of volatile facts and notes
    are excluded, so passing time alone ("hours overdue") never counts as a change.
    """
    facts = evidence_doc.get("facts") or []
    return {
        "facts": {
            f.get("key"): f.get("value")
            for f in facts
            if isinstance(f, Mapping) and not f.get("volatile")
        },
        "records": evidence_doc.get("records") or {},
    }


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    word = singular if count == 1 else (plural_form or f"{singular}s")
    return f"{count} {word}"


def hours(delta: timedelta) -> Decimal:
    """A duration in hours, rounded to one decimal (for display only)."""
    return (Decimal(delta.total_seconds()) / Decimal(3600)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def format_local(moment: datetime, timezone: str) -> str:
    """Display a UTC instant in the store time zone with its abbreviation (BR-501)."""
    try:
        zone: ZoneInfo | Any = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return moment.astimezone(zone).strftime("%Y-%m-%d %H:%M %Z")


def dedup_key(exception_type: ExceptionType, entity_type: EntityType, entity_id: uuid.UUID) -> str:
    """``{exception_type}:{entity_type}:{entity_id}`` (STATE_MACHINES.md §3.3)."""
    return f"{exception_type.value}:{entity_type.value}:{entity_id}"


@dataclass(frozen=True)
class EntityRef:
    type: EntityType
    id: uuid.UUID
    label: str

    def as_source(self) -> dict[str, str]:
        return source(self.type.value, self.id, self.label)


@dataclass(frozen=True)
class Finding:
    """One detected condition, ready to be reconciled against stored exceptions."""

    rule_id: str
    exception_type: ExceptionType
    category: ExceptionCategory
    primary_entity: EntityRef
    severity: Severity
    title: str
    evidence: dict[str, Any]
    calculation: dict[str, Any]
    recommended_action: str
    detected_at: datetime
    related_entities: tuple[EntityRef, ...] = ()
    affected_order_ids: tuple[uuid.UUID, ...] = ()
    exposure_amount: Decimal = ZERO_MONEY
    deadline_at: datetime | None = None

    @property
    def dedup_key(self) -> str:
        return dedup_key(self.exception_type, self.primary_entity.type, self.primary_entity.id)

    @property
    def affected_order_count(self) -> int:
        return len(set(self.affected_order_ids))


RuleFunction = Callable[[EvaluationSnapshot, RuleSettings, datetime], list[Finding]]


@dataclass(frozen=True)
class Rule:
    """A registered detection rule (one per EXCEPTION_CATALOG entry)."""

    rule_id: str
    exception_type: ExceptionType
    category: ExceptionCategory
    evaluate: RuleFunction
