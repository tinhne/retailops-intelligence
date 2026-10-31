"""Demo dataset generator (T-056): engineered scenarios and internal consistency."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo.seed import seed_demo
from app.domains.analytics import queries as analytics_queries
from app.domains.catalog.models import Product
from app.domains.identity.models import Membership
from app.domains.identity.permissions import Role
from app.domains.inventory import service as inventory

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)


def _balance(db: Session, store_id: object, sku: str) -> tuple[int, int, int]:
    product = db.scalars(
        select(Product).where(Product.store_id == store_id, Product.sku == sku)
    ).one()
    balance = inventory.get_balance(db, product.store_id, product.id)
    return balance.on_hand, balance.reserved, product.reorder_point


def test_seed_is_consistent_and_engineers_every_inventory_scenario(db: Session) -> None:
    summary = seed_demo(db, now=NOW, seed=7)
    db.commit()

    assert summary.orders > 1000
    assert inventory.reconcile(db, summary.store_id) == []  # BR-104: ledger == balances
    scenarios = summary.scenarios
    for sku in scenarios["INVENTORY_OVERSOLD"]:
        on_hand, reserved, _ = _balance(db, summary.store_id, sku)
        assert on_hand >= 0
        assert reserved > on_hand  # BR-402a: oversold always has committed demand
    (oos,) = scenarios["INVENTORY_OUT_OF_STOCK"]
    on_hand, reserved, _ = _balance(db, summary.store_id, oos)
    assert on_hand - reserved == 0
    for sku in scenarios["INVENTORY_BELOW_REORDER_POINT"]:
        on_hand, reserved, rop = _balance(db, summary.store_id, sku)
        assert 0 < on_hand - reserved <= rop
    (negative,) = scenarios["DATA_NEGATIVE_ON_HAND"]
    assert _balance(db, summary.store_id, negative)[0] < 0
    # BR-402a: the negative product is a data issue, not one of the oversold products.
    health = analytics_queries.active_product_health_counts(
        db, summary.store_id, factor=Decimal("1.25")
    )
    assert health.get("DATA_ISSUE") == 1
    assert health.get("OVERSOLD") == len(scenarios["INVENTORY_OVERSOLD"])
    for key in (
        "ORDER_FULFILLMENT_OVERDUE",
        "ORDER_STALLED_AFTER_PAYMENT",
        "ORDER_REFUND_PENDING",
        "DATA_ORDER_TOTAL_MISMATCH",
    ):
        assert scenarios[key], key


def test_reseeding_replaces_the_demo_org_and_keeps_viewer_read_only(db: Session) -> None:
    first = seed_demo(db, now=NOW, seed=7)
    db.commit()
    second = seed_demo(db, now=NOW, seed=7)
    db.commit()

    assert first.organization_id != second.organization_id
    roles = db.scalars(
        select(Membership.role).where(Membership.organization_id == second.organization_id)
    ).all()
    assert roles.count(Role.VIEWER) == 1
    assert Role.OWNER in roles
