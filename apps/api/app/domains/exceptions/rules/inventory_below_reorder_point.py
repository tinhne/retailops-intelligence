"""INVENTORY_BELOW_REORDER_POINT (``INV-BELOW-ROP@1``): 0 < available ≤ reorder_point."""

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
    cover_days,
    inventory_condition,
    product_ref,
    product_source,
    supplier_source,
    velocity,
)
from app.domains.exceptions.snapshot import EvaluationSnapshot, ProductFacts, RuleSettings

RULE_ID = "INV-BELOW-ROP@1"
EXCEPTION_TYPE = ExceptionType.INVENTORY_BELOW_REORDER_POINT
CATEGORY = ExceptionCategory.INVENTORY


def evaluate(
    snapshot: EvaluationSnapshot, settings: RuleSettings, as_of: datetime
) -> list[Finding]:
    return [
        _finding(product, settings, as_of)
        for product in snapshot.products_in_order
        if inventory_condition(product, snapshot.pending_demand(product.id)) is EXCEPTION_TYPE
    ]


def suggested_quantity(product: ProductFacts) -> int:
    """max(0, (reorder_quantity if set, else reorder_point × 2 − available) − incoming).

    A reorder_quantity of 0 counts as "not set", because it would never suggest an order.
    """
    base = (
        product.reorder_quantity
        if product.reorder_quantity
        else product.reorder_point * 2 - product.available
    )
    return max(0, base - product.incoming)


def recommended_action(product: ProductFacts) -> str:
    suggested = suggested_quantity(product)
    if suggested > 0:
        return f"Place a replenishment order for at least {suggested} units."
    supplier = product.supplier_name or "your supplier"
    return clip(
        f"Incoming stock ({product.incoming} units) covers the reorder point. "
        f"Confirm the ETA with {supplier}.",
        ACTION_MAX,
    )


def _finding(product: ProductFacts, settings: RuleSettings, as_of: datetime) -> Finding:
    window = settings.velocity_window_days
    daily = velocity(product, window)
    cover = cover_days(product, window)
    lead = product.lead_time_days
    # HIGH only when velocity and lead time are both known and cover runs out first.
    high = cover is not None and lead is not None and cover < lead
    suggested = suggested_quantity(product)
    balance = balance_source(product)
    supplier = supplier_source(product)
    prod = product_source(product)
    facts = [
        fact(
            "available",
            "Available (on hand − reserved)",
            product.available,
            src=balance,
            unit="units",
        ),
        fact("reorder_point", "Reorder point", product.reorder_point, src=prod, unit="units"),
        fact(
            "reorder_quantity", "Reorder quantity", product.reorder_quantity, src=prod, unit="units"
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
            "avg_daily_units",
            "Average daily units (estimate)",
            daily,
            src=None,
            unit="units/day",
            estimate=True,
            volatile=True,
        ),
        fact(
            "days_of_cover",
            "Days of cover (estimate)",
            cover,
            src=None,
            unit="days",
            estimate=True,
            volatile=True,
        ),
        fact("supplier", "Supplier", product.supplier_name, src=supplier),
        fact("lead_time_days", "Supplier lead time", lead, src=supplier, unit="days"),
    ]
    return Finding(
        rule_id=RULE_ID,
        exception_type=EXCEPTION_TYPE,
        category=CATEGORY,
        primary_entity=product_ref(product),
        severity=Severity.HIGH if high else Severity.MEDIUM,
        title=clip(
            f"Below reorder point: {product.sku} ({product.name}) has {product.available} "
            f"available, reorder point {product.reorder_point}",
            TITLE_MAX,
        ),
        evidence=evidence(facts),
        calculation=calculation(
            formulas=[
                "available = on_hand − reserved (BR-101)",
                "condition: reorder_point > 0 and 0 < available ≤ reorder_point (BR-140)",
                f"avg_daily_units = units sold in the last {window} days ÷ {window} (BR-150)",
                "days_of_cover = available ÷ avg_daily_units (BR-151)",
                "severity = HIGH if days_of_cover < lead_time_days (both known) else MEDIUM",
                "suggested = max(0, (reorder_quantity if set, else reorder_point × 2 − available) "
                "− incoming)",
            ],
            inputs={
                "on_hand": product.on_hand,
                "reserved": product.reserved,
                "reorder_point": product.reorder_point,
                "reorder_quantity": product.reorder_quantity,
                "incoming": product.incoming,
                "units_sold_in_window": product.units_sold_in_window,
                "velocity_window_days": window,
                "lead_time_days": lead,
            },
            outputs={
                "available": product.available,
                "avg_daily_units": daily,
                "days_of_cover": cover,
                "suggested": suggested,
            },
        ),
        recommended_action=recommended_action(product),
        detected_at=as_of,
        exposure_amount=ZERO_MONEY,
    )


RULE = Rule(RULE_ID, EXCEPTION_TYPE, CATEGORY, evaluate)
