"""Exception tools: list_exceptions, get_exception, get_exception_history (TOOL_CATALOG §2.2–2.4).

They call the same ``exceptions.service`` functions as the REST endpoints, so the copilot and the
exception inbox can never disagree about a number.
"""

import uuid
from datetime import timedelta
from typing import Any, Literal

from pydantic import AwareDatetime, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.domains.ai.tools.base import (
    ToolArgs,
    ToolContext,
    ToolOutput,
    ToolSpec,
    check_since,
    invalid,
    not_found,
    ref,
)
from app.domains.ai.tools.sanitize import NAME_MAX, NOTE_MAX, TITLE_MAX, TextGuard
from app.domains.catalog.models import Product
from app.domains.exceptions import service as exceptions
from app.domains.exceptions.models import (
    EntityType,
    ExceptionCategory,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    PriorityBand,
    Severity,
)
from app.domains.exceptions.schemas import ExceptionDetail, ExceptionListItem
from app.domains.identity.permissions import Permission
from app.domains.orders.models import Order

PRIORITY_NOTE = (
    "The priority score is a ranking aid built from severity (S), affected orders (A), value at "
    "risk (E), deadline (D) and time open (T); it is not a measure of business impact."
)
EXPOSURE_NOTE = (
    "exposure_amount is the gross order-line value at risk (BR-404), not a measured financial "
    "impact. Sums are not additive across exceptions: one order line can sit in several."
)

# Static text per exception type, mirroring EXCEPTION_CATALOG.md (condition and severity rule).
RULE_CONDITION: dict[ExceptionType, str] = {
    ExceptionType.INVENTORY_OVERSOLD: "Active product with available < 0 (committed demand "
    "exceeds on-hand stock).",
    ExceptionType.INVENTORY_OVERSELL_RISK: "Active product with available ≥ 0 and pending demand "
    "> available (BR-403).",
    ExceptionType.INVENTORY_OUT_OF_STOCK: "Active product with available = 0.",
    ExceptionType.INVENTORY_BELOW_REORDER_POINT: "Active product with 0 < available ≤ reorder "
    "point.",
    ExceptionType.ORDER_FULFILLMENT_OVERDUE: "Order in PAID, PROCESSING or READY_TO_SHIP and "
    "past its ship-by (BR-202).",
    ExceptionType.ORDER_STALLED_AFTER_PAYMENT: "Order still PAID longer than the stall threshold "
    "after payment, not yet overdue (BR-203).",
    ExceptionType.ORDER_REFUND_PENDING: "Cancelled order still PAID longer than the refund "
    "threshold after cancellation (BR-206).",
    ExceptionType.DATA_ORDER_TOTAL_MISMATCH: "Order total differs from its lines by more than "
    "0.01 (BR-205).",
    ExceptionType.DATA_NEGATIVE_ON_HAND: "Product with on_hand < 0: a receipt or count is "
    "missing from the ledger.",
}
SEVERITY_CRITERIA: dict[ExceptionType, str] = {
    ExceptionType.INVENTORY_OVERSOLD: "Always CRITICAL.",
    ExceptionType.INVENTORY_OVERSELL_RISK: "Always HIGH.",
    ExceptionType.INVENTORY_OUT_OF_STOCK: "HIGH if the product is selling (average daily units "
    "> 0); otherwise MEDIUM.",
    ExceptionType.INVENTORY_BELOW_REORDER_POINT: "HIGH if days of cover < supplier lead time; "
    "otherwise MEDIUM.",
    ExceptionType.ORDER_FULFILLMENT_OVERDUE: "Overdue ≤ 24 h → MEDIUM; > 24 h and ≤ 72 h → HIGH; "
    "> 72 h → CRITICAL.",
    ExceptionType.ORDER_STALLED_AFTER_PAYMENT: "HIGH if the ship-by is 12 h away or less; "
    "otherwise MEDIUM.",
    ExceptionType.ORDER_REFUND_PENDING: "HIGH; CRITICAL when more than 3 × the refund threshold "
    "has passed since cancellation.",
    ExceptionType.DATA_ORDER_TOTAL_MISMATCH: "MEDIUM; LOW if the difference is below 1.00.",
    ExceptionType.DATA_NEGATIVE_ON_HAND: "Always HIGH.",
}
_COMPONENT_LETTER = {
    "severity": "S",
    "affected_orders": "A",
    "exposure": "E",
    "deadline": "D",
    "age": "T",
}
NESTED_CAP = 20  # evidence lists, events, notes inside one record
EXCEPTION_SORTS = Literal["-priority_score", "due_at", "-first_detected_at", "-last_detected_at"]


