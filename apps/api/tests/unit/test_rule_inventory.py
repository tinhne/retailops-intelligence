"""Inventory rules (EXCEPTION_CATALOG.md: INV-OVERSOLD@1, INV-OVERSELL-RISK@1, INV-OUT-OF-STOCK@1,
INV-BELOW-ROP@1) and their precedence (BR-401). Pure unit tests on hand-built snapshots."""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.domains.catalog.models import ProductStatus
from app.domains.exceptions.models import ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.rules import (
    inventory_below_reorder_point,
    inventory_out_of_stock,
    inventory_oversell_risk,
    inventory_oversold,
)
from app.domains.exceptions.rules.base import Finding, material_view
from app.domains.exceptions.rules.inventory_common import allocate_fifo, inventory_condition
from app.domains.exceptions.rules.registry import RULES
from app.domains.exceptions.snapshot import EvaluationSnapshot
from app.domains.orders.models import OrderStatus
from tests.factories_exceptions import (
    SETTINGS,
    T0,
    facts_line,
    facts_product,
    snapshot,
)

INVENTORY_RULES = (
    inventory_oversold.evaluate,
    inventory_oversell_risk.evaluate,
    inventory_out_of_stock.evaluate,
    inventory_below_reorder_point.evaluate,
)


def _facts(finding: Finding) -> dict[str, object]:
    return {f["key"]: f["value"] for f in finding.evidence["facts"]}


def _all_inventory(snap: EvaluationSnapshot) -> list[Finding]:
    return [f for rule in INVENTORY_RULES for f in rule(snap, SETTINGS, T0)]


# --- INV-OVERSOLD@1 ----------------------------------------------------------------------------


def test_oversold_fires_at_available_minus_one_not_at_zero() -> None:
    """INV-OVERSOLD@1: available < 0. available = 0 is out of stock, never oversold (BR-102)."""
    p_short = facts_product("SKU-A", on_hand=2, reserved=3)
    p_zero = facts_product("SKU-B", on_hand=3, reserved=3)
    snap = snapshot(
        products=[p_short, p_zero],
        committed=[facts_line(p_short, "1001", 3), facts_line(p_zero, "1002", 3)],
    )

    findings = inventory_oversold.evaluate(snap, SETTINGS, T0)

    assert [f.primary_entity.label for f in findings] == ["SKU-A"]
    finding = findings[0]
    assert finding.rule_id == "INV-OVERSOLD@1"
    assert finding.exception_type is ExceptionType.INVENTORY_OVERSOLD
    assert finding.category is ExceptionCategory.INVENTORY
    assert finding.severity is Severity.CRITICAL
    assert finding.dedup_key == f"INVENTORY_OVERSOLD:product:{p_short.id}"
    facts = _facts(finding)
    assert facts["available"] == -1
    assert facts["shortage"] == 1


def test_oversold_fifo_allocation_by_paid_at_with_ties_broken_by_order_number() -> None:
    """BR-402: on_hand is allocated FIFO by paid_at, ties by order_number; uncovered lines are
    affected, and exposure = Σ uncovered × line unit price (BR-404)."""
    p = facts_product("SKU-A", on_hand=5, reserved=9)
    early = facts_line(p, "1003", 2, paid_at=T0 - timedelta(hours=5), unit_price="10.00")
    tie_b = facts_line(p, "1002", 3, paid_at=T0 - timedelta(hours=2), unit_price="10.00")
    tie_a = facts_line(p, "1001", 2, paid_at=T0 - timedelta(hours=2), unit_price="10.00")
    late = facts_line(p, "1000", 2, paid_at=T0 - timedelta(hours=1), unit_price="25.50")

    allocations = allocate_fifo(5, (late, tie_b, early, tie_a))

    assert [(a.line.order_number, a.covered, a.uncovered) for a in allocations] == [
        ("1003", 2, 0),
        ("1001", 2, 0),  # tie on paid_at: 1001 before 1002
        ("1002", 1, 2),
        ("1000", 0, 2),
    ]
    snap = snapshot(products=[p], committed=[late, tie_b, early, tie_a])
    finding = inventory_oversold.evaluate(snap, SETTINGS, T0)[0]
    assert [o.label for o in finding.related_entities] == ["1002", "1000"]
    assert finding.affected_order_count == 2
    assert finding.exposure_amount == Decimal("71.00")  # 2 × 10.00 + 2 × 25.50
    affected = finding.evidence["records"]["affected_orders"]
    assert [(r["order_number"], r["uncovered_quantity"]) for r in affected] == [
        ("1002", 2),
        ("1000", 2),
    ]
    assert affected[0]["source"]["type"] == "order"


