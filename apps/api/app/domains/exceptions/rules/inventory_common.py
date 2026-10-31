"""Inventory conditions shared by the four inventory rules (BR-401, BR-402, BR-403).

The conditions are mutually exclusive per product. ``inventory_condition`` classifies a product
top-down and each inventory rule emits a finding only when the classification is its own type, so
precedence holds even when a run executes a subset of the rules.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domains.catalog.models import ProductStatus
from app.domains.exceptions.models import EntityType, ExceptionType
from app.domains.exceptions.rules.base import EntityRef, source
from app.domains.exceptions.snapshot import DemandLine, ProductFacts
from app.domains.inventory.calculations import avg_daily_units, days_of_cover

INVENTORY_PRECEDENCE: tuple[ExceptionType, ...] = (
    ExceptionType.INVENTORY_OVERSOLD,
    ExceptionType.INVENTORY_OVERSELL_RISK,
    ExceptionType.INVENTORY_OUT_OF_STOCK,
    ExceptionType.INVENTORY_BELOW_REORDER_POINT,
)

NEGATIVE_ON_HAND_NOTE = (
    "Inventory rules (oversold, oversell risk, out of stock, below reorder point) are suppressed "
    "for this product until on_hand is corrected, because the stock figure is invalid."
)
_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


def inventory_condition(product: ProductFacts, pending_demand: int) -> ExceptionType | None:
    """The single inventory condition of a product, evaluated top-down (BR-401).

    Only ACTIVE products are classified. A negative on_hand is invalid input: it is reported as
    DATA_NEGATIVE_ON_HAND and suppresses every inventory rule for the product.
    """
    if product.status is not ProductStatus.ACTIVE or product.on_hand < 0:
        return None
    available = product.available
    if available < 0:
        return ExceptionType.INVENTORY_OVERSOLD
    if pending_demand > available:  # BR-403
        return ExceptionType.INVENTORY_OVERSELL_RISK
    if available == 0:
        return ExceptionType.INVENTORY_OUT_OF_STOCK
    if product.reorder_point > 0 and available <= product.reorder_point:  # BR-140
        return ExceptionType.INVENTORY_BELOW_REORDER_POINT
    return None


@dataclass(frozen=True)
class LineAllocation:
    line: DemandLine
    covered: int
    uncovered: int


def allocate_fifo(on_hand: int, lines: tuple[DemandLine, ...]) -> list[LineAllocation]:
    """BR-402: allocate on_hand to committed lines in FIFO order of paid_at.

    Ties are broken by order_number (then line_number). Lines that cannot be fully covered are
    the affected lines.
    """
    ordered = sorted(
        lines,
        key=lambda line: (line.paid_at or _FAR_FUTURE, line.order_number, line.line_number),
    )
    remaining = max(on_hand, 0)
    allocations: list[LineAllocation] = []
    for line in ordered:
        covered = min(remaining, line.quantity)
        remaining -= covered
        allocations.append(LineAllocation(line, covered, line.quantity - covered))
    return allocations


def product_ref(product: ProductFacts) -> EntityRef:
    return EntityRef(EntityType.PRODUCT, product.id, product.sku)


def balance_source(product: ProductFacts) -> dict[str, str]:
    return source("inventory_balance", product.id, f"Inventory balance of {product.sku}")


def product_source(product: ProductFacts) -> dict[str, str]:
    return source("product", product.id, f"{product.sku} · {product.name}")


def supplier_source(product: ProductFacts) -> dict[str, str] | None:
    if product.supplier_id is None:
        return None
    return source("supplier", product.supplier_id, product.supplier_name or "Supplier")


def order_source(order_id: uuid.UUID, order_number: str) -> dict[str, str]:
    return source("order", order_id, f"Order {order_number}")


def velocity(product: ProductFacts, window_days: int) -> Decimal:
    """BR-150 average daily units (an estimate, BR-152)."""
    return avg_daily_units(product.units_sold_in_window, max(window_days, 1))


def cover_days(product: ProductFacts, window_days: int) -> Decimal | None:
    """BR-151 days of cover; None means "not enough sales history"."""
    return days_of_cover(product.available, velocity(product, window_days))


def supplier_phrase(product: ProductFacts) -> str:
    """Supplier name with its lead time, e.g. "Harbor Ceramics (lead time 14 days)".

    Without a supplier the text is "your supplier"; without a lead time the clause is left out.
    """
    name = product.supplier_name or "your supplier"
    if product.supplier_name and product.lead_time_days is not None:
        return f"{name} (lead time {product.lead_time_days} days)"
    return name
