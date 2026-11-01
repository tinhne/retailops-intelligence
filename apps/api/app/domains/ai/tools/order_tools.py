"""Order tools: get_related_orders and get_overdue_orders (TOOL_CATALOG.md §2.5, §2.9).

Both read through ``orders.queries`` (the order list and detail behind the REST endpoints). The
overdue predicate is the shared BR-202 condition and the severity preview is the rule's own
``severity_for``. ``customer_ref`` and the tracking number are never returned.
"""

import uuid
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.pagination import PageParams
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
from app.domains.ai.tools.exception_tools import load_detail
from app.domains.ai.tools.sanitize import NAME_MAX, REFERENCE_MAX, TextGuard
from app.domains.catalog.models import Product
from app.domains.exceptions.models import EntityType, ExceptionType, LinkRole
from app.domains.exceptions.rules.base import hours
from app.domains.exceptions.rules.order_fulfillment_overdue import severity_for
from app.domains.identity.permissions import Permission
from app.domains.orders import queries as orders
from app.domains.orders import service as order_service
from app.domains.orders.models import OrderStatus
from app.domains.orders.schemas import LinkedException, OrderDetail
from app.domains.orders.state import COMMITTED_STATUSES

LINES_CAP = 20
_OVERDUE_SCAN_PAGES = 20  # 2,000 overdue orders at most are ranked in memory


def active_exception_refs(items: list[LinkedException], guard: TextGuard) -> list[dict[str, Any]]:
    return [
        {
            "ref": ref("exception", e.id, f"{e.reference} · {guard(e.title, NAME_MAX)}"),
            "exception_type": e.exception_type,
            "severity": e.severity,
            "priority_band": e.priority_band,
        }
        for e in items
        if e.is_active
    ]


def order_record(order: OrderDetail, guard: TextGuard, *, include_lines: bool) -> dict[str, Any]:
    amounts = order.amounts
    record: dict[str, Any] = {
        "ref": ref("order", order.id, order.order_number),
        "order_number": order.order_number,
        "channel": order.channel,
        "status": order.status,
        "payment_status": order.payment_status,
        "fulfillment_status": order.fulfillment_status,
        "placed_at": order.placed_at,
        "paid_at": order.paid_at,
        "ship_by": order.ship_by,
        "ship_by_source": order.ship_by_source,
        "shipped_at": order.shipped_at,
        "delivered_at": order.delivered_at,
        "cancelled_at": order.cancelled_at,
        "currency": amounts.currency,
        "subtotal": amounts.subtotal,
        "discount_total": amounts.discount_total,
        "shipping_total": amounts.shipping_total,
        "tax_total": amounts.tax_total,
        "total": amounts.total,
        "expected_total": amounts.expected_total,
        "total_difference": amounts.difference,
        "has_total_mismatch": amounts.has_total_mismatch,
        "is_overdue": order.is_overdue,
        "hours_overdue": order.hours_overdue,
        "has_tracking": bool(order.tracking_number),
        "carrier": guard(order.carrier, REFERENCE_MAX),
        "line_count": len(order.lines),
        "active_exceptions": active_exception_refs(order.exceptions, guard),
    }
    if include_lines:
        record["lines"] = [
            {
                "line_number": line.line_number,
                "sku": line.product_sku,
                "product": {
                    "ref": ref(
                        "product",
                        line.product_id,
                        f"{line.product_sku} · {guard(line.product_name, NAME_MAX)}",
                    )
                },
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "line_discount": line.line_discount,
            }
            for line in order.lines[:LINES_CAP]
        ]
    return record


_UNTRUSTED_ORDER_FIELDS = [
    "records[].carrier",
    "records[].lines[].product.ref.label",
    "records[].active_exceptions[].ref.label",
]


# --- get_related_orders --------------------------------------------------------------------------