# --- shared record building ----------------------------------------------------------------------


def _entity_ref(
    entity_type: EntityType, entity_id: uuid.UUID, label: str, name: str | None, guard: TextGuard
) -> dict[str, str]:
    if entity_type is EntityType.PRODUCT:
        text = f"{label} · {name}" if name else label
        return ref("product", entity_id, guard(text, NAME_MAX) or label)
    return ref("order", entity_id, label)


def exception_label(reference: str, title: str, guard: TextGuard) -> str:
    return f"{reference} · {guard(title, TITLE_MAX)}"


def list_record(item: ExceptionListItem, guard: TextGuard) -> dict[str, Any]:
    return {
        "ref": ref("exception", item.id, exception_label(item.reference, item.title, guard)),
        "reference": item.reference,
        "title": guard(item.title, TITLE_MAX),
        "exception_type": item.exception_type,
        "category": item.category,
        "severity": item.severity,
        "status": item.status,
        "priority_score": item.priority_score,
        "priority_band": item.priority_band,
        "primary_entity": {
            "ref": _entity_ref(
                item.primary_entity.type,
                item.primary_entity.id,
                item.primary_entity.label,
                item.primary_entity.name,
                guard,
            )
        },
        "exposure_amount": item.exposure_amount,
        "affected_order_count": item.affected_order_count,
        "deadline_at": item.deadline_at,
        "due_at": item.due_at,
        "is_past_due": item.is_past_due,
        "assignee": {"display_name": item.assignee.full_name} if item.assignee else None,
        "first_detected_at": item.first_detected_at,
        "last_detected_at": item.last_detected_at,
        "detection_count": item.detection_count,
        "reopen_count": item.reopen_count,
        "closed_at": item.closed_at,
        "resolution_code": item.resolution_code,
    }


def _priority(detail: ExceptionDetail) -> dict[str, Any]:
    breakdown = detail.priority_breakdown or {}
    result: dict[str, Any] = {"score": detail.priority_score, "band": detail.priority_band}
    components = []
    for component in breakdown.get("components") or []:
        letter = _COMPONENT_LETTER.get(str(component.get("key")))
        if letter:
            result[letter] = component.get("points")
        components.append(
            {
                "key": component.get("key"),
                "label": component.get("label"),
                "points": component.get("points"),
                "max_points": component.get("max_points"),
                "explanation": component.get("explanation"),
            }
        )
    result["components"] = components
    return result


def _source_ref(source: Any, guard: TextGuard) -> dict[str, str] | None:
    if not isinstance(source, dict) or source.get("type") not in ("product", "order", "import"):
        return None
    return ref(
        source["type"], str(source.get("id")), guard(str(source.get("label")), NAME_MAX) or ""
    )


def _evidence(detail: ExceptionDetail, guard: TextGuard) -> tuple[list[dict[str, Any]], bool]:
    facts = list((detail.evidence or {}).get("facts") or [])
    rows = []
    for item in facts[:NESTED_CAP]:
        value = item.get("value")
        row: dict[str, Any] = {
            "key": item.get("key"),
            "label": item.get("label"),
            "value": guard(value, NAME_MAX) if isinstance(value, str) else value,
            "unit": item.get("unit"),
        }
        if item.get("estimate"):
            row["is_estimate"] = True
        source = _source_ref(item.get("source"), guard)
        if source is not None:
            row["source"] = source
        rows.append(row)
    return rows, len(facts) > NESTED_CAP


