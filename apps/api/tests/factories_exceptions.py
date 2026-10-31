"""Test helpers for the exception engine and lifecycle.

Two families:
- ``facts_*`` / ``snapshot``: hand-built snapshot dataclasses for pure rule unit tests.
- ``make_*`` / ``evaluate``: real rows through the catalog, orders and inventory services for
  integration tests against PostgreSQL.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.exceptions.engine import run_evaluation
from app.domains.exceptions.models import (
    EvaluationRun,
    EvaluationTrigger,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionType,
    OperationalException,
)
from app.domains.exceptions.snapshot import (
    DemandLine,
    EvaluationSnapshot,
    OrderFacts,
    ProductFacts,
    RuleSettings,
)
from app.domains.inventory import service as inventory
from app.domains.inventory.models import MovementSource, MovementType
from app.domains.orders import service as orders
from app.domains.orders.models import (
    ChangeSource,
    Order,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
    ShipBySource,
)
from app.domains.orders.state import AXES
from tests.factories import Tenant, login

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
STORE_ID = uuid.UUID("00000000-0000-0000-0000-00000000a001")
SETTINGS = RuleSettings()
_NS = uuid.UUID("6f1c2d3e-0000-4000-8000-000000000000")


def stable_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"{kind}:{key}")


# --- pure snapshot builders ----------------------------------------------------------------------


def facts_product(
    sku: str = "KH-MUG-01",
    *,
    on_hand: int = 10,
    reserved: int = 0,
    incoming: int = 0,
    incoming_eta: datetime | None = None,
    reorder_point: int = 5,
    reorder_quantity: int | None = None,
    unit_price: str = "20.00",
    status: ProductStatus = ProductStatus.ACTIVE,
    units_sold: int = 0,
    supplier_name: str | None = "Harbor Ceramics",
    lead_time_days: int | None = 14,
    last_cycle_count_at: datetime | None = None,
    name: str = "Stoneware Mug",
) -> ProductFacts:
    return ProductFacts(
        id=stable_id("product", sku),
        sku=sku,
        name=name,
        status=status,
        unit_price=Decimal(unit_price),
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
        supplier_id=stable_id("supplier", supplier_name) if supplier_name else None,
        supplier_name=supplier_name,
        lead_time_days=lead_time_days,
        on_hand=on_hand,
        reserved=reserved,
        incoming=incoming,
        incoming_eta=incoming_eta,
        last_cycle_count_at=last_cycle_count_at,
        units_sold_in_window=units_sold,
    )


def facts_line(
    product: ProductFacts,
    order_number: str,
    quantity: int,
    *,
    unit_price: str = "20.00",
    status: OrderStatus = OrderStatus.PAID,
    paid_at: datetime | None = T0,
    placed_at: datetime | None = None,
    ship_by: datetime | None = None,
    line_number: int = 1,
) -> DemandLine:
    return DemandLine(
        order_id=stable_id("order", order_number),
        order_number=order_number,
        order_status=status,
        placed_at=placed_at or (paid_at or T0) - timedelta(minutes=5),
        paid_at=paid_at,
        ship_by=ship_by if ship_by is not None else (paid_at or T0) + timedelta(hours=48),
        order_item_id=stable_id("item", f"{order_number}:{line_number}"),
        line_number=line_number,
        product_id=product.id,
        sku=product.sku,
        quantity=quantity,
        unit_price=Decimal(unit_price),
    )


def facts_order(
    order_number: str = "KHK-1001",
    *,
    status: OrderStatus = OrderStatus.PAID,
    payment_status: PaymentStatus | None = None,
    total: str = "120.00",
    paid_at: datetime | None = T0,
    placed_at: datetime | None = None,
    ship_by: datetime | None = None,
    ship_by_source: ShipBySource | None = ShipBySource.STORE_SLA,
    cancelled_at: datetime | None = None,
    line_count: int = 1,
    line_sum: str | None = None,
    discount_total: str = "0.00",
    shipping_total: str = "0.00",
    tax_total: str = "0.00",
) -> OrderFacts:
    payment = payment_status or AXES[status][0][0]
    fulfillment = AXES[status][1][0]
    return OrderFacts(
        id=stable_id("order", order_number),
        order_number=order_number,
        status=status,
        payment_status=payment,
        fulfillment_status=fulfillment,
        placed_at=placed_at or (paid_at or T0) - timedelta(minutes=5),
        paid_at=paid_at,
        ship_by=ship_by
        if ship_by is not None
        else (paid_at + timedelta(hours=48) if paid_at else None),
        ship_by_source=ship_by_source,
        cancelled_at=cancelled_at,
        currency="USD",
        subtotal=Decimal(line_sum or total),
        discount_total=Decimal(discount_total),
        shipping_total=Decimal(shipping_total),
        tax_total=Decimal(tax_total),
        total=Decimal(total),
        line_count=line_count,
        line_sum=Decimal(line_sum if line_sum is not None else total),
    )


def snapshot(
    *,
    products: Sequence[ProductFacts] = (),
    committed: Sequence[DemandLine] = (),
    pending: Sequence[DemandLine] = (),
    orders_: Sequence[OrderFacts] = (),
    as_of: datetime = T0,
    **extra: object,
) -> EvaluationSnapshot:
    return EvaluationSnapshot(
        store_id=STORE_ID,
        as_of=as_of,
        currency="USD",
        timezone="America/New_York",
        products={p.id: p for p in products},
        committed_lines=tuple(committed),
        pending_lines=tuple(pending),
        orders={o.id: o for o in orders_},
        **extra,  # type: ignore[arg-type]
    )


# --- database builders ---------------------------------------------------------------------------


def make_product(
    db: Session,
    tenant: Tenant,
    sku: str = "KH-MUG-01",
    *,
    reorder_point: int = 5,
    reorder_quantity: int | None = None,
    unit_price: str = "20.00",
    status: ProductStatus = ProductStatus.ACTIVE,
    supplier: tuple[str, int | None] | None = ("Harbor Ceramics", 14),
    name: str | None = None,
) -> Product:
    supplier_id = None
    if supplier is not None:
        existing = db.scalar(
            select(Supplier).where(
                Supplier.store_id == tenant.store.id, Supplier.name == supplier[0]
            )
        )
        if existing is None:
            existing = Supplier(
                store_id=tenant.store.id, name=supplier[0], lead_time_days=supplier[1]
            )
            db.add(existing)
            db.flush()
        supplier_id = existing.id
    product = Product(
        store_id=tenant.store.id,
        sku=sku,
        name=name or f"Product {sku}",
        status=status,
        unit_price=Decimal(unit_price),
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
        supplier_id=supplier_id,
    )
    db.add(product)
    db.flush()
    return product


_COUNT_SEQ = {"n": 0}


def set_stock(db: Session, tenant: Tenant, product: Product, on_hand: int, at: datetime) -> None:
    """Record a cycle count so on_hand becomes ``on_hand`` as of ``at``."""
    _COUNT_SEQ["n"] += 1
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=MovementType.CYCLE_COUNT,
        quantity=on_hand,
        occurred_at=at,
        source=MovementSource.IMPORT,
        reference=f"count-{product.sku}-{_COUNT_SEQ['n']}",
    )


def adjust_stock(
    db: Session,
    tenant: Tenant,
    product: Product,
    movement_type: MovementType,
    quantity: int,
    at: datetime,
) -> None:
    _COUNT_SEQ["n"] += 1
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=movement_type,
        quantity=quantity,
        occurred_at=at,
        source=MovementSource.IMPORT,
        reference=f"adj-{product.sku}-{_COUNT_SEQ['n']}",
    )


@dataclass
class LineSpec:
    product: Product
    quantity: int
    unit_price: str = "20.00"


@dataclass
class OrderSpec:
    number: str
    status: OrderStatus
    lines: list[LineSpec] = field(default_factory=list)
    placed_at: datetime = T0 - timedelta(hours=1)
    paid_at: datetime | None = None
    ship_by: datetime | None = None
    shipped_at: datetime | None = None
    cancelled_at: datetime | None = None
    payment_status: PaymentStatus | None = None
    total: str | None = None
    shipping_total: str = "0.00"
    tax_total: str = "0.00"
    discount_total: str = "0.00"


def make_order(db: Session, tenant: Tenant, spec: OrderSpec, *, now: datetime = T0) -> Order:
    """Upsert an order and its lines through the orders service, then sync reservations."""
    payment = spec.payment_status or AXES[spec.status][0][0]
    fulfillment = AXES[spec.status][1][0]
    paid_at = spec.paid_at
    if paid_at is None and payment in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
        paid_at = spec.placed_at
    lines_total = sum((Decimal(ln.unit_price) * ln.quantity for ln in spec.lines), Decimal(0))
    total = (
        Decimal(spec.total)
        if spec.total is not None
        else lines_total
        - Decimal(spec.discount_total)
        + Decimal(spec.shipping_total)
        + Decimal(spec.tax_total)
    )
    snapshot_row = orders.OrderSnapshot(
        order_number=spec.number,
        channel=SalesChannel.WEB,
        customer_ref=None,
        status=spec.status,
        payment_status=payment,
        fulfillment_status=fulfillment,
        placed_at=spec.placed_at,
        paid_at=paid_at,
        ship_by=spec.ship_by,
        shipped_at=spec.shipped_at,
        delivered_at=None,
        cancelled_at=spec.cancelled_at,
        currency="USD",
        subtotal=lines_total,
        discount_total=Decimal(spec.discount_total),
        shipping_total=Decimal(spec.shipping_total),
        tax_total=Decimal(spec.tax_total),
        total=total,
        carrier=None,
        tracking_number=None,
    )
    order, _ = orders.upsert_order(
        db,
        store_id=tenant.store.id,
        snapshot=snapshot_row,
        fulfillment_sla_hours=48,
        source=ChangeSource.IMPORT,
    )
    for number, ln in enumerate(spec.lines, start=1):
        orders.upsert_order_item(
            db,
            order=order,
            line=orders.OrderLineSnapshot(
                line_number=number,
                product_id=ln.product.id,
                sku=ln.product.sku,
                quantity=ln.quantity,
                unit_price=Decimal(ln.unit_price),
                line_discount=Decimal("0"),
            ),
        )
    inventory.sync_reservations(db, tenant.store.id, [order.id], now=now)
    db.flush()
    return order


def evaluate(
    db: Session,
    tenant: Tenant,
    as_of: datetime,
    *,
    rule_ids: list[str] | None = None,
    trigger: EvaluationTrigger = EvaluationTrigger.SCHEDULED,
) -> EvaluationRun:
    db.commit()
    run = run_evaluation(db, tenant.store.id, trigger=trigger, as_of=as_of, rule_ids=rule_ids)
    db.commit()
    return run


def exceptions_for(
    db: Session,
    tenant: Tenant,
    exception_type: ExceptionType | None = None,
    entity_id: uuid.UUID | None = None,
) -> list[OperationalException]:
    stmt = select(OperationalException).where(OperationalException.store_id == tenant.store.id)
    if exception_type is not None:
        stmt = stmt.where(OperationalException.exception_type == exception_type)
    if entity_id is not None:
        stmt = stmt.where(OperationalException.primary_entity_id == entity_id)
    db.expire_all()
    return list(db.scalars(stmt.order_by(OperationalException.first_detected_at)).all())


def one_exception(
    db: Session, tenant: Tenant, exception_type: ExceptionType, entity_id: uuid.UUID
) -> OperationalException:
    rows = exceptions_for(db, tenant, exception_type, entity_id)
    assert len(rows) == 1, [r.reference for r in rows]
    return rows[0]


def event_types(db: Session, exc: OperationalException) -> list[ExceptionEventType]:
    return list(
        db.scalars(
            select(ExceptionEvent.event_type)
            .where(ExceptionEvent.exception_id == exc.id)
            .order_by(ExceptionEvent.occurred_at)
        ).all()
    )


def user_client(app: FastAPI, email: str) -> tuple[TestClient, dict[str, str]]:
    """A separate client signed in as ``email``, with the CSRF header for mutations."""
    client = TestClient(app)
    token = login(client, email)
    return client, {"X-CSRF-Token": token}