class GetRelatedOrdersArgs(ToolArgs):
    exception_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    order_numbers: list[str] | None = Field(default=None, min_length=1, max_length=20)
    status: list[OrderStatus] | None = Field(default=None, max_length=9)
    placed_since: AwareDatetime | None = None
    include_lines: bool = True
    sort: Literal["-placed_at", "placed_at", "ship_by"] = "-placed_at"
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _one_selector(self) -> "GetRelatedOrdersArgs":
        chosen = [
            name
            for name in ("exception_id", "product_id", "sku", "order_numbers")
            if getattr(self, name) is not None
        ]
        if len(chosen) != 1:
            raise ValueError(
                "exactly one of exception_id, product_id, sku, order_numbers is required"
            )
        if self.order_numbers is not None and any(
            not n.strip() or len(n) > 64 for n in self.order_numbers
        ):
            raise ValueError("order numbers must be 1–64 characters")
        return self


def _related_permissions(args: GetRelatedOrdersArgs) -> tuple[Permission, ...]:
    return (Permission.EXCEPTIONS_READ,) if args.exception_id is not None else ()


def _order(db: Session, ctx: ToolContext, order_id: uuid.UUID) -> OrderDetail | None:
    try:
        return orders.get_order(db, ctx.store_id, order_id, as_of=ctx.as_of)
    except NotFoundError:
        return None


def _filtered(details: list[OrderDetail], args: GetRelatedOrdersArgs) -> list[OrderDetail]:
    if args.status:
        details = [d for d in details if d.status in args.status]
    if args.placed_since is not None:
        details = [d for d in details if d.placed_at >= args.placed_since]
    return details


def get_related_orders(db: Session, ctx: ToolContext, args: GetRelatedOrdersArgs) -> ToolOutput:
    check_since(args.placed_since, ctx, "placed_since")
    limit = min(args.limit, ctx.max_rows)
    extra: dict[str, Any] = {}
    roles: dict[uuid.UUID, LinkRole] = {}
    uncovered: dict[str, Any] = {}
    if args.exception_id is not None:
        detail = load_detail(db, ctx, args.exception_id)
        links = [link for link in detail.links if link.entity_type is EntityType.ORDER]
        roles = {link.entity_id: link.role for link in links}
        if detail.exception_type is ExceptionType.INVENTORY_OVERSOLD:
            for rows in (detail.evidence or {}).get("records", {}).values():
                for row in rows if isinstance(rows, list) else []:
                    if isinstance(row, dict) and "uncovered_quantity" in row:
                        uncovered[str(row.get("order_id"))] = row["uncovered_quantity"]
        found = [d for d in (_order(db, ctx, link.entity_id) for link in links) if d is not None]
        found.sort(key=lambda d: (roles.get(d.id) is not LinkRole.PRIMARY, d.placed_at))
        details = _filtered(found, args)
    elif args.order_numbers is not None:
        details, missing = [], []
        for number in dict.fromkeys(n.strip() for n in args.order_numbers):
            order = order_service.find_by_number(db, ctx.store_id, number)
            detail_ = _order(db, ctx, order.id) if order is not None else None
            if detail_ is None:
                missing.append(number)
            else:
                details.append(detail_)
        details = _filtered(details, args)
        extra["not_found"] = missing
    else:
        selector = (
            Product.sku == args.sku.strip()
            if args.sku is not None
            else Product.id == args.product_id
        )
        product_id = db.scalar(select(Product.id).where(Product.store_id == ctx.store_id, selector))
        if product_id is None:
            raise not_found("product")
        page = orders.list_orders(
            db,
            ctx.store_id,
            filters=orders.OrderFilters(
                statuses=args.status, placed_from=args.placed_since, product_id=product_id
            ),
            sort=args.sort,
            paging=PageParams(page=1, page_size=limit),
            as_of=ctx.as_of,
        )
        details = [d for d in (_order(db, ctx, item.id) for item in page.items) if d is not None]
        records = []
        for detail_ in details:
            guard = TextGuard()
            records.append(
                guard.mark(order_record(detail_, guard, include_lines=args.include_lines))
            )
        return ToolOutput(
            records=records,
            total_available=page.total,
            truncated=any(len(d.lines) > LINES_CAP for d in details),
            data_window_from=args.placed_since,
            untrusted_fields=_UNTRUSTED_ORDER_FIELDS,
        )

    records = []
    for detail_ in details[:limit]:
        guard = TextGuard()
        record = order_record(detail_, guard, include_lines=args.include_lines)
        if detail_.id in roles:
            record["link_role"] = roles[detail_.id]
        if str(detail_.id) in uncovered:
            record["uncovered_quantity"] = uncovered[str(detail_.id)]
        records.append(guard.mark(record))
    return ToolOutput(
        records=records,
        total_available=len(details),
        truncated=any(len(d.lines) > LINES_CAP for d in details[:limit]),
        data_window_from=args.placed_since,
        untrusted_fields=_UNTRUSTED_ORDER_FIELDS,
        extra=extra,
    )