def _evidence_records(
    detail: ExceptionDetail, guard: TextGuard
) -> tuple[dict[str, list[dict[str, Any]]], bool]:
    """Record lists of the evidence (affected orders, lines), each capped at 20 rows."""
    truncated = False
    out: dict[str, list[dict[str, Any]]] = {}
    for name, rows in ((detail.evidence or {}).get("records") or {}).items():
        if not isinstance(rows, list):
            continue
        truncated = truncated or len(rows) > NESTED_CAP
        cleaned = []
        for row in rows[:NESTED_CAP]:
            if not isinstance(row, dict):
                continue
            item = {
                k: (guard(v, NAME_MAX) if isinstance(v, str) else v)
                for k, v in row.items()
                if k not in ("source", "customer_ref") and not isinstance(v, dict | list)
            }
            source = _source_ref(row.get("source"), guard)
            if source is not None:
                item["ref"] = source
            cleaned.append(item)
        out[str(name)] = cleaned
    return out, truncated


def detail_record(detail: ExceptionDetail, guard: TextGuard) -> tuple[dict[str, Any], bool]:
    record = list_record(detail, guard)
    evidence, evidence_cut = _evidence(detail, guard)
    records, records_cut = _evidence_records(detail, guard)
    calculation = detail.calculation or {}
    record.update(
        {
            "rule_id": detail.rule_id,
            "rule_condition": RULE_CONDITION.get(detail.exception_type),
            "severity_criteria": SEVERITY_CRITERIA.get(detail.exception_type),
            "recommended_action": detail.recommended_action,
            "evidence": evidence,
            "evidence_records": records,
            "calculation": {
                "formulas": calculation.get("formulas") or [],
                "outputs": calculation.get("outputs") or {},
            },
            "priority_breakdown": _priority(detail),
            "linked_entities": [
                {
                    "ref": _entity_ref(
                        link.entity_type, link.entity_id, link.label, link.name, guard
                    ),
                    "role": link.role,
                }
                for link in detail.links[:NESTED_CAP]
            ],
            "resolution_note": guard(
                detail.resolution.resolution_note if detail.resolution else None, NOTE_MAX
            ),
            "verified_at": detail.resolution.verified_at if detail.resolution else None,
            "dismissed_reason": detail.dismissed_reason,
            "superseded_by": (
                {"ref": ref("exception", detail.superseded_by.id, detail.superseded_by.reference)}
                if detail.superseded_by
                else None
            ),
            "previous_occurrence": (
                {
                    "ref": ref(
                        "exception",
                        detail.previous_occurrence.id,
                        detail.previous_occurrence.reference,
                    )
                }
                if detail.previous_occurrence
                else None
            ),
        }
    )
    return record, evidence_cut or records_cut or len(detail.links) > NESTED_CAP


_UNTRUSTED_EXCEPTION_FIELDS = ["records[].title", "records[].ref.label"]


# --- list_exceptions -----------------------------------------------------------------------------


class ListExceptionsArgs(ToolArgs):
    status: list[ExceptionStatus] | None = Field(default=None, max_length=6)
    severity: list[Severity] | None = Field(default=None, max_length=4)
    category: list[ExceptionCategory] | None = Field(default=None, max_length=4)
    exception_type: list[ExceptionType] | None = Field(default=None, max_length=9)
    priority_band: list[PriorityBand] | None = Field(default=None, max_length=4)
    assignee: Literal["ME", "UNASSIGNED", "ANY"] = "ANY"
    entity_sku: str | None = Field(default=None, min_length=1, max_length=64)
    entity_order_number: str | None = Field(default=None, min_length=1, max_length=64)
    query: str | None = Field(
        default=None, min_length=2, max_length=100, description="reference or title contains"
    )
    detected_since: AwareDatetime | None = None
    resolved_since: AwareDatetime | None = None
    due_before: AwareDatetime | None = None
    sort: EXCEPTION_SORTS = "-priority_score"
    limit: int = Field(default=20, ge=1, le=50)