def test_oversold_deadline_is_earliest_ship_by_among_affected_orders_only() -> None:
    p = facts_product("SKU-A", on_hand=1, reserved=3)
    covered = facts_line(
        p, "1001", 1, paid_at=T0 - timedelta(hours=9), ship_by=T0 + timedelta(hours=1)
    )
    affected_late = facts_line(
        p, "1002", 1, paid_at=T0 - timedelta(hours=8), ship_by=T0 + timedelta(hours=30)
    )
    affected_soon = facts_line(
        p, "1003", 1, paid_at=T0 - timedelta(hours=7), ship_by=T0 + timedelta(hours=10)
    )
    snap = snapshot(products=[p], committed=[covered, affected_late, affected_soon])

    finding = inventory_oversold.evaluate(snap, SETTINGS, T0)[0]

    assert finding.deadline_at == T0 + timedelta(hours=10)


def test_oversold_evidence_carries_source_references_and_calculation() -> None:
    p = facts_product(
        "SKU-A", on_hand=4, reserved=6, incoming=10, incoming_eta=T0 + timedelta(days=3)
    )
    snap = snapshot(products=[p], committed=[facts_line(p, "1001", 6)])

    finding = inventory_oversold.evaluate(snap, SETTINGS, T0)[0]

    facts = {f["key"]: f for f in finding.evidence["facts"]}
    assert facts["on_hand"]["source"] == {
        "type": "inventory_balance",
        "id": str(p.id),
        "label": "Inventory balance of SKU-A",
    }
    assert facts["incoming"]["value"] == 10
    assert facts["incoming_eta"]["value"] == (T0 + timedelta(days=3)).isoformat()
    calc = finding.calculation
    assert calc["inputs"] == {"on_hand": 4, "reserved": 6, "committed_lines": 1}
    assert calc["outputs"]["available"] == -2
    assert calc["outputs"]["exposure_amount"] == "40.00"
    assert "BR-402" in " ".join(calc["formulas"])
    assert finding.recommended_action.startswith("Confirm physical stock with a cycle count.")
    assert finding.title == "Oversold: SKU-A (Stoneware Mug) short by 2 units across 1 order"


def test_inactive_products_are_never_classified() -> None:
    for status in (ProductStatus.DRAFT, ProductStatus.ARCHIVED):
        p = facts_product("SKU-A", on_hand=0, reserved=2, status=status)
        snap = snapshot(products=[p], committed=[facts_line(p, "1001", 2)])
        assert _all_inventory(snap) == []


def test_negative_on_hand_suppresses_every_inventory_rule() -> None:
    """BR-402a: on_hand < 0 is invalid input, only DQ-NEGATIVE-ON-HAND@1 fires. Available is −3
    here, which would otherwise be INV-OVERSOLD@1."""
    p = facts_product("SKU-A", on_hand=-1, reserved=2, reorder_point=10)
    snap = snapshot(
        products=[p],
        committed=[facts_line(p, "1001", 2)],
        pending=[facts_line(p, "1002", 5, status=OrderStatus.PAYMENT_PENDING, paid_at=None)],
    )

    assert inventory_condition(p, 5) is None
    assert _all_inventory(snap) == []


# --- INV-OVERSELL-RISK@1 -----------------------------------------------------------------------


def test_oversell_risk_requires_pending_demand_strictly_above_available() -> None:
    """BR-403: available ≥ 0 and pending_demand > available."""
    p_equal = facts_product("SKU-A", on_hand=3, reserved=0, reorder_point=0)
    p_above = facts_product("SKU-B", on_hand=3, reserved=0, reorder_point=0, unit_price="12.50")
    pending = [
        facts_line(p_equal, "2001", 3, status=OrderStatus.CREATED, paid_at=None),
        facts_line(p_above, "2002", 2, status=OrderStatus.PAYMENT_PENDING, paid_at=None),
        facts_line(p_above, "2003", 3, status=OrderStatus.CREATED, paid_at=None),
    ]
    snap = snapshot(products=[p_equal, p_above], pending=pending)

    findings = inventory_oversell_risk.evaluate(snap, SETTINGS, T0)

    assert [f.primary_entity.label for f in findings] == ["SKU-B"]
    finding = findings[0]
    assert finding.severity is Severity.HIGH
    facts = _facts(finding)
    assert (facts["available"], facts["pending_demand"], facts["potential_shortage"]) == (3, 5, 2)
    assert finding.exposure_amount == Decimal("25.00")  # 2 × current unit price 12.50
    assert finding.affected_order_count == 2
    assert finding.deadline_at is None


