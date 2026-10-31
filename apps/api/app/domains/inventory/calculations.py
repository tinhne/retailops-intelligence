"""Pure inventory calculations (BUSINESS_RULES.md §2). No I/O; fully unit-tested."""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.domains.inventory.models import MovementType


class StockHealth(StrEnum):
    OVERSOLD = "OVERSOLD"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    BELOW_REORDER_POINT = "BELOW_REORDER_POINT"
    APPROACHING_REORDER_POINT = "APPROACHING_REORDER_POINT"
    HEALTHY = "HEALTHY"


def available(on_hand: int, reserved: int) -> int:
    """BR-101. Pending demand is deliberately not subtracted."""
    return on_hand - reserved


def approaching_threshold(reorder_point: int, factor: Decimal) -> int:
    return math.ceil(Decimal(reorder_point) * factor)


def classify_health(available_qty: int, reorder_point: int, factor: Decimal) -> StockHealth:
    """§2.5, evaluated top-down. BR-140: reorder_point 0 never yields reorder-based health."""
    if available_qty < 0:
        return StockHealth.OVERSOLD
    if available_qty == 0:
        return StockHealth.OUT_OF_STOCK
    if reorder_point > 0 and available_qty <= reorder_point:
        return StockHealth.BELOW_REORDER_POINT
    if reorder_point > 0 and available_qty <= approaching_threshold(reorder_point, factor):
        return StockHealth.APPROACHING_REORDER_POINT
    return StockHealth.HEALTHY


def avg_daily_units(units_sold: int, window_days: int) -> Decimal:
    """BR-150: simple moving average over the velocity window (an estimate)."""
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    return (Decimal(units_sold) / Decimal(window_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def days_of_cover(available_qty: int, daily_units: Decimal) -> Decimal | None:
    """BR-151. None means "not enough sales history" (no velocity)."""
    if daily_units <= 0:
        return None
    return (Decimal(max(available_qty, 0)) / daily_units).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


@dataclass(frozen=True)
class MovementDeltas:
    on_hand_delta: int
    incoming_delta: int


_NEGATIVE_TYPES = frozenset({MovementType.DAMAGE, MovementType.SHRINKAGE, MovementType.SHIPMENT})
_POSITIVE_TYPES = frozenset({MovementType.RETURN_RESTOCK})


def movement_deltas(
    movement_type: MovementType,
    quantity: int,
    *,
    on_hand_at_occurrence: int,
    current_incoming: int,
) -> MovementDeltas:
    """Translate an adjustment into ledger deltas (BR-111).

    ``quantity`` semantics: CYCLE_COUNT is an absolute count (≥0); CORRECTION is a signed non-zero
    delta; every other type is a positive magnitude whose sign is implied by the type.
    ``on_hand_at_occurrence`` is on-hand as of the movement's ``occurred_at`` (only CYCLE_COUNT
    uses it, so a late-imported count does not erase movements recorded after it).
    """
    if movement_type is MovementType.CYCLE_COUNT:
        if quantity < 0:
            raise ValueError("A cycle count cannot be negative")
        return MovementDeltas(quantity - on_hand_at_occurrence, 0)
    if movement_type is MovementType.CORRECTION:
        if quantity == 0:
            raise ValueError("A correction must be non-zero")
        return MovementDeltas(quantity, 0)
    if quantity <= 0:
        raise ValueError(f"{movement_type.value} quantity must be positive")
    if movement_type is MovementType.RECEIPT:
        return MovementDeltas(quantity, -min(quantity, current_incoming))
    if movement_type is MovementType.INCOMING_EXPECTED:
        return MovementDeltas(0, quantity)
    if movement_type is MovementType.INCOMING_CANCELLED:
        return MovementDeltas(0, -min(quantity, current_incoming))
    if movement_type in _NEGATIVE_TYPES:
        return MovementDeltas(-quantity, 0)
    if movement_type in _POSITIVE_TYPES:
        return MovementDeltas(quantity, 0)
    raise ValueError(f"Unsupported movement type {movement_type}")  # pragma: no cover
