"""DATA_NEGATIVE_ON_HAND (``DQ-NEGATIVE-ON-HAND@1``): physical stock below zero.

Applies to products of any status. While it holds, the four inventory rules are suppressed for the
product (``inventory_common.inventory_condition``), because the stock figure is invalid input.
"""

from datetime import datetime

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
    plural,
    source,
)
from app.domains.exceptions.rules.inventory_common import (
    NEGATIVE_ON_HAND_NOTE,
    balance_source,
    product_ref,
)
from app.domains.exceptions.snapshot import (
    EvaluationSnapshot,
    MovementFacts,
    ProductFacts,
    RuleSettings,
)

RULE_ID = "DQ-NEGATIVE-ON-HAND@1"
EXCEPTION_TYPE = ExceptionType.DATA_NEGATIVE_ON_HAND
CATEGORY = ExceptionCategory.DATA_QUALITY
RECOMMENDED_ACTION = "Perform a cycle count and import it as a CYCLE_COUNT adjustment."


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(snapshot, product, as_of)
        for product in snapshot.products_in_order
        if product.on_hand < 0
    ]


def _movement_row(movement: MovementFacts) -> dict[str, object]:
    return {
        "movement_id": movement.id,
        "movement_type": movement.movement_type,
        "on_hand_delta": movement.on_hand_delta,
        "incoming_delta": movement.incoming_delta,
        "on_hand_after": movement.on_hand_after,
        "occurred_at": movement.occurred_at,
        "reference": movement.reference,
        "source": source(
            "inventory_movement",
            movement.id,
            f"{movement.movement_type.value} {movement.reference or ''}".strip(),
        ),
    }


def _finding(snapshot: EvaluationSnapshot, product: ProductFacts, as_of: datetime) -> Finding:
    balance = balance_source(product)
    movements = snapshot.recent_movements.get(product.id, ())
    last_count = snapshot.last_cycle_counts.get(product.id)
    facts = [
        fact("on_hand", "On hand", product.on_hand, src=balance, unit="units"),
        fact(
            "reserved", "Reserved for committed orders", product.reserved, src=balance, unit="units"
        ),
        fact("incoming", "Incoming", product.incoming, src=balance, unit="units"),
        fact(
            "product_status",
            "Product status",
            product.status,
            src=source("product", product.id, product.sku),
        ),
        fact("last_cycle_count_at", "Last cycle count", product.last_cycle_count_at, src=balance),
    ]
    records = {
        "recent_movements": [_movement_row(m) for m in movements],
        "last_cycle_count": [_movement_row(last_count)] if last_count else [],
    }
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=product_ref(product),
        severity=Severity.HIGH,
        title=clip(
            f"Negative on-hand stock: {product.sku} ({product.name}) at "
            f"{plural(product.on_hand, 'unit')}",
            TITLE_MAX,
        ),
        evidence=evidence(facts, records, notes=[NEGATIVE_ON_HAND_NOTE]),
        calculation=calculation(
            formulas=[
                "on_hand = Σ on_hand_delta of the product's ledger movements (BR-110)",
                "condition: on_hand < 0 (any product status)",
            ],
            inputs={"on_hand": product.on_hand, "movements_shown": len(movements)},
            outputs={"on_hand": product.on_hand, "inventory_rules_suppressed": True},
        ),
        recommended_action=clip(RECOMMENDED_ACTION, ACTION_MAX),
        detected_at=as_of,
        exposure_amount=ZERO_MONEY,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