def test_oversell_risk_lists_pending_orders_oldest_first() -> None:
    p = facts_product("SKU-A", on_hand=1, reorder_point=0)
    newer = facts_line(
        p, "2001", 1, status=OrderStatus.CREATED, paid_at=None, placed_at=T0 - timedelta(hours=1)
    )
    older = facts_line(
        p, "2002", 1, status=OrderStatus.CREATED, paid_at=None, placed_at=T0 - timedelta(hours=3)
    )
    snap = snapshot(products=[p], pending=[newer, older])

    finding = inventory_oversell_risk.evaluate(snap, SETTINGS, T0)[0]

    rows = finding.evidence["records"]["pending_orders"]
    assert [r["order_number"] for r in rows] == ["2002", "2001"]
    assert [o.label for o in finding.related_entities] == ["2002", "2001"]


def test_oversell_risk_at_zero_available_takes_precedence_over_out_of_stock() -> None:
    p = facts_product("SKU-A", on_hand=0, reorder_point=5)
    snap = snapshot(
        products=[p],
        pending=[facts_line(p, "2001", 1, status=OrderStatus.CREATED, paid_at=None)],
    )

    findings = _all_inventory(snap)

    assert [f.exception_type for f in findings] == [ExceptionType.INVENTORY_OVERSELL_RISK]


# --- INV-OUT-OF-STOCK@1 ------------------------------------------------------------------------


@pytest.mark.parametrize(("units_sold", "severity"), [(1, Severity.HIGH), (0, Severity.MEDIUM)])
def test_out_of_stock_severity_depends_on_whether_the_product_is_selling(
    units_sold: int, severity: Severity
) -> None:
    p = facts_product("SKU-A", on_hand=4, reserved=4, units_sold=units_sold)
    snap = snapshot(products=[p], committed=[facts_line(p, "1001", 4)])

    findings = inventory_out_of_stock.evaluate(snap, SETTINGS, T0)

    assert len(findings) == 1
    assert findings[0].severity is severity
    assert findings[0].exposure_amount == Decimal("0.00")
    assert findings[0].affected_order_count == 0
    avg = next(f for f in findings[0].evidence["facts"] if f["key"] == "avg_daily_units")
    assert avg["estimate"] is True  # BR-152
    assert avg["volatile"] is True


def test_out_of_stock_applies_with_reorder_point_zero() -> None:
    p = facts_product("SKU-A", on_hand=0, reorder_point=0)
    assert [f.exception_type for f in _all_inventory(snapshot(products=[p]))] == [
        ExceptionType.INVENTORY_OUT_OF_STOCK
    ]


def test_out_of_stock_recommended_action_names_supplier_and_lead_time() -> None:
    with_supplier = facts_product("SKU-A", on_hand=0, lead_time_days=21)
    no_supplier = facts_product("SKU-B", on_hand=0, supplier_name=None, lead_time_days=None)
    no_lead = facts_product("SKU-C", on_hand=0, lead_time_days=None)
    snap = snapshot(products=[with_supplier, no_supplier, no_lead])

    actions = [f.recommended_action for f in inventory_out_of_stock.evaluate(snap, SETTINGS, T0)]

    assert actions == [
        "Reorder from Harbor Ceramics (lead time 21 days) or hide the listing until stock arrives.",
        "Reorder from your supplier or hide the listing until stock arrives.",
        "Reorder from Harbor Ceramics or hide the listing until stock arrives.",
    ]


# --- INV-BELOW-ROP@1 ---------------------------------------------------------------------------


@pytest.mark.parametrize(("available", "fires"), [(0, False), (1, True), (5, True), (6, False)])
def test_below_reorder_point_boundaries(available: int, fires: bool) -> None:
    """0 < available ≤ reorder_point (reorder point 5)."""
    p = facts_product("SKU-A", on_hand=available, reorder_point=5)
    findings = inventory_below_reorder_point.evaluate(snapshot(products=[p]), SETTINGS, T0)
    assert bool(findings) is fires


def test_reorder_point_zero_never_below_reorder_point() -> None:
    """BR-140."""
    p = facts_product("SKU-A", on_hand=1, reorder_point=0)
    assert inventory_below_reorder_point.evaluate(snapshot(products=[p]), SETTINGS, T0) == []