def _entity_id(
    db: Session, ctx: ToolContext, model: type[Product] | type[Order], value: str
) -> Any:
    column = Product.sku if model is Product else Order.order_number
    store_column = Product.store_id if model is Product else Order.store_id
    id_column = Product.id if model is Product else Order.id
    return db.scalar(select(id_column).where(store_column == ctx.store_id, column == value.strip()))


def list_exceptions(db: Session, ctx: ToolContext, args: ListExceptionsArgs) -> ToolOutput:
    check_since(args.detected_since, ctx, "detected_since")
    check_since(args.resolved_since, ctx, "resolved_since")
    if args.due_before is not None and args.due_before > ctx.as_of + timedelta(days=30):
        raise invalid("due_before may lie at most 30 days after as_of.")
    product_id = order_id = None
    if args.entity_sku is not None:
        product_id = _entity_id(db, ctx, Product, args.entity_sku)
    if args.entity_order_number is not None:
        order_id = _entity_id(db, ctx, Order, args.entity_order_number)
    statuses = args.status
    if statuses is None and args.resolved_since is not None:
        statuses = [ExceptionStatus.RESOLVED]
    notes = [PRIORITY_NOTE, EXPOSURE_NOTE]
    window_from = min(
        (d for d in (args.detected_since, args.resolved_since) if d is not None), default=None
    )
    if (args.entity_sku and product_id is None) or (args.entity_order_number and order_id is None):
        notes.append("The SKU or order number does not exist in this store, so nothing matches.")
        return ToolOutput(records=[], total_available=0, notes=notes, data_window_from=window_from)
    items, total = exceptions.list_exceptions(
        db,
        ctx.store_id,
        current_user_id=ctx.store.user.id,
        filters=exceptions.ExceptionFilters(
            statuses=statuses,
            severities=args.severity,
            exception_types=args.exception_type,
            categories=args.category,
            priority_bands=args.priority_band,
            assignee={"ME": "me", "UNASSIGNED": "unassigned", "ANY": None}[args.assignee],
            product_id=product_id,
            order_id=order_id,
            q=args.query,
            detected_from=args.detected_since,
            resolved_from=args.resolved_since,
            due_before=args.due_before,
        ),
        sort=args.sort,
        offset=0,
        limit=min(args.limit, ctx.max_rows),
        now=ctx.as_of,
    )
    records = []
    for item in items:
        guard = TextGuard()
        records.append(guard.mark(list_record(item, guard)))
    return ToolOutput(
        records=records,
        total_available=total,
        notes=notes,
        untrusted_fields=_UNTRUSTED_EXCEPTION_FIELDS,
        data_window_from=window_from,
    )


# --- get_exception -------------------------------------------------------------------------------


class GetExceptionArgs(ToolArgs):
    exception_id: uuid.UUID


def load_detail(db: Session, ctx: ToolContext, exception_id: uuid.UUID) -> ExceptionDetail:
    try:
        return exceptions.get_exception_detail(db, ctx.store, exception_id, now=ctx.as_of)
    except NotFoundError as err:
        raise not_found("exception") from err


def get_exception(db: Session, ctx: ToolContext, args: GetExceptionArgs) -> ToolOutput:
    detail = load_detail(db, ctx, args.exception_id)
    guard = TextGuard()
    record, truncated = detail_record(detail, guard)
    return ToolOutput(
        records=[guard.mark(record)],
        truncated=truncated,
        notes=[PRIORITY_NOTE, EXPOSURE_NOTE],
        untrusted_fields=[
            *_UNTRUSTED_EXCEPTION_FIELDS,
            "records[].resolution_note",
            "records[].evidence[].value",
            "records[].evidence_records",
        ],
    )


# --- get_exception_history -----------------------------------------------------------------------

