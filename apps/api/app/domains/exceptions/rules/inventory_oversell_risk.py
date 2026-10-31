"""INVENTORY_OVERSELL_RISK (``INV-OVERSELL-RISK@1``): pending demand exceeds available (BR-403)."""

import uuid
from datetime import UTC, datetime
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
)
from app.domains.exceptions.rules.inventory_common import (
    balance_source,
    inventory_condition,
    order_source,
    product_ref,
    product_source,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, ProductFacts, RuleSettings

RULE_ID = "INV-OVERSELL-RISK@1"
EXCEPTION_TYPE = ExceptionType.INVENTORY_OVERSELL_RISK
CATEGORY = ExceptionCategory.INVENTORY
RECOMMENDED_ACTION = (
    "Pending orders would exceed available stock if they are paid. Consider pausing the listing "
    "or confirming incoming stock."
)
_EPOCH = datetime.min.replace(tzinfo=UTC)


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, product, as_of)
        for product in snapshot.products_in_order
        if inventory_condition(product, snapshot.pending_demand(product.id)) is EXCEPTION_TYPE
    ]


def _finding(snapshot: EvaluationSnapshot, product: ProductFacts, as_of: datetime) -> Finding:
    pending_lines = sorted(
        snapshot.pending_lines_for(product.id),
        key=lambda line: (line.placed_at or _EPOCH, line.order_number, line.line_number),
    )
    pending_demand = sum(line.quantity for line in pending_lines)
    shortage = pending_demand - product.available
    exposure = money(Decimal(shortage) * product.unit_price)
    orders: dict[uuid.UUID, str] = {}
    for line in pending_lines:
        orders.setdefault(line.order_id, line.order_number)
    balance = balance_source(product)
    currency = snapshot.currency

    facts = [
        fact(
            "available",
            "Available (on hand − reserved)",
            product.available,
            src=balance,
            unit="units",
        ),
        fact("pending_demand", "Units on unpaid orders", pending_demand, src=None, unit="units"),
        fact("potential_shortage", "Potential shortage", shortage, src=None, unit="units"),
        fact(
            "unit_price",
            "Current unit price",
            product.unit_price,
            src=product_source(product),
            unit=currency,
        ),
        fact(
            "incoming",
            "Incoming (not counted as available)",
            product.incoming,
            src=balance,
            unit="units",
        ),
        fact("incoming_eta", "Earliest incoming ETA", product.incoming_eta, src=balance),
        fact("exposure_amount", "Gross value at risk", exposure, src=None, unit=currency),
    ]
    pending_rows = [
        {
            "order_id": line.order_id,
            "order_number": line.order_number,
            "status": line.order_status,
            "placed_at": line.placed_at,
            "order_item_id": line.order_item_id,
            "line_number": line.line_number,
            "quantity": line.quantity,
            "source": order_source(line.order_id, line.order_number),
        }
        for line in pending_lines
    ]
    title = clip(
        f"Oversell risk: {product.sku} ({product.name}) has {pending_demand} units on unpaid "
        f"orders but {product.available} available",
        TITLE_MAX,
    )
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=product_ref(product),
        severity=Severity.HIGH,
        title=title,
        evidence=evidence(facts, {"pending_orders": pending_rows}),
        calculation=calculation(
            formulas=[
                "available = on_hand − reserved (BR-101)",
                "pending_demand = Σ quantity on CREATED / PAYMENT_PENDING orders",
                "condition: available ≥ 0 and pending_demand > available (BR-403)",
                "potential_shortage = pending_demand − available",
                "exposure = potential_shortage × current unit_price (BR-404)",
            ],
            inputs={
                "on_hand": product.on_hand,
                "reserved": product.reserved,
                "pending_demand": pending_demand,
                "unit_price": product.unit_price,
            },
            outputs={
                "available": product.available,
                "potential_shortage": shortage,
                "exposure_amount": exposure,
            },
        ),
        recommended_action=clip(RECOMMENDED_ACTION, ACTION_MAX),
        detected_at=as_of,
        related_entities=tuple(
            EntityRef(EntityType.ORDER, order_id, number) for order_id, number in orders.items()
        ),
        affected_order_ids=tuple(orders),
        exposure_amount=exposure,
        deadline_at=None,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
