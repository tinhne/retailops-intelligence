"""INVENTORY_OVERSOLD (``INV-OVERSOLD@1``): committed demand exceeds on-hand stock."""

import uuid
from datetime import datetime
from decimal import Decimal

from app.domains.exceptions.models import (
    EntityType,
    ExceptionCategory,
    ExceptionType,
    Severity,
)
from app.domains.exceptions.rules.base import (
    ACTION_MAX,
    TITLE_MAX,
    EntityRef,
    Finding,
    Rule,
    calculation,
    clip,
    evidence,
    fact,
    money,
    plural,
)
from app.domains.exceptions.rules.inventory_common import (
    allocate_fifo,
    balance_source,
    inventory_condition,
    order_source,
    product_ref,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, ProductFacts, RuleSettings

RULE_ID = "INV-OVERSOLD@1"
EXCEPTION_TYPE = ExceptionType.INVENTORY_OVERSOLD
CATEGORY = ExceptionCategory.INVENTORY
RECOMMENDED_ACTION = (
    "Confirm physical stock with a cycle count. Then expedite incoming stock or contact the "
    "affected customers about a delay, starting with the most recent orders."
)


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, product, as_of)
        for product in snapshot.products_in_order
        if inventory_condition(product, snapshot.pending_demand(product.id)) is EXCEPTION_TYPE
    ]


def _finding(snapshot: EvaluationSnapshot, product: ProductFacts, as_of: datetime) -> Finding:
    lines = snapshot.committed_lines_for(product.id)
    allocations = allocate_fifo(product.on_hand, lines)
    affected = [a for a in allocations if a.uncovered > 0]

    # Distinct affected orders, in allocation (FIFO) order.
    affected_orders: dict[uuid.UUID, str] = {}
    for allocation in affected:
        affected_orders.setdefault(allocation.line.order_id, allocation.line.order_number)
    exposure = money(sum((Decimal(a.uncovered) * a.line.unit_price for a in affected), Decimal(0)))
    ship_bys = [a.line.ship_by for a in affected if a.line.ship_by is not None]
    deadline = min(ship_bys) if ship_bys else None
    shortage = -product.available
    committed_units = sum(line.quantity for line in lines)
    balance = balance_source(product)
    currency = snapshot.currency

    affected_rows = [
        {
            "order_id": a.line.order_id,
            "order_number": a.line.order_number,
            "order_item_id": a.line.order_item_id,
            "line_number": a.line.line_number,
            "paid_at": a.line.paid_at,
            "ship_by": a.line.ship_by,
            "quantity": a.line.quantity,
            "covered_quantity": a.covered,
            "uncovered_quantity": a.uncovered,
            "unit_price": a.line.unit_price,
            "value_at_risk": money(Decimal(a.uncovered) * a.line.unit_price),
            "source": order_source(a.line.order_id, a.line.order_number),
        }
        for a in affected
    ]
    facts = [
        fact("on_hand", "On hand", product.on_hand, src=balance, unit="units"),
        fact(
            "reserved", "Reserved for committed orders", product.reserved, src=balance, unit="units"
        ),
        fact(
            "available",
            "Available (on hand − reserved)",
            product.available,
            src=balance,
            unit="units",
        ),
        fact("shortage", "Shortage (−available)", shortage, src=balance, unit="units"),
        fact(
            "committed_units",
            "Units on committed order lines",
            committed_units,
            src=None,
            unit="units",
        ),
        fact(
            "incoming",
            "Incoming (not counted as available)",
            product.incoming,
            src=balance,
            unit="units",
        ),
        fact("incoming_eta", "Earliest incoming ETA", product.incoming_eta, src=balance),
        fact("last_cycle_count_at", "Last cycle count", product.last_cycle_count_at, src=balance),
        fact(
            "affected_order_count", "Affected orders", len(affected_orders), src=None, unit="orders"
        ),
        fact(
            "exposure_amount", "Gross order-line value at risk", exposure, src=None, unit=currency
        ),
    ]
    steps: list[dict[str, object]] = [
        {
            "order_number": a.line.order_number,
            "line_number": a.line.line_number,
            "paid_at": a.line.paid_at,
            "quantity": a.line.quantity,
            "covered": a.covered,
            "uncovered": a.uncovered,
        }
        for a in allocations
    ]
    title = clip(
        f"Oversold: {product.sku} ({product.name}) short by {plural(shortage, 'unit')} "
        f"across {plural(len(affected_orders), 'order')}",
        TITLE_MAX,
    )
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=product_ref(product),
        severity=Severity.CRITICAL,
        title=title,
        evidence=evidence(facts, {"affected_orders": affected_rows}),
        calculation=calculation(
            formulas=[
                "available = on_hand − reserved (BR-101)",
                "shortage = −available",
                "Allocate on_hand to committed lines by paid_at, ties by order_number; "
                "lines not fully covered are affected (BR-402)",
                "exposure = Σ uncovered_quantity × unit_price (gross value at risk, BR-404)",
                "deadline = earliest ship_by among affected orders",
            ],
            inputs={
                "on_hand": product.on_hand,
                "reserved": product.reserved,
                "committed_lines": len(lines),
            },
            outputs={
                "available": product.available,
                "shortage": shortage,
                "affected_orders": len(affected_orders),
                "uncovered_units": sum(a.uncovered for a in affected),
                "exposure_amount": exposure,
                "deadline_at": deadline,
            },
            steps=steps,
        ),
        recommended_action=clip(RECOMMENDED_ACTION, ACTION_MAX),
        detected_at=as_of,
        related_entities=tuple(
            EntityRef(EntityType.ORDER, order_id, number)
            for order_id, number in affected_orders.items()
        ),
        affected_order_ids=tuple(affected_orders),
        exposure_amount=exposure,
        deadline_at=deadline,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
