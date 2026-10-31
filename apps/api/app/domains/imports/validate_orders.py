"""orders.csv: upsert by order_number (BR-608, STATE_MACHINES.md §1).

Status rules are not re-implemented here: the axis matrix, required timestamps, the derived
fulfillment status and reachability all come from ``orders.state`` / ``orders.service``.
Optional columns absent from the file keep the stored value of an existing order.
"""

import dataclasses
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.imports.parsing import ParsedFile
from app.domains.imports.validation import (
    IssueCollector,
    RowPlan,
    RowReader,
    ValidationContext,
    ValidationResult,
    classify,
    duplicate_check,
)
from app.domains.orders import service as orders
from app.domains.orders.models import (
    FulfillmentStatus,
    Order,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
    ShipBySource,
)
from app.domains.orders.state import (
    OrderTimestamps,
    axis_errors,
    default_fulfillment,
    timestamp_issues,
    transition_error,
)

_ZERO = Decimal("0.00")
_TIMESTAMP_COLUMNS = ("paid_at", "shipped_at", "delivered_at", "cancelled_at")
_COMPARED_FIELDS = tuple(
    f.name for f in dataclasses.fields(orders.OrderSnapshot) if f.name != "order_number"
)


def validate(
    db: Session, ctx: ValidationContext, parsed: ParsedFile
) -> ValidationResult[orders.OrderSnapshot]:
    collector = IssueCollector(ctx.timezone)
    seen: dict[str, int] = {}
    plans: list[RowPlan[orders.OrderSnapshot]] = []

    for parsed_row in parsed.rows:
        row = RowReader(parsed_row, ctx, collector)
        number = row.text("order_number", max_length=64, required=True)
        duplicate_check(row, seen, number, "order_number", "Order")
        existing = orders.find_by_number(db, ctx.store_id, number) if number else None

        channel = row.enum("channel", SalesChannel)
        customer_ref = row.text("customer_ref", max_length=64)
        placed_at = row.timestamp("placed_at", required=True)
        status = row.enum("status", OrderStatus, required=True)
        payment = row.enum("payment_status", PaymentStatus, required=True)
        fulfillment = row.enum("fulfillment_status", FulfillmentStatus)
        stamps = {column: row.timestamp(column) for column in _TIMESTAMP_COLUMNS}
        ship_by = row.timestamp("ship_by")
        currency = row.text("currency", max_length=64, required=True)
        subtotal = row.money("subtotal", required=True)
        discount_total = row.money("discount_total")
        shipping_total = row.money("shipping_total")
        tax_total = row.money("tax_total")
        total = row.money("total", required=True)
        carrier = row.text("carrier", max_length=100)
        tracking_number = row.text("tracking_number", max_length=100)

        if currency is not None and currency.upper() != ctx.currency.upper():
            row.error(
                "currency",
                "CURRENCY_MISMATCH",
                f"currency must be the store currency {ctx.currency} (BR-004).",
                currency,
            )
        if fulfillment is None and status is not None and not row.raw("fulfillment_status"):
            fulfillment = default_fulfillment(status)  # STATE_MACHINES §1.3
            if fulfillment is None:
                row.error(
                    "fulfillment_status",
                    "REQUIRED",
                    f"fulfillment_status is required when status is {status.value}.",
                )

        # Absent optional columns keep the stored values of an existing order.
        for column in _TIMESTAMP_COLUMNS:
            if not parsed.has_column(column) and existing is not None:
                stamps[column] = getattr(existing, column)
        if not parsed.has_column("ship_by") and existing is not None:
            ship_by = existing.ship_by if existing.ship_by_source is ShipBySource.IMPORTED else None

        if status is not None and payment is not None and fulfillment is not None:
            for message in axis_errors(status, payment, fulfillment):
                column = message.split(" ", 1)[0]
                row.error(
                    column,
                    "ORDER_INVALID_STATUS_COMBINATION",
                    f"{message} (STATE_MACHINES §1.3).",
                    row.raw(column) or None,
                )
            if placed_at is not None and not row.datetime_failed:
                timestamps = OrderTimestamps(
                    placed_at=placed_at,
                    paid_at=stamps["paid_at"],
                    shipped_at=stamps["shipped_at"],
                    delivered_at=stamps["delivered_at"],
                    cancelled_at=stamps["cancelled_at"],
                )
                for issue in timestamp_issues(status, payment, fulfillment, timestamps):
                    row.error(
                        issue.field, issue.code, f"{issue.message}.", row.raw(issue.field) or None
                    )

        snapshot: orders.OrderSnapshot | None = None
        if (
            number is not None
            and status is not None
            and payment is not None
            and fulfillment is not None
            and placed_at is not None
            and subtotal is not None
            and total is not None
        ):
            snapshot = orders.OrderSnapshot(
                order_number=number,
                channel=_channel(parsed, channel, existing),
                customer_ref=_stored(parsed, "customer_ref", customer_ref, existing),
                status=status,
                payment_status=payment,
                fulfillment_status=fulfillment,
                placed_at=placed_at,
                paid_at=stamps["paid_at"],
                ship_by=ship_by,
                shipped_at=stamps["shipped_at"],
                delivered_at=stamps["delivered_at"],
                cancelled_at=stamps["cancelled_at"],
                currency=ctx.currency,
                subtotal=subtotal,
                discount_total=_amount(parsed, "discount_total", discount_total, existing),
                shipping_total=_amount(parsed, "shipping_total", shipping_total, existing),
                tax_total=_amount(parsed, "tax_total", tax_total, existing),
                total=total,
                carrier=_stored(parsed, "carrier", carrier, existing),
                tracking_number=_stored(parsed, "tracking_number", tracking_number, existing),
            )
            reason = orders.check_transition(existing, snapshot)
        elif existing is not None and status is not None:
            reason = transition_error(existing.status, existing.payment_status, status)
        else:
            reason = None
        if reason:
            row.error(
                "status",
                "ORDER_TRANSITION_NOT_ALLOWED",
                f"{reason}: the target is not reachable from the current status "
                "(STATE_MACHINES §1.2).",
                row.raw("status"),
            )

        if snapshot is None or row.has_errors:
            plans.append(RowPlan(parsed_row.row_number, number or "", *classify(row, None, [])))
            continue
        changed = _changes(existing, snapshot, ctx) if existing is not None else []
        action, fields = classify(row, existing, changed)
        plans.append(
            RowPlan(parsed_row.row_number, snapshot.order_number, action, fields, snapshot)
        )
    return ValidationResult(plans=plans, issues=collector.finalize())


