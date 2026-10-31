"""INVENTORY_OUT_OF_STOCK (``INV-OUT-OF-STOCK@1``): an active product with available = 0."""

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
)
from app.domains.exceptions.rules.inventory_common import (
    balance_source,
    inventory_condition,
    product_ref,
    supplier_phrase,
    supplier_source,
    velocity,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, ProductFacts, RuleSettings

RULE_ID = "INV-OUT-OF-STOCK@1"
EXCEPTION_TYPE = ExceptionType.INVENTORY_OUT_OF_STOCK
CATEGORY = ExceptionCategory.INVENTORY


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(product, settings, as_of)
        for product in snapshot.products_in_order
        if inventory_condition(product, snapshot.pending_demand(product.id)) is EXCEPTION_TYPE
    ]


def recommended_action(product: ProductFacts) -> str:
    return clip(
        f"Reorder from {supplier_phrase(product)} or hide the listing until stock arrives.",
        ACTION_MAX,
    )


def _finding(product: ProductFacts, settings: RuleSettings, as_of: datetime) -> Finding:
    window = settings.velocity_window_days
    daily = velocity(product, window)
    # "Selling" means avg_daily_units > 0 before rounding, i.e. any unit sold in the window.
    selling = product.units_sold_in_window > 0
    balance = balance_source(product)
    supplier = supplier_source(product)
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
        fact(
            "incoming",
            "Incoming (not counted as available)",
            product.incoming,
            src=balance,
            unit="units",
        ),
        fact("incoming_eta", "Earliest incoming ETA", product.incoming_eta, src=balance),
        fact(
            "units_sold_in_window",
            f"Units sold in the last {window} days",
            product.units_sold_in_window,
            src=None,
            unit="units",
            volatile=True,
        ),
        fact(
            "avg_daily_units",
            "Average daily units (estimate)",
            daily,
            src=None,
            unit="units/day",
            estimate=True,
            volatile=True,
        ),
        fact("supplier", "Supplier", product.supplier_name, src=supplier),
        fact(
            "lead_time_days",
            "Supplier lead time",
            product.lead_time_days,
            src=supplier,
            unit="days",
        ),
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=product_ref(product),
        severity=Severity.HIGH if selling else Severity.MEDIUM,
        title=clip(f"Out of stock: {product.sku} ({product.name})", TITLE_MAX),
        evidence=evidence(facts),
        calculation=calculation(
            formulas=[
                "available = on_hand − reserved (BR-101)",
                "condition: available = 0 (and no higher-precedence inventory condition)",
                f"avg_daily_units = units sold in the last {window} days ÷ {window} (BR-150)",
                "severity = HIGH if avg_daily_units > 0 else MEDIUM",
            ],
            inputs={
                "on_hand": product.on_hand,
                "reserved": product.reserved,
                "units_sold_in_window": product.units_sold_in_window,
                "velocity_window_days": window,
            },
            outputs={"available": product.available, "avg_daily_units": daily, "selling": selling},
        ),
        recommended_action=recommended_action(product),
        detected_at=as_of,
        exposure_amount=ZERO_MONEY,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
