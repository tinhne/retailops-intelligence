"""Inventory formulas (BUSINESS_RULES.md §2)."""

from decimal import Decimal

import pytest

from app.domains.inventory.calculations import (
    StockHealth,
    available,
    avg_daily_units,
    classify_health,
    days_of_cover,
    movement_deltas,
)
from app.domains.inventory.models import MovementType as M

FACTOR = Decimal("1.25")


def test_br101_available_does_not_subtract_pending_demand() -> None:
    assert available(on_hand=10, reserved=4) == 6
    assert available(on_hand=3, reserved=5) == -2  # BR-102: negative is reported, not clamped


@pytest.mark.parametrize(
    ("avail", "rop", "expected"),
    [
        (-1, 10, StockHealth.OVERSOLD),
        (0, 10, StockHealth.OUT_OF_STOCK),
        (10, 10, StockHealth.BELOW_REORDER_POINT),
        (11, 10, StockHealth.APPROACHING_REORDER_POINT),
        (13, 10, StockHealth.APPROACHING_REORDER_POINT),  # ceil(12.5) = 13
        (14, 10, StockHealth.HEALTHY),
        (1, 0, StockHealth.HEALTHY),  # BR-140
    ],
)
def test_health_classification_boundaries(avail: int, rop: int, expected: StockHealth) -> None:
    assert classify_health(avail, rop, FACTOR) is expected


def test_br150_velocity_and_br151_days_of_cover() -> None:
    daily = avg_daily_units(units_sold=56, window_days=28)
    assert daily == Decimal("2.00")
    assert days_of_cover(9, daily) == Decimal("4.5")
    assert days_of_cover(5, Decimal("0")) is None  # not enough sales history


@pytest.mark.parametrize(
    ("movement", "qty", "expected"),
    [
        (M.RECEIPT, 30, (30, -20)),  # receipt consumes incoming down to zero
        (M.INCOMING_EXPECTED, 15, (0, 15)),
        (M.INCOMING_CANCELLED, 50, (0, -20)),
        (M.DAMAGE, 2, (-2, 0)),
        (M.SHRINKAGE, 1, (-1, 0)),
        (M.SHIPMENT, 3, (-3, 0)),
        (M.RETURN_RESTOCK, 1, (1, 0)),
        (M.CORRECTION, -4, (-4, 0)),
        (M.CYCLE_COUNT, 12, (2, 0)),  # absolute count vs on-hand 10 at that time
    ],
)
def test_br111_movement_deltas(movement: M, qty: int, expected: tuple[int, int]) -> None:
    deltas = movement_deltas(movement, qty, on_hand_at_occurrence=10, current_incoming=20)
    assert (deltas.on_hand_delta, deltas.incoming_delta) == expected


@pytest.mark.parametrize(
    ("movement", "qty"), [(M.CYCLE_COUNT, -1), (M.CORRECTION, 0), (M.RECEIPT, 0), (M.DAMAGE, -2)]
)
def test_invalid_movement_quantities(movement: M, qty: int) -> None:
    with pytest.raises(ValueError, match=r"."):
        movement_deltas(movement, qty, on_hand_at_occurrence=0, current_incoming=0)
