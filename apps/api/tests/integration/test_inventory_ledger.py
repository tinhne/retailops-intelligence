"""Ledger, reservations and the cycle-count cutoff against PostgreSQL (BUSINESS_RULES.md §2)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolationError
from app.domains.catalog.models import Product, ProductStatus
from app.domains.inventory import service as inventory
from app.domains.inventory.models import (
    InventoryMovement,
    MovementSource,
    MovementType,
    ReservationStatus,
    StockReservation,
)
from app.domains.orders import service as orders
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
)
from tests.factories import Tenant, create_tenant

pytestmark = pytest.mark.integration
T0 = datetime(2026, 10, 1, 9, tzinfo=UTC)


def _product(db: Session, tenant: Tenant, sku: str = "KH-MUG-01") -> Product:
    product = Product(
        store_id=tenant.store.id,
        sku=sku,
        name="Stoneware Mug",
        status=ProductStatus.ACTIVE,
        unit_price=Decimal("18.00"),
        reorder_point=5,
    )
    db.add(product)
    db.flush()
    return product


def _count(db: Session, tenant: Tenant, product: Product, qty: int, at: datetime) -> None:
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=MovementType.CYCLE_COUNT,
        quantity=qty,
        occurred_at=at,
        source=MovementSource.IMPORT,
        reference=f"count-{at.isoformat()}",
    )


def _order(
    db: Session,
    tenant: Tenant,
    product: Product,
    *,
    number: str,
    status: OrderStatus,
    qty: int,
    shipped_at: datetime | None = None,
) -> None:
    payment = {
        OrderStatus.PAYMENT_PENDING: PaymentStatus.PENDING,
        OrderStatus.CANCELLED: PaymentStatus.PENDING,
    }.get(status, PaymentStatus.PAID)
    fulfillment = {
        OrderStatus.SHIPPED: FulfillmentStatus.SHIPPED,
        OrderStatus.PROCESSING: FulfillmentStatus.IN_PROGRESS,
    }.get(status, FulfillmentStatus.UNFULFILLED)
    snapshot = orders.OrderSnapshot(
        order_number=number,
        channel=SalesChannel.WEB,
        customer_ref=None,
        status=status,
        payment_status=payment,
        fulfillment_status=fulfillment,
        placed_at=T0,
        paid_at=T0 if payment is PaymentStatus.PAID else None,
        ship_by=None,
        shipped_at=shipped_at,
        delivered_at=None,
        cancelled_at=T0 if status is OrderStatus.CANCELLED else None,
        currency="USD",
        subtotal=Decimal("18.00") * qty,
        discount_total=Decimal("0"),
        shipping_total=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("18.00") * qty,
        carrier=None,
        tracking_number=None,
    )
    order, _ = orders.upsert_order(
        db,
        store_id=tenant.store.id,
        snapshot=snapshot,
        fulfillment_sla_hours=48,
        source=ChangeSource.IMPORT,
    )
    orders.upsert_order_item(
        db,
        order=order,
        line=orders.OrderLineSnapshot(
            line_number=1,
            product_id=product.id,
            sku=product.sku,
            quantity=qty,
            unit_price=Decimal("18.00"),
            line_discount=Decimal("0"),
        ),
    )
    inventory.sync_reservations(db, tenant.store.id, [order.id], now=T0 + timedelta(hours=1))


def test_reservations_follow_order_status_and_available_formula(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    _count(db, tenant, product, 10, T0 - timedelta(days=1))

    _order(db, tenant, product, number="1001", status=OrderStatus.PAID, qty=3)
    _order(db, tenant, product, number="1002", status=OrderStatus.PAYMENT_PENDING, qty=4)
    balance = inventory.get_balance(db, tenant.store.id, product.id)
    assert (balance.on_hand, balance.reserved, balance.available) == (10, 3, 7)  # BR-101

    _order(db, tenant, product, number="1001", status=OrderStatus.CANCELLED, qty=3)
    db.refresh(balance)
    assert balance.reserved == 0  # BR-121 released
    statuses = db.scalars(select(StockReservation.status)).all()
    assert statuses == [ReservationStatus.RELEASED]


def test_shipment_after_count_decrements_on_hand_once(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    _count(db, tenant, product, 10, T0 - timedelta(days=1))

    _order(db, tenant, product, number="2001", status=OrderStatus.PAID, qty=2)
    shipped = T0 + timedelta(hours=5)
    _order(
        db, tenant, product, number="2001", status=OrderStatus.SHIPPED, qty=2, shipped_at=shipped
    )
    # Re-running the sync must not create a second movement (BR-131).
    order = orders.find_by_number(db, tenant.store.id, "2001")
    assert order is not None
    inventory.sync_reservations(db, tenant.store.id, [order.id], now=shipped)

    balance = inventory.get_balance(db, tenant.store.id, product.id)
    assert (balance.on_hand, balance.reserved) == (8, 0)
    shipments = db.scalars(
        select(InventoryMovement).where(InventoryMovement.movement_type == MovementType.SHIPMENT)
    ).all()
    assert len(shipments) == 1


def test_br130_shipment_before_latest_count_is_not_double_counted(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    # The count at T0+1d already reflects the order shipped at T0+5h.
    _count(db, tenant, product, 8, T0 + timedelta(days=1))
    _order(
        db,
        tenant,
        product,
        number="3001",
        status=OrderStatus.SHIPPED,
        qty=2,
        shipped_at=T0 + timedelta(hours=5),
    )

    balance = inventory.get_balance(db, tenant.store.id, product.id)
    assert balance.on_hand == 8
    reservation = db.scalars(select(StockReservation)).one()
    assert reservation.status is ReservationStatus.CONSUMED


def test_late_imported_count_keeps_movements_recorded_after_it(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=MovementType.RECEIPT,
        quantity=5,
        occurred_at=T0 + timedelta(hours=10),
        source=MovementSource.IMPORT,
        reference="rcpt-1",
    )
    # Count taken at T0 (before the receipt) but imported afterwards.
    _count(db, tenant, product, 20, T0)

    balance = inventory.get_balance(db, tenant.store.id, product.id)
    assert balance.on_hand == 25  # 20 counted + 5 received later


def test_stale_cycle_count_is_rejected(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    _count(db, tenant, product, 10, T0)
    with pytest.raises(BusinessRuleViolationError) as exc:
        _count(db, tenant, product, 4, T0 - timedelta(hours=1))
    assert exc.value.code == "STALE_CYCLE_COUNT"


def test_reconcile_reports_no_drift_after_normal_operations(db: Session) -> None:
    tenant = create_tenant(db)
    product = _product(db, tenant)
    _count(db, tenant, product, 10, T0 - timedelta(days=1))
    _order(db, tenant, product, number="4001", status=OrderStatus.PROCESSING, qty=4)
    assert inventory.reconcile(db, tenant.store.id) == []

    balance = inventory.get_balance(db, tenant.store.id, product.id)
    balance.reserved = 99  # simulate a defect
    db.flush()
    drift = inventory.reconcile(db, tenant.store.id)
    assert [(d.field, d.stored, d.computed) for d in drift] == [("reserved", 99, 4)]


def test_br121_sku_change_on_committed_line_moves_the_reservation(db: Session) -> None:
    tenant = create_tenant(db)
    mug = _product(db, tenant, "KH-MUG-01")
    bowl = _product(db, tenant, "KH-BOWL-01")
    _order(db, tenant, mug, number="5001", status=OrderStatus.PAID, qty=2)
    order = orders.find_by_number(db, tenant.store.id, "5001")
    assert order is not None

    orders.upsert_order_item(
        db,
        order=order,
        line=orders.OrderLineSnapshot(
            line_number=1,
            product_id=bowl.id,
            sku=bowl.sku,
            quantity=2,
            unit_price=Decimal("18.00"),
            line_discount=Decimal("0"),
        ),
    )
    inventory.sync_reservations(db, tenant.store.id, [order.id], now=T0)

    assert inventory.get_balance(db, tenant.store.id, mug.id).reserved == 0
    assert inventory.get_balance(db, tenant.store.id, bowl.id).reserved == 2
    assert inventory.reconcile(db, tenant.store.id) == []
