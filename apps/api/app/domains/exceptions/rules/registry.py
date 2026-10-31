"""The v1 rule registry (EXCEPTION_CATALOG.md) and the supersede precedence between types."""

from collections.abc import Sequence

from app.core.errors import BusinessRuleViolationError
from app.domains.exceptions.models import ExceptionType
from app.domains.exceptions.rules import (
    data_negative_on_hand,
    data_order_total_mismatch,
    inventory_below_reorder_point,
    inventory_out_of_stock,
    inventory_oversell_risk,
    inventory_oversold,
    order_fulfillment_overdue,
    order_refund_pending,
    order_stalled_after_payment,
)
from app.domains.exceptions.rules.base import Rule
from app.domains.exceptions.rules.inventory_common import INVENTORY_PRECEDENCE

# Registry order is also the processing order of findings, so references are allocated
# deterministically (most severe inventory condition first).
RULES: tuple[Rule, ...] = (
    inventory_oversold.RULE,
    inventory_oversell_risk.RULE,
    inventory_out_of_stock.RULE,
    inventory_below_reorder_point.RULE,
    order_fulfillment_overdue.RULE,
    order_stalled_after_payment.RULE,
    order_refund_pending.RULE,
    data_order_total_mismatch.RULE,
    data_negative_on_hand.RULE,
)
RULES_BY_ID: dict[str, Rule] = {rule.rule_id: rule for rule in RULES}
RULES_BY_TYPE: dict[ExceptionType, Rule] = {rule.exception_type: rule for rule in RULES}

# A finding of the key type resolves active exceptions of the value types for the same entity as
# SUPERSEDED (BR-401 for inventory; overdue supersedes stalled for orders).
SUPERSEDES: dict[ExceptionType, frozenset[ExceptionType]] = {
    **{
        higher: frozenset(INVENTORY_PRECEDENCE[index + 1 :])
        for index, higher in enumerate(INVENTORY_PRECEDENCE)
    },
    ExceptionType.ORDER_FULFILLMENT_OVERDUE: frozenset({ExceptionType.ORDER_STALLED_AFTER_PAYMENT}),
    # BR-402a: a negative on-hand suppresses the inventory rules. The stock problem is not fixed,
    # it is hidden behind invalid data, so it is superseded rather than auto-resolved.
    ExceptionType.DATA_NEGATIVE_ON_HAND: frozenset(INVENTORY_PRECEDENCE),
}


class UnknownRuleError(BusinessRuleViolationError):
    code = "UNKNOWN_RULE"


def select_rules(rule_ids: Sequence[str] | None) -> tuple[Rule, ...]:
    """The rules to execute: all by default, else the given ids in registry order."""
    if not rule_ids:
        return RULES
    unknown = sorted(set(rule_ids) - RULES_BY_ID.keys())
    if unknown:
        raise UnknownRuleError(
            "Unknown rule id.",
            details=[{"rule_id": rule_id, "known": sorted(RULES_BY_ID)} for rule_id in unknown],
        )
    wanted = set(rule_ids)
    return tuple(rule for rule in RULES if rule.rule_id in wanted)
