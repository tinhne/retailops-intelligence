"""Helpers shared by the order rules (BUSINESS_RULES.md §3)."""

import uuid
from datetime import datetime, timedelta

from app.domains.exceptions.models import EntityType
from app.domains.exceptions.rules.base import EntityRef, source
from app.domains.exceptions.snapshot import EvaluationSnapshot, OrderFacts, RuleSettings
from app.domains.orders.models import ShipBySource


def order_ref(order: OrderFacts) -> EntityRef:
    return EntityRef(EntityType.ORDER, order.id, order.order_number)


def order_src(order: OrderFacts) -> dict[str, str]:
    return source("order", order.id, f"Order {order.order_number}")


def effective_ship_by(
    order: OrderFacts, settings: RuleSettings
) -> tuple[datetime | None, ShipBySource | None]:
    """BR-201: the stored ship_by; if it is missing, paid_at + fulfillment_sla_hours."""
    if order.ship_by is not None:
        return order.ship_by, order.ship_by_source or ShipBySource.IMPORTED
    if order.paid_at is not None:
        return (
            order.paid_at + timedelta(hours=settings.fulfillment_sla_hours),
            ShipBySource.STORE_SLA,
        )
    return None, None


def line_products(snapshot: EvaluationSnapshot, order_id: uuid.UUID) -> tuple[EntityRef, ...]:
    """Distinct products on a committed order's lines, as AFFECTED entity references."""
    refs: dict[uuid.UUID, EntityRef] = {}
    for line in snapshot.lines_for_order(order_id):
        refs.setdefault(line.product_id, EntityRef(EntityType.PRODUCT, line.product_id, line.sku))
    return tuple(refs.values())
