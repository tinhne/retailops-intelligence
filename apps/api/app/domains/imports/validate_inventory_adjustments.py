"""inventory_adjustments.csv: append-only, idempotent by reference (BR-110..113).

Quantity semantics come from ``inventory.calculations.movement_deltas``. A reference that is
already in the ledger is reported as ``ALREADY_APPLIED`` and the row is a no-op (BR-112). A cycle
count older than the product's latest count is a ``STALE_CYCLE_COUNT`` error (BR-113), checked
against the ledger and against counts earlier in the same file.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.catalog import service as catalog
from app.domains.imports.parsing import ParsedFile
from app.domains.imports.validation import (
    IssueCollector,
    RowAction,
    RowPlan,
    RowReader,
    ValidationContext,
    ValidationResult,
    classify,
    duplicate_check,
)
from app.domains.inventory import service as inventory
from app.domains.inventory.calculations import movement_deltas
from app.domains.inventory.models import InventoryBalance, MovementType

ADJUSTMENT_TYPES = tuple(t for t in MovementType if t is not MovementType.SHIPMENT)
# Shipment movements use ``order_item:{id}`` in the same per-store reference space (BR-131).
RESERVED_REFERENCE_PREFIX = "order_item:"


@dataclass(frozen=True)
class AdjustmentRow:
    reference: str
    product_id: uuid.UUID
    movement_type: MovementType
    quantity: int
    occurred_at: datetime
    expected_at: datetime | None
    note: str | None


def validate(
    db: Session, ctx: ValidationContext, parsed: ParsedFile
) -> ValidationResult[AdjustmentRow]:
    collector = IssueCollector(ctx.timezone)
    products = catalog.find_products_by_sku(
        db, ctx.store_id, (row.values.get("sku", "") for row in parsed.rows)
    )
    latest_count = _last_cycle_counts(db, ctx.store_id, [p.id for p in products.values()])
    seen: dict[str, int] = {}
    plans: list[RowPlan[AdjustmentRow]] = []

    for parsed_row in parsed.rows:
        row = RowReader(parsed_row, ctx, collector)
        reference = row.text("reference", max_length=100, required=True)
        if reference is not None and reference.lower().startswith(RESERVED_REFERENCE_PREFIX):
            row.error(
                "reference",
                "RESERVED_REFERENCE",
                "References starting with 'order_item:' are reserved for system shipment "
                "movements.",
                reference,
            )
            reference = None
        duplicate_check(row, seen, reference, "reference", "Reference")
        if (
            reference
            and not row.has_errors
            and inventory.reference_exists(db, ctx.store_id, reference)
        ):
            row.warning(
                "reference",
                "ALREADY_APPLIED",
                f"Reference {reference} is already in the inventory ledger; the row has no "
                "effect (BR-112).",
                reference,
            )
            plans.append(RowPlan(parsed_row.row_number, reference, RowAction.UNCHANGED))
            continue

        sku = row.text("sku", max_length=64, required=True)
        movement_type = row.enum(
            "adjustment_type", MovementType, required=True, allowed=ADJUSTMENT_TYPES
        )
        quantity = row.integer("quantity", required=True, minimum=None)
        occurred_at = row.timestamp("occurred_at", required=True)
        expected_at = row.timestamp("expected_at")
        note = row.text("note", max_length=500)

        product = products.get(sku) if sku else None
        if sku and product is None:
            row.error("sku", "UNKNOWN_SKU", f"SKU {sku} does not exist.", sku)
        if movement_type is not None and quantity is not None:
            _check_quantity(row, movement_type, quantity)
        if movement_type is MovementType.CYCLE_COUNT and product and occurred_at:
            latest = latest_count.get(product.id)
            if latest is not None and occurred_at < latest:
                row.error(
                    "occurred_at",
                    "STALE_CYCLE_COUNT",
                    f"A newer cycle count ({latest.isoformat()}) already exists for {sku}; a "
                    "count older than the latest one is rejected (BR-113).",
                    row.raw("occurred_at"),
                )

        if (
            row.has_errors
            or reference is None
            or product is None
            or movement_type is None
            or quantity is None
            or occurred_at is None
        ):
            plans.append(
                RowPlan(parsed_row.row_number, row.raw("reference"), *classify(row, None, []))
            )
            continue
        if movement_type is MovementType.CYCLE_COUNT:
            latest_count[product.id] = max(occurred_at, latest_count.get(product.id, occurred_at))
        payload = AdjustmentRow(
            reference=reference,
            product_id=product.id,
            movement_type=movement_type,
            quantity=quantity,
            occurred_at=occurred_at,
            expected_at=expected_at,
            note=note,
        )
        plans.append(RowPlan(parsed_row.row_number, reference, RowAction.CREATE, (), payload))
    return ValidationResult(plans=plans, issues=collector.finalize())


def _check_quantity(row: RowReader, movement_type: MovementType, quantity: int) -> None:
    """Quantity semantics per type (BR-111), delegated to ``movement_deltas``."""
    if quantity < 0 and movement_type is not MovementType.CORRECTION:
        row.error(
            "quantity",
            "NEGATIVE_VALUE",
            f"{movement_type.value} quantity must not be negative; the sign is implied by the type "
            "(use CORRECTION for a signed delta).",
            str(quantity),
        )
        return
    try:
        movement_deltas(movement_type, quantity, on_hand_at_occurrence=0, current_incoming=0)
    except ValueError as exc:
        row.error("quantity", "INVALID_INTEGER", f"{exc}.", str(quantity))


def _last_cycle_counts(
    db: Session, store_id: uuid.UUID, product_ids: list[uuid.UUID]
) -> dict[uuid.UUID, datetime]:
    """Latest cycle count per product (read-only; the inventory service has no batch reader)."""
    if not product_ids:
        return {}
    rows = db.execute(
        select(InventoryBalance.product_id, InventoryBalance.last_cycle_count_at).where(
            InventoryBalance.store_id == store_id,
            InventoryBalance.product_id.in_(product_ids),
            InventoryBalance.last_cycle_count_at.is_not(None),
        )
    ).all()
    return {product_id: counted_at for product_id, counted_at in rows if counted_at is not None}
