"""order_items.csv: upsert by (order_number, line_number) (BR-605, BR-609).

Orders and SKUs must already exist. The line lock comes from ``orders.service.line_lock_reason``.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domains.catalog import service as catalog
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
from app.domains.orders.models import Order, OrderItem

_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class OrderItemRow:
    order_number: str
    line: orders.OrderLineSnapshot


def line_key(order_number: str, line_number: int) -> str:
    return f"{order_number}#{line_number}"


def validate(
    db: Session, ctx: ValidationContext, parsed: ParsedFile
) -> ValidationResult[OrderItemRow]:
    collector = IssueCollector(ctx.timezone)
    products = catalog.find_products_by_sku(
        db, ctx.store_id, (row.values.get("sku", "") for row in parsed.rows)
    )
    found: dict[str, Order | None] = {}
    lines: dict[str, dict[int, OrderItem]] = {}
    seen: dict[str, int] = {}
    plans: list[RowPlan[OrderItemRow]] = []

    def order_for(number: str) -> Order | None:
        if number not in found:
            order = orders.find_by_number(db, ctx.store_id, number)
            found[number] = order
            if order is not None:
                lines[number] = {item.line_number: item for item in order.items}
        return found[number]

    for parsed_row in parsed.rows:
        row = RowReader(parsed_row, ctx, collector)
        number = row.text("order_number", max_length=64, required=True)
        line_number = row.integer("line_number", required=True, minimum=1)
        key = line_key(number, line_number) if number and line_number else None
        duplicate_check(row, seen, key, "line_number", "Order line")
        sku = row.text("sku", max_length=64, required=True)
        quantity = row.integer("quantity", required=True, minimum=1)
        unit_price = row.money("unit_price", required=True)
        line_discount = row.money("line_discount")

        order = order_for(number) if number else None
        if number and order is None:
            row.error(
                "order_number",
                "UNKNOWN_ORDER",
                f"Order {number} does not exist. Import it with orders.csv first (BR-605).",
                number,
            )
        product = products.get(sku) if sku else None
        if sku and product is None:
            row.error("sku", "UNKNOWN_SKU", f"SKU {sku} does not exist (BR-605).", sku)
        existing = lines[number].get(line_number) if order and number and line_number else None
        if not parsed.has_column("line_discount") and existing is not None:
            line_discount = existing.line_discount
        discount = line_discount if line_discount is not None else _ZERO
        if quantity is not None and unit_price is not None and discount > quantity * unit_price:
            row.error(
                "line_discount",
                "LINE_DISCOUNT_EXCEEDS_LINE",
                f"line_discount {discount} exceeds quantity × unit_price "
                f"({quantity * unit_price}).",
                str(discount),
            )

        if (
            order is None
            or product is None
            or number is None
            or line_number is None
            or sku is None
            or quantity is None
            or unit_price is None
        ):
            plans.append(RowPlan(parsed_row.row_number, key or "", *classify(row, None, [])))
            continue
        line = orders.OrderLineSnapshot(
            line_number=line_number,
            product_id=product.id,
            sku=sku,
            quantity=quantity,
            unit_price=unit_price,
            line_discount=discount,
        )
        reason = orders.line_lock_reason(order, existing, line)
        if reason:
            row.error(
                None,
                "ORDER_LINE_LOCKED",
                f"{reason} (order {number} is {order.fulfillment_status.value}, BR-609).",
            )
        changed = _changes(existing, line) if existing is not None else []
        action, fields = classify(row, existing, changed)
        payload = None if row.has_errors else OrderItemRow(order_number=number, line=line)
        plans.append(RowPlan(parsed_row.row_number, key or "", action, fields, payload))
    return ValidationResult(plans=plans, issues=collector.finalize())


def _changes(existing: OrderItem, line: orders.OrderLineSnapshot) -> list[str]:
    pairs = (
        ("sku", existing.sku, line.sku),
        ("quantity", existing.quantity, line.quantity),
        ("unit_price", existing.unit_price, line.unit_price),
        ("line_discount", existing.line_discount, line.line_discount),
    )
    changed = [name for name, old, new in pairs if old != new]
    if existing.product_id != line.product_id and "sku" not in changed:
        changed.append("sku")
    return changed