@pytest.mark.parametrize(
    ("units_sold", "lead_time", "severity"),
    [
        # 28 units / 28 days = 1.00/day → 4 days of cover with 4 available
        (28, 5, Severity.HIGH),  # 4 < 5
        (28, 4, Severity.MEDIUM),  # 4 = 4 is not < 4
        (0, 30, Severity.MEDIUM),  # no velocity → no days of cover
        (28, None, Severity.MEDIUM),  # no lead time
    ],
)
def test_below_reorder_point_severity_needs_velocity_and_lead_time(
    units_sold: int, lead_time: int | None, severity: Severity
) -> None:
    p = facts_product(
        "SKU-A", on_hand=4, reorder_point=5, units_sold=units_sold, lead_time_days=lead_time
    )
    finding = inventory_below_reorder_point.evaluate(snapshot(products=[p]), SETTINGS, T0)[0]
    assert finding.severity is severity


def test_below_reorder_point_suggested_quantity_and_action() -> None:
    """suggested = max(0, (reorder_quantity if set, else ROP × 2 − available) − incoming)."""
    base = facts_product("SKU-A", on_hand=3, reorder_point=10)  # 20 − 3 = 17
    with_qty = facts_product("SKU-B", on_hand=3, reorder_point=10, reorder_quantity=24, incoming=4)
    covered = facts_product(
        "SKU-C", on_hand=3, reorder_point=10, incoming=40, supplier_name=None, lead_time_days=None
    )
    snap = snapshot(products=[base, with_qty, covered])

    findings = inventory_below_reorder_point.evaluate(snap, SETTINGS, T0)

    assert [f.calculation["outputs"]["suggested"] for f in findings] == [17, 20, 0]
    assert findings[0].recommended_action == "Place a replenishment order for at least 17 units."
    assert findings[1].recommended_action == "Place a replenishment order for at least 20 units."
    assert findings[2].recommended_action == (
        "Incoming stock (40 units) covers the reorder point. Confirm the ETA with your supplier."
    )


# --- precedence (BR-401) -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("on_hand", "reserved", "pending", "expected"),
    [
        (2, 3, 5, ExceptionType.INVENTORY_OVERSOLD),
        (3, 1, 3, ExceptionType.INVENTORY_OVERSELL_RISK),
        (2, 2, 0, ExceptionType.INVENTORY_OUT_OF_STOCK),
        (4, 0, 4, ExceptionType.INVENTORY_BELOW_REORDER_POINT),
        (9, 0, 0, None),
    ],
)
def test_inventory_precedence_emits_one_finding_per_product(
    on_hand: int, reserved: int, pending: int, expected: ExceptionType | None
) -> None:
    """BR-401: OVERSOLD > OVERSELL_RISK > OUT_OF_STOCK > BELOW_REORDER_POINT."""
    p = facts_product("SKU-A", on_hand=on_hand, reserved=reserved, reorder_point=5)
    committed = [facts_line(p, "1001", reserved)] if reserved else []
    pending_lines = (
        [facts_line(p, "2001", pending, status=OrderStatus.CREATED, paid_at=None)]
        if pending
        else []
    )
    snap = snapshot(products=[p], committed=committed, pending=pending_lines)

    findings = _all_inventory(snap)

    assert [f.exception_type for f in findings] == ([expected] if expected else [])
    assert inventory_condition(p, pending) is expected


def test_rules_are_deterministic_and_material_view_ignores_volatile_facts() -> None:
    p = facts_product("SKU-A", on_hand=0, units_sold=3)
    first = inventory_out_of_stock.evaluate(snapshot(products=[p]), SETTINGS, T0)[0]
    again = inventory_out_of_stock.evaluate(snapshot(products=[p]), SETTINGS, T0)[0]
    assert first == again

    faster = facts_product("SKU-A", on_hand=0, units_sold=30)
    later = inventory_out_of_stock.evaluate(snapshot(products=[faster]), SETTINGS, T0)[0]
    assert later.evidence != first.evidence
    assert material_view(later.evidence) == material_view(first.evidence)


def test_registry_lists_all_nine_catalog_rules_once() -> None:
    assert [r.rule_id for r in RULES] == [
        "INV-OVERSOLD@1",
        "INV-OVERSELL-RISK@1",
        "INV-OUT-OF-STOCK@1",
        "INV-BELOW-ROP@1",
        "ORD-OVERDUE@1",
        "ORD-STALLED@1",
        "PAY-REFUND-PENDING@1",
        "DQ-ORDER-TOTAL@1",
        "DQ-NEGATIVE-ON-HAND@1",
    ]
    assert {r.exception_type for r in RULES} == set(ExceptionType)
