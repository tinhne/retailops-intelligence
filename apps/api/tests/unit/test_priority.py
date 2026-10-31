"""Priority score, bands, breakdown and due date (PRIORITY_MODEL.md)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domains.exceptions.models import PriorityBand, Severity
from app.domains.exceptions.priority import (
    DEFAULT_WEIGHTS,
    FORMULA_VERSION,
    PriorityInputs,
    PriorityWeights,
    band_for,
    compute_due_at,
    compute_priority,
    exposure_points,
)
from app.domains.identity.models import DEFAULT_PRIORITY_WEIGHTS
from tests.factories_exceptions import T0

CAP = Decimal("5000")


def _score(
    severity: Severity,
    *,
    orders: int = 0,
    exposure: str = "0",
    deadline_in: timedelta | None = None,
    open_for: timedelta = timedelta(0),
    weights: PriorityWeights = DEFAULT_WEIGHTS,
) -> tuple[int, PriorityBand, dict[str, int]]:
    as_of = T0
    result = compute_priority(
        PriorityInputs(
            severity=severity,
            affected_order_count=orders,
            exposure_amount=Decimal(exposure),
            deadline_at=as_of + deadline_in if deadline_in is not None else None,
            first_detected_at=as_of - open_for,
        ),
        weights=weights,
        exposure_cap=CAP,
        as_of=as_of,
    )
    points = {c["key"]: c["points"] for c in result.breakdown["components"]}
    return result.score, result.band, points


def test_worked_example_oversold_sku() -> None:
    """4 committed orders, 600.00 at risk, nearest ship-by in 10 h, new → 81 (P1)."""
    score, band, points = _score(
        Severity.CRITICAL, orders=4, exposure="600.00", deadline_in=timedelta(hours=10)
    )
    assert points == {
        "severity": 50,
        "affected_orders": 12,
        "exposure": 11,
        "deadline": 8,
        "age": 0,
    }
    assert (score, band) == (81, PriorityBand.P1)


def test_worked_example_overdue_order() -> None:
    """Overdue by 30 h, total 120.00, detected when it became overdue (1 whole day) → 60 (P2)."""
    score, band, points = _score(
        Severity.HIGH,
        orders=1,
        exposure="120.00",
        deadline_in=-timedelta(hours=30),
        open_for=timedelta(hours=30),
    )
    assert points == {"severity": 35, "affected_orders": 3, "exposure": 8, "deadline": 12, "age": 2}
    assert (score, band) == (60, PriorityBand.P2)


def test_worked_example_below_reorder_point() -> None:
    """Medium severity, no orders, 3 days open → 26 (P4)."""
    score, band, points = _score(Severity.MEDIUM, open_for=timedelta(days=3))
    assert points == {"severity": 20, "affected_orders": 0, "exposure": 0, "deadline": 0, "age": 6}
    assert (score, band) == (26, PriorityBand.P4)


def test_worked_example_refund_pending() -> None:
    """Refund pending on 89.90, 26 h after cancellation (deadline passed 2 h ago) → 58 (P2)."""
    score, band, points = _score(
        Severity.HIGH, orders=1, exposure="89.90", deadline_in=-timedelta(hours=2)
    )
    assert points == {"severity": 35, "affected_orders": 3, "exposure": 8, "deadline": 12, "age": 0}
    assert (score, band) == (58, PriorityBand.P2)


@pytest.mark.parametrize(
    ("value", "points"),
    [
        ("0", 0),
        ("-5", 0),
        ("0.01", 0),
        ("89.90", 8),
        ("108.00", 8),
        ("120.00", 8),
        ("230.04", 10),
        ("600.00", 11),  # 15 × log10(601) / log10(5001) = 11.27
        ("5000.00", 15),
        ("250000.00", 15),  # clamped to the cap
    ],
)
def test_exposure_component_is_logarithmic_and_clamped(value: str, points: int) -> None:
    assert exposure_points(Decimal(value), CAP, 15) == points


@pytest.mark.parametrize(
    ("deadline_in", "points"),
    [
        (None, 0),
        (-timedelta(hours=1), 12),
        (timedelta(0), 12),  # deadline_at ≤ as_of counts as passed
        (timedelta(seconds=1), 8),
        (timedelta(hours=24), 8),
        (timedelta(hours=24, seconds=1), 4),
        (timedelta(hours=72), 4),
        (timedelta(hours=72, seconds=1), 0),
    ],
)
def test_deadline_component_boundaries(deadline_in: timedelta | None, points: int) -> None:
    _, _, breakdown = _score(Severity.LOW, deadline_in=deadline_in)
    assert breakdown["deadline"] == points


@pytest.mark.parametrize(
    ("open_for", "points"),
    [
        (timedelta(hours=23, minutes=59), 0),
        (timedelta(days=1), 2),
        (timedelta(days=3, hours=23), 6),
        (timedelta(days=4), 8),
        (timedelta(days=30), 8),
    ],
)
def test_age_component_counts_whole_days_and_is_capped(open_for: timedelta, points: int) -> None:
    _, _, breakdown = _score(Severity.LOW, open_for=open_for)
    assert breakdown["age"] == points


def test_affected_orders_component_is_capped() -> None:
    assert _score(Severity.LOW, orders=5)[2]["affected_orders"] == 15
    assert _score(Severity.LOW, orders=9)[2]["affected_orders"] == 15


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, PriorityBand.P1),
        (70, PriorityBand.P1),
        (69, PriorityBand.P2),
        (50, PriorityBand.P2),
        (49, PriorityBand.P3),
        (30, PriorityBand.P3),
        (29, PriorityBand.P4),
        (0, PriorityBand.P4),
    ],
)
def test_priority_bands(score: int, band: PriorityBand) -> None:
    assert band_for(score) is band


def test_maximum_score_is_100_and_breakdown_explains_each_component() -> None:
    result = compute_priority(
        PriorityInputs(
            severity=Severity.CRITICAL,
            affected_order_count=10,
            exposure_amount=Decimal("9999"),
            deadline_at=T0 - timedelta(hours=1),
            first_detected_at=T0 - timedelta(days=10),
        ),
        weights=DEFAULT_WEIGHTS,
        exposure_cap=CAP,
        as_of=T0,
    )
    assert result.score == 100
    breakdown = result.breakdown
    assert breakdown["total"] == 100
    assert breakdown["band"] == "P1"
    assert breakdown["formula_version"] == FORMULA_VERSION
    assert [c["key"] for c in breakdown["components"]] == [
        "severity",
        "affected_orders",
        "exposure",
        "deadline",
        "age",
    ]
    assert [c["max_points"] for c in breakdown["components"]] == [50, 15, 15, 12, 8]
    for component in breakdown["components"]:
        assert set(component) == {"key", "label", "points", "max_points", "explanation"}
        assert component["explanation"]
    exposure = breakdown["components"][2]["explanation"]
    assert "value at risk" in exposure
    assert "loss" in exposure


def test_custom_weights_from_store_settings_are_merged_over_defaults() -> None:
    weights = PriorityWeights.from_settings(
        {**DEFAULT_PRIORITY_WEIGHTS, "severity": {"HIGH": 40}, "age_cap": 4, "bogus": "x"}
    )
    assert weights.severity[Severity.HIGH] == 40
    assert weights.severity[Severity.CRITICAL] == 50  # default kept
    assert weights.age_cap == 4
    malformed = PriorityWeights.from_settings({"affected_orders_cap": "lots", "age_cap": -3})
    assert malformed.affected_orders_cap == 15
    assert malformed.age_cap == 0
    score, _, points = _score(Severity.HIGH, open_for=timedelta(days=5), weights=weights)
    assert points["severity"] == 40
    assert points["age"] == 4
    assert score == 44


@pytest.mark.parametrize(
    ("severity", "hours"),
    [(Severity.CRITICAL, 4), (Severity.HIGH, 24), (Severity.MEDIUM, 72), (Severity.LOW, 168)],
)
def test_due_date_from_response_hours(severity: Severity, hours: int) -> None:
    due = compute_due_at(severity, T0, None)
    assert due.due_at == T0 + timedelta(hours=hours)
    assert due.basis == "SEVERITY"


def test_due_date_uses_an_earlier_future_business_deadline() -> None:
    earlier = compute_due_at(Severity.HIGH, T0, T0 + timedelta(hours=10))
    assert (earlier.due_at, earlier.basis) == (T0 + timedelta(hours=10), "DEADLINE")
    later = compute_due_at(Severity.HIGH, T0, T0 + timedelta(hours=30))
    assert (later.due_at, later.basis) == (T0 + timedelta(hours=24), "SEVERITY")
    passed = compute_due_at(Severity.HIGH, T0, T0 - timedelta(hours=1))
    assert (passed.due_at, passed.basis) == (T0 + timedelta(hours=24), "SEVERITY")
    assert earlier.as_json()["anchor_at"] == T0.isoformat()