def _channel(
    parsed: ParsedFile, value: SalesChannel | None, existing: Order | None
) -> SalesChannel:
    if not parsed.has_column("channel") and existing is not None:
        return existing.channel
    return value or SalesChannel.WEB


def _stored(
    parsed: ParsedFile, column: str, value: str | None, existing: Order | None
) -> str | None:
    if not parsed.has_column(column) and existing is not None:
        stored: str | None = getattr(existing, column)
        return stored
    return value


def _amount(
    parsed: ParsedFile, column: str, value: Decimal | None, existing: Order | None
) -> Decimal:
    if not parsed.has_column(column) and existing is not None:
        stored: Decimal = getattr(existing, column)
        return stored
    return value if value is not None else _ZERO


def _changes(existing: Order, snapshot: orders.OrderSnapshot, ctx: ValidationContext) -> list[str]:
    changed: list[str] = []
    for name in _COMPARED_FIELDS:
        if name == "ship_by":
            continue
        if getattr(existing, name) != getattr(snapshot, name):
            changed.append(name)
    ship_by = orders.compute_ship_by(snapshot.ship_by, snapshot.paid_at, ctx.fulfillment_sla_hours)
    if (existing.ship_by, existing.ship_by_source) != ship_by:
        changed.append("ship_by")
    return changed