_PAYLOAD_KEYS = (
    "reason",
    "from",
    "to",
    "severity",
    "resolution_code",
    "dismissal_reason",
    "source",
    "superseded_by_reference",
    "carried_over_from_reference",
    "note",
)
_HISTORY_SCAN = 200  # newest events scanned before the event_types filter is applied


class GetExceptionHistoryArgs(ToolArgs):
    exception_id: uuid.UUID
    event_types: list[ExceptionEventType] | None = Field(default=None, max_length=12)
    include_notes: bool = True
    limit: int = Field(default=30, ge=1, le=50)


def _payload_summary(payload: dict[str, Any], guard: TextGuard) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in _PAYLOAD_KEYS:
        value = payload.get(key)
        if value is None or isinstance(value, dict | list):
            continue
        summary[key] = guard(value, 200) if isinstance(value, str) and key == "note" else value
    return summary


def get_exception_history(
    db: Session, ctx: ToolContext, args: GetExceptionHistoryArgs
) -> ToolOutput:
    detail = load_detail(db, ctx, args.exception_id)
    guard = TextGuard()
    _, total = exceptions.list_events(db, ctx.store, detail.id, offset=0, limit=1)
    scan_from = max(total - _HISTORY_SCAN, 0)
    events, _ = exceptions.list_events(
        db, ctx.store, detail.id, offset=scan_from, limit=_HISTORY_SCAN
    )
    wanted = set(args.event_types or [])
    newest = [e for e in reversed(events) if not wanted or e.event_type in wanted]
    limit = min(args.limit, ctx.max_rows)
    event_rows = [
        {
            "event_type": e.event_type,
            "occurred_at": e.occurred_at,
            "actor": {
                "type": e.actor_type,
                "display_name": e.actor.full_name if e.actor else None,
            },
            "from_status": e.from_status,
            "to_status": e.to_status,
            "evaluation_run_id": e.evaluation_run_id,
            "payload_summary": _payload_summary(e.payload or {}, guard),
        }
        for e in newest[:limit]
    ]
    note_rows: list[dict[str, Any]] = []
    notes_total = 0
    if args.include_notes:
        _, notes_total = exceptions.list_notes(db, ctx.store, detail.id, offset=0, limit=1)
        notes, _ = exceptions.list_notes(
            db, ctx.store, detail.id, offset=max(notes_total - NESTED_CAP, 0), limit=NESTED_CAP
        )
        note_rows = [
            {
                "author_display_name": n.author.full_name if n.author else None,
                "source": n.source,
                "created_at": n.created_at,
                "body": guard(n.body, NOTE_MAX),
            }
            for n in reversed(notes)
        ]
    record = {
        "ref": ref("exception", detail.id, exception_label(detail.reference, detail.title, guard)),
        "status": detail.status,
        "assignee": {"display_name": detail.assignee.full_name} if detail.assignee else None,
        "reopen_count": detail.reopen_count,
        "event_count": total,
        "events": event_rows,
        "notes": note_rows,
    }
    return ToolOutput(
        records=[guard.mark(record)],
        truncated=len(newest) > limit or notes_total > NESTED_CAP,
        untrusted_fields=[
            "records[].ref.label",
            "records[].notes[].body",
            "records[].events[].payload_summary.note",
        ],
    )


SPECS = (
    ToolSpec(
        name="list_exceptions",
        description="Find and rank the store's exceptions with filters.",
        args_model=ListExceptionsArgs,
        permission=Permission.EXCEPTIONS_READ,
        row_cap=50,
        handler=list_exceptions,
    ),
    ToolSpec(
        name="get_exception",
        description="One exception with evidence, severity rule, priority breakdown and "
        "recommended action.",
        args_model=GetExceptionArgs,
        permission=Permission.EXCEPTIONS_READ,
        row_cap=1,
        handler=get_exception,
    ),
    ToolSpec(
        name="get_exception_history",
        description="Events and notes of one exception, newest first.",
        args_model=GetExceptionHistoryArgs,
        permission=Permission.EXCEPTIONS_READ,
        row_cap=1,
        handler=get_exception_history,
    ),
)