# --- get_overdue_orders --------------------------------------------------------------------------


class GetOverdueOrdersArgs(ToolArgs):
    status: list[OrderStatus] | None = Field(default=None, max_length=3)
    min_hours_overdue: float = Field(default=0, ge=0, le=2160)
    sort: Literal["-hours_overdue", "ship_by", "-total"] = "-hours_overdue"
    limit: int = Field(default=20, ge=1, le=50)


def get_overdue_orders(db: Session, ctx: ToolContext, args: GetOverdueOrdersArgs) -> ToolOutput:
    statuses = list(args.status or sorted(COMMITTED_STATUSES))
    if any(s not in COMMITTED_STATUSES for s in statuses):
        raise invalid("status must be a subset of PAID, PROCESSING and READY_TO_SHIP.")
    rows = []
    for page_number in range(1, _OVERDUE_SCAN_PAGES + 1):
        page = orders.list_orders(
            db,
            ctx.store_id,
            filters=orders.OrderFilters(statuses=statuses, overdue=True),
            sort="ship_by",
            paging=PageParams(page=page_number, page_size=100),
            as_of=ctx.as_of,
        )
        rows.extend(page.items)
        if page_number * 100 >= page.total:
            break
    matching = []
    for item in rows:
        assert item.ship_by is not None  # overdue implies a ship-by (BR-202)
        overdue = ctx.as_of - item.ship_by
        if overdue.total_seconds() / 3600 >= args.min_hours_overdue:
            matching.append((item, overdue))
    if args.sort == "-total":
        matching.sort(key=lambda pair: (-pair[0].total, pair[0].order_number))
    # "-hours_overdue" and "ship_by" are the same order: the oldest ship-by first.
    limit = min(args.limit, ctx.max_rows)
    records = []
    for item, overdue in matching[:limit]:
        linked = orders.linked_exceptions(db, ctx.store_id, EntityType.ORDER, item.id)
        exception = next(
            (
                e
                for e in linked
                if e.is_active and e.exception_type is ExceptionType.ORDER_FULFILLMENT_OVERDUE
            ),
            None,
        )
        records.append(
            {
                "ref": ref("order", item.id, item.order_number),
                "order_number": item.order_number,
                "status": item.status,
                "paid_at": item.paid_at,
                "ship_by": item.ship_by,
                "ship_by_source": item.ship_by_source,
                "hours_overdue": hours(overdue),
                "total": item.total,
                "currency": item.currency,
                "line_count": item.line_count,
                "severity_if_detected": severity_for(overdue),
                "exception": (
                    {"ref": ref("exception", exception.id, exception.reference)}
                    if exception
                    else None
                ),
            }
        )
    notes = ["Overdue means a committed status and as_of after ship_by (BR-202), evaluated now."]
    if any(r["exception"] is None for r in records):
        notes.append(
            "Orders without an exception became overdue after the last evaluation run; the next "
            "run will create their ORDER_FULFILLMENT_OVERDUE exception."
        )
    return ToolOutput(
        records=records,
        total_available=len(matching),
        notes=notes,
        extra={"total_overdue": len(matching)},
    )


SPECS = (
    ToolSpec(
        name="get_related_orders",
        description="Orders behind an exception, containing a product, or by order number.",
        args_model=GetRelatedOrdersArgs,
        permission=Permission.ORDERS_READ,
        row_cap=50,
        handler=get_related_orders,
        extra_permissions=_related_permissions,
    ),
    ToolSpec(
        name="get_overdue_orders",
        description="Orders past their ship-by right now (BR-202), oldest deadline first.",
        args_model=GetOverdueOrdersArgs,
        permission=Permission.ORDERS_READ,
        row_cap=50,
        handler=get_overdue_orders,
    ),
)
