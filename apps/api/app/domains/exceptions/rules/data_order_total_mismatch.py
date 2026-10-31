"""DATA_ORDER_TOTAL_MISMATCH (``DQ-ORDER-TOTAL@1``): recorded total ≠ expected total (BR-205)."""

from datetime import datetime
from decimal import Decimal

from app.domains.exceptions.models import ExceptionCategory, ExceptionType, Severity
from app.domains.exceptions.rules.base import (
    ACTION_MAX,
    TITLE_MAX,
    ZERO_MONEY,
    Finding,
    Rule,
    calculation,
    clip,
    evidence,
    fact,
    money,
    source,
)
from app.domains.exceptions.rules.order_common import order_ref, order_src
from app.domains.exceptions.snapshot import (
    EvaluationSnapshot,
    OrderFacts,
    RejectedImportRows,
    RuleSettings,
)

RULE_ID = "DQ-ORDER-TOTAL@1"
EXCEPTION_TYPE = ExceptionType.DATA_ORDER_TOTAL_MISMATCH
CATEGORY = ExceptionCategory.DATA_QUALITY
TOLERANCE = Decimal("0.01")
LOW_BELOW = Decimal("1.00")
RECOMMENDED_ACTION = (
    "Compare the order in the source system. A rejected or missing order line is the most "
    "common cause."
)


def expected_total(order: OrderFacts) -> Decimal:
    """BR-205: Σ(quantity × unit_price − line_discount) − order discount + shipping + tax."""
    return money(order.line_sum - order.discount_total + order.shipping_total + order.tax_total)


def difference(order: OrderFacts) -> Decimal:
    return money(order.total - expected_total(order))


def has_mismatch(order: OrderFacts) -> bool:
    """A mismatch needs at least one line and |total − expected_total| > 0.01."""
    return order.line_count >= 1 and abs(difference(order)) > TOLERANCE


def severity_for(diff: Decimal) -> Severity:
    return Severity.LOW if abs(diff) < LOW_BELOW else Severity.MEDIUM


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, order, as_of)
        for order in snapshot.orders_in_order
        if has_mismatch(order)
    ]


def _finding(snapshot: EvaluationSnapshot, order: OrderFacts, as_of: datetime) -> Finding:
    expected = expected_total(order)
    diff = difference(order)
    rejected = snapshot.rejected_import_rows.get(
        order.order_number, RejectedImportRows(count=0, import_ids=())
    )
    src = order_src(order)
    cur = order.currency
    facts = [
        fact("recorded_total", "Recorded total", money(order.total), src=src, unit=cur),
        fact("expected_total", "Expected total", expected, src=None, unit=cur),
        fact("difference", "Difference (recorded − expected)", diff, src=None, unit=cur),
        fact("line_count", "Order lines", order.line_count, src=src, unit="lines"),
        fact(
            "lines_total",
            "Σ line quantity × unit price − line discount",
            money(order.line_sum),
            src=src,
            unit=cur,
        ),
        fact("discount_total", "Order discount", money(order.discount_total), src=src, unit=cur),
        fact("shipping_total", "Shipping", money(order.shipping_total), src=src, unit=cur),
        fact("tax_total", "Tax", money(order.tax_total), src=src, unit=cur),
        fact(
            "rejected_import_rows",
            "Rejected import rows naming this order",
            rejected.count,
            src=None,
            unit="rows",
        ),
    ]
    import_rows = [
        {"import_id": import_id, "source": source("data_import", import_id, "Data import")}
        for import_id in rejected.import_ids
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=order_ref(order),
        severity=severity_for(diff),
        title=clip(
            f"Order {order.order_number} total {money(order.total)} does not match its lines "
            f"(expected {expected} {cur})",
            TITLE_MAX,
        ),
        evidence=evidence(
            facts,
            {"rejected_imports": import_rows},
            notes=[
                "Only import issues raised on the order_number column can be attributed to an "
                "order; other rejected line rows are not linked."
            ],
        ),
        calculation=calculation(
            formulas=[
                "expected_total = Σ(quantity × unit_price − line_discount) − discount_total "
                "+ shipping_total + tax_total (BR-205)",
                "mismatch when |total − expected_total| > 0.01 and the order has ≥ 1 line",
                "severity = LOW if |difference| < 1.00 else MEDIUM",
            ],
            inputs={
                "total": order.total,
                "lines_total": order.line_sum,
                "discount_total": order.discount_total,
                "shipping_total": order.shipping_total,
                "tax_total": order.tax_total,
                "line_count": order.line_count,
            },
            outputs={"expected_total": expected, "difference": diff},
        ),
        recommended_action=clip(RECOMMENDED_ACTION, ACTION_MAX),
        detected_at=as_of,
        affected_order_ids=(order.id,),
        exposure_amount=ZERO_MONEY,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
