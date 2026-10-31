"""Data-quality rules (EXCEPTION_CATALOG.md: DQ-ORDER-TOTAL@1, DQ-NEGATIVE-ON-HAND@1)."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest

from app.domains.catalog.models import ProductStatus
from app.domains.exceptions.models import ExceptionCategory, Severity
from app.domains.exceptions.rules import data_negative_on_hand, data_order_total_mismatch
from app.domains.exceptions.rules.base import Finding
from app.domains.exceptions.rules.inventory_common import NEGATIVE_ON_HAND_NOTE
from app.domains.exceptions.snapshot import MovementFacts, RejectedImportRows
from app.domains.inventory.models import MovementType
from tests.factories_exceptions import SETTINGS, T0, facts_order, facts_product, snapshot


def _mismatch(
    total: str,
    line_sum: str = "48.00",
    *,
    shipping: str = "5.95",
    tax: str = "3.12",
    discount: str = "0.00",
    line_count: int = 1,
) -> list[Finding]:
    order = facts_order(
        "KHK-100610",
        total=total,
        line_sum=line_sum,
        shipping_total=shipping,
        tax_total=tax,
        discount_total=discount,
        line_count=line_count,
    )
    return list(data_order_total_mismatch.evaluate(snapshot(orders_=[order]), SETTINGS, T0))


@pytest.mark.parametrize(
    ("total", "severity"),
    [
        ("57.07", None),  # 48.00 + 5.95 + 3.12 reconciles
        ("57.08", None),  # |difference| = 0.01 is within tolerance (BR-205)
        ("57.06", None),
        ("57.09", Severity.LOW),  # 0.02
        ("58.06", Severity.LOW),  # 0.99 < 1.00
        ("58.07", Severity.MEDIUM),  # exactly 1.00
        ("56.07", Severity.MEDIUM),  # −1.00
        ("62.02", Severity.MEDIUM),  # the gift-wrap example: 4.95
    ],
)
def test_total_mismatch_tolerance_and_severity_bands(total: str, severity: Severity | None) -> None:
    findings = _mismatch(total)
    if severity is None:
        assert findings == []
    else:
        (finding,) = findings
        assert finding.severity is severity


def test_total_mismatch_formula_includes_order_discount_shipping_and_tax() -> None:
    """expected = Σ(qty × price − line discount) − order discount + shipping + tax."""
    (finding,) = _mismatch("60.00", line_sum="50.00", discount="5.00", shipping="10.00", tax="2.50")
    outputs = finding.calculation["outputs"]
    assert outputs == {"expected_total": "57.50", "difference": "2.50"}
    assert finding.exposure_amount == Decimal("0.00")
    assert finding.category is ExceptionCategory.DATA_QUALITY
    assert finding.affected_order_count == 1


def test_order_without_lines_is_never_a_mismatch() -> None:
    assert _mismatch("999.00", line_sum="0.00", line_count=0) == []


def test_total_mismatch_reports_rejected_import_rows_for_the_order() -> None:
    order = facts_order("KHK-100610", total="70.00", line_sum="48.00")
    import_id = uuid.uuid4()
    snap = snapshot(
        orders_=[order],
        rejected_import_rows={"KHK-100610": RejectedImportRows(count=2, import_ids=(import_id,))},
    )

    (finding,) = data_order_total_mismatch.evaluate(snap, SETTINGS, T0)

    facts = {f["key"]: f["value"] for f in finding.evidence["facts"]}
    assert facts["rejected_import_rows"] == 2
    assert facts["difference"] == "22.00"
    assert finding.evidence["records"]["rejected_imports"][0]["import_id"] == str(import_id)


# --- DQ-NEGATIVE-ON-HAND@1 ---------------------------------------------------------------------


@pytest.mark.parametrize("status", list(ProductStatus))
def test_negative_on_hand_fires_for_any_product_status(status: ProductStatus) -> None:
    product = facts_product("SKU-A", on_hand=-3, reserved=2, status=status)
    zero = facts_product("SKU-B", on_hand=0, status=status)

    findings = data_negative_on_hand.evaluate(snapshot(products=[product, zero]), SETTINGS, T0)

    assert [f.primary_entity.label for f in findings] == ["SKU-A"]
    assert findings[0].severity is Severity.HIGH
    assert findings[0].exposure_amount == Decimal("0.00")


def test_negative_on_hand_evidence_lists_movements_reserved_and_suppression_note() -> None:
    product = facts_product("SKU-A", on_hand=-2, reserved=4, last_cycle_count_at=T0)
    count = MovementFacts(
        id=uuid.uuid4(),
        product_id=product.id,
        movement_type=MovementType.CYCLE_COUNT,
        on_hand_delta=3,
        incoming_delta=0,
        on_hand_after=3,
        occurred_at=T0,
        reference="count-1",
    )
    damage = MovementFacts(
        id=uuid.uuid4(),
        product_id=product.id,
        movement_type=MovementType.DAMAGE,
        on_hand_delta=-5,
        incoming_delta=0,
        on_hand_after=-2,
        occurred_at=T0 + timedelta(hours=1),
        reference="adj-9",
    )
    snap = snapshot(
        products=[product],
        recent_movements={product.id: (damage, count)},
        last_cycle_counts={product.id: count},
    )

    (finding,) = data_negative_on_hand.evaluate(snap, SETTINGS, T0 + timedelta(hours=2))

    facts = {f["key"]: f["value"] for f in finding.evidence["facts"]}
    assert facts["on_hand"] == -2
    assert facts["reserved"] == 4
    assert finding.evidence["notes"] == [NEGATIVE_ON_HAND_NOTE]
    movements = finding.evidence["records"]["recent_movements"]
    assert [m["movement_type"] for m in movements] == ["DAMAGE", "CYCLE_COUNT"]
    assert movements[0]["source"]["type"] == "inventory_movement"
    assert finding.evidence["records"]["last_cycle_count"][0]["reference"] == "count-1"
    assert finding.recommended_action == (
        "Perform a cycle count and import it as a CYCLE_COUNT adjustment."
    )
