"""Commerce fixtures for read-side API tests: products, stock, orders, exceptions, imports.

Stock goes through ``inventory.service.record_movement`` and orders through ``orders.service``
plus ``inventory.service.sync_reservations``, so balances, reservations and events are produced by
the real write path. Exceptions, imports and evaluation runs are inserted directly: their engines
are not under test here.
"""

import itertools
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.exceptions.models import (
    ActorType,
    EntityType,
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionCategory,
    ExceptionEntityLink,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    OperationalException,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.identity import service as identity_service
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission, Role, permissions_for
from app.domains.imports.models import DataImport, ImportStatus, ImportType
from app.domains.inventory import service as inventory
from app.domains.inventory.models import MovementSource, MovementType
from app.domains.orders import service as orders
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    Order,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
)
from app.domains.orders.state import AXES
from tests.factories import Tenant

_refs = itertools.count(1)

# Every read router takes "now" from its own module attribute; tests freeze them all at once.
FROZEN_ROUTER_MODULES = (
    "app.domains.catalog.router",
    "app.domains.orders.router",
    "app.domains.inventory.router",
    "app.domains.analytics.router",
)


def freeze_now(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    for module in FROZEN_ROUTER_MODULES:
        monkeypatch.setattr(f"{module}.utcnow", lambda: now)


def strip_permission(monkeypatch: pytest.MonkeyPatch, permission: Permission) -> None:
    """Simulate a role without ``permission`` (no built-in role lacks the read permissions)."""

    def reduced(role: Role) -> frozenset[Permission]:
        return permissions_for(role) - {permission}

    monkeypatch.setattr(identity_service, "permissions_for", reduced)


def create_supplier(
    db: Session, tenant: Tenant, name: str, *, lead_time_days: int | None = None
) -> Supplier:
    supplier = Supplier(store_id=tenant.store.id, name=name, lead_time_days=lead_time_days)
    db.add(supplier)
    db.flush()
    return supplier


def create_product(
    db: Session,
    tenant: Tenant,
    sku: str,
    *,
    name: str | None = None,
    category: str | None = None,
    status: ProductStatus = ProductStatus.ACTIVE,
    unit_price: str = "10.00",
    unit_cost: str | None = None,
    reorder_point: int = 0,
    reorder_quantity: int | None = None,
    supplier: Supplier | None = None,
) -> Product:
    product = Product(
        store_id=tenant.store.id,
        sku=sku,
        name=name or f"Product {sku}",
        category=category,
        status=status,
        unit_price=Decimal(unit_price),
        unit_cost=Decimal(unit_cost) if unit_cost is not None else None,
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
        supplier_id=supplier.id if supplier else None,
    )
    db.add(product)
    db.flush()
    return product


def count_stock(db: Session, tenant: Tenant, product: Product, qty: int, at: datetime) -> None:
    """A CYCLE_COUNT movement (BR-113) setting on-hand as of ``at``."""
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=MovementType.CYCLE_COUNT,
        quantity=qty,
        occurred_at=at,
        source=MovementSource.IMPORT,
        reference=f"CC-{product.sku}-{next(_refs)}",
    )


def move_stock(
    db: Session,
    tenant: Tenant,
    product: Product,
    movement_type: MovementType,
    qty: int,
    at: datetime,
    *,
    expected_at: datetime | None = None,
    note: str | None = None,
) -> None:
    inventory.record_movement(
        db,
        store_id=tenant.store.id,
        product_id=product.id,
        movement_type=movement_type,
        quantity=qty,
        occurred_at=at,
        source=MovementSource.IMPORT,
        reference=f"ADJ-{product.sku}-{next(_refs)}",
        expected_at=expected_at,
        note=note,
    )


@dataclass(frozen=True)
class Line:
    product: Product
    quantity: int
    unit_price: str = "10.00"
    line_discount: str = "0.00"


_DEFAULT_PAYMENT = {
    OrderStatus.CANCELLED: PaymentStatus.PENDING,
}


def create_order(
    db: Session,
    tenant: Tenant,
    number: str,
    *,
    status: OrderStatus,
    lines: Sequence[Line],
    placed_at: datetime,
    paid_at: datetime | None = None,
    ship_by: datetime | None = None,
    shipped_at: datetime | None = None,
    delivered_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    payment_status: PaymentStatus | None = None,
    fulfillment_status: FulfillmentStatus | None = None,
    channel: SalesChannel = SalesChannel.WEB,
    customer_ref: str | None = None,
    discount_total: str = "0.00",
    shipping_total: str = "0.00",
    tax_total: str = "0.00",
    total: str | None = None,
    sla_hours: int = 48,
) -> Order:
    """Create or update an order through the real write path and sync its reservations.

    Payment and fulfillment default to the first value the axis matrix allows (§1.3). ``paid_at``
    defaults to ``placed_at`` when the payment axis requires it. ``total`` defaults to the BR-205
    expected total, so a mismatch is only present when a test asks for one.
    """
    payment = payment_status or _DEFAULT_PAYMENT.get(status) or AXES[status][0][0]
    fulfillment = fulfillment_status or AXES[status][1][0]
    if paid_at is None and payment in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
        paid_at = placed_at
    if cancelled_at is None and status is OrderStatus.CANCELLED:
        cancelled_at = placed_at + timedelta(hours=1)
    subtotal = sum(
        (Decimal(line.unit_price) * line.quantity - Decimal(line.line_discount) for line in lines),
        Decimal("0"),
    )
    expected = subtotal - Decimal(discount_total) + Decimal(shipping_total) + Decimal(tax_total)
    snapshot = orders.OrderSnapshot(
        order_number=number,
        channel=channel,
        customer_ref=customer_ref,
        status=status,
        payment_status=payment,
        fulfillment_status=fulfillment,
        placed_at=placed_at,
        paid_at=paid_at,
        ship_by=ship_by,
        shipped_at=shipped_at,
        delivered_at=delivered_at,
        cancelled_at=cancelled_at,
        currency="USD",
        subtotal=subtotal,
        discount_total=Decimal(discount_total),
        shipping_total=Decimal(shipping_total),
        tax_total=Decimal(tax_total),
        total=Decimal(total) if total is not None else expected,
        carrier=None,
        tracking_number=None,
    )
    order, _ = orders.upsert_order(
        db,
        store_id=tenant.store.id,
        snapshot=snapshot,
        fulfillment_sla_hours=sla_hours,
        source=ChangeSource.IMPORT,
    )
    for number_in_order, line in enumerate(lines, start=1):
        orders.upsert_order_item(
            db,
            order=order,
            line=orders.OrderLineSnapshot(
                line_number=number_in_order,
                product_id=line.product.id,
                sku=line.product.sku,
                quantity=line.quantity,
                unit_price=Decimal(line.unit_price),
                line_discount=Decimal(line.line_discount),
            ),
        )
    inventory.sync_reservations(db, tenant.store.id, [order.id], now=placed_at)
    db.commit()
    return order


_TYPE_CATEGORY = {
    "INVENTORY": "INVENTORY",
    "ORDER_FULFILLMENT": "FULFILLMENT",
    "ORDER_STALLED": "FULFILLMENT",
    "ORDER_REFUND": "PAYMENT",
    "DATA": "DATA_QUALITY",
}


def _category(exception_type: ExceptionType) -> ExceptionCategory:
    for prefix, category in _TYPE_CATEGORY.items():
        if exception_type.value.startswith(prefix):
            return ExceptionCategory(category)
    raise ValueError(exception_type)  # pragma: no cover


_BAND_FLOOR = ((70, PriorityBand.P1), (50, PriorityBand.P2), (30, PriorityBand.P3))


def band_for(score: int) -> PriorityBand:
    return next((band for floor, band in _BAND_FLOOR if score >= floor), PriorityBand.P4)


def create_exception(
    db: Session,
    tenant: Tenant,
    exception_type: ExceptionType,
    *,
    entity: Product | Order,
    first_detected_at: datetime,
    severity: Severity = Severity.HIGH,
    status: ExceptionStatus = ExceptionStatus.OPEN,
    priority_score: int = 50,
    due_at: datetime | None = None,
    resolved_at: datetime | None = None,
    resolution_code: ResolutionCode | None = None,
    assignee: User | None = None,
    affected: Sequence[Product | Order] = (),
    reopened_at: Sequence[datetime] = (),
    title: str | None = None,
) -> OperationalException:
    """Insert an exception row with its entity links (and REOPENED events, if any)."""
    entity_type = EntityType.PRODUCT if isinstance(entity, Product) else EntityType.ORDER
    exc = OperationalException(
        store_id=tenant.store.id,
        reference=f"EXC-{1000 + next(_refs)}",
        exception_type=exception_type,
        category=_category(exception_type),
        rule_id=f"{exception_type.value}@1",
        dedup_key=f"{exception_type.value}:{entity_type.value}:{entity.id}:{uuid.uuid4().hex[:6]}",
        primary_entity_type=entity_type,
        primary_entity_id=entity.id,
        status=status,
        severity=severity,
        priority_score=priority_score,
        priority_band=band_for(priority_score),
        priority_breakdown={},
        title=title or f"{exception_type.value} on {entity.id}",
        evidence={},
        calculation={},
        recommended_action="Investigate.",
        exposure_amount=Decimal("0"),
        affected_order_count=0,
        due_at=due_at or first_detected_at + timedelta(hours=24),
        assignee_id=assignee.id if assignee else None,
        first_detected_at=first_detected_at,
        last_detected_at=first_detected_at,
        resolved_at=resolved_at,
        resolution_code=resolution_code,
        resolution_actor=(
            None
            if resolution_code is None
            else ActorType.SYSTEM
            if resolution_code in (ResolutionCode.CONDITION_CLEARED, ResolutionCode.SUPERSEDED)
            else ActorType.USER
        ),
        reopen_count=len(reopened_at),
    )
    db.add(exc)
    db.flush()
    links = [(entity_type, entity.id, LinkRole.PRIMARY)] + [
        (
            EntityType.PRODUCT if isinstance(other, Product) else EntityType.ORDER,
            other.id,
            LinkRole.AFFECTED,
        )
        for other in affected
    ]
    for link_type, link_id, role in links:
        db.add(
            ExceptionEntityLink(
                exception_id=exc.id,
                store_id=tenant.store.id,
                entity_type=link_type,
                entity_id=link_id,
                role=role,
            )
        )
    for at in reopened_at:
        db.add(
            ExceptionEvent(
                exception_id=exc.id,
                store_id=tenant.store.id,
                event_type=ExceptionEventType.REOPENED,
                actor_type=ActorType.SYSTEM,
                from_status=ExceptionStatus.RESOLVED,
                to_status=ExceptionStatus.REOPENED,
                payload={"reason": "VERIFICATION_FAILED"},
                occurred_at=at,
            )
        )
    db.commit()
    return exc


def create_import(
    db: Session,
    tenant: Tenant,
    import_type: ImportType,
    *,
    status: ImportStatus,
    applied_at: datetime | None,
) -> DataImport:
    record = DataImport(
        store_id=tenant.store.id,
        import_type=import_type,
        status=status,
        original_filename=f"{import_type.value}.csv",
        file_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        size_bytes=128,
        row_count=1,
        summary={},
        applied_at=applied_at,
    )
    db.add(record)
    db.commit()
    return record


def create_evaluation_run(
    db: Session,
    tenant: Tenant,
    *,
    started_at: datetime,
    status: EvaluationStatus = EvaluationStatus.SUCCEEDED,
    trigger: EvaluationTrigger = EvaluationTrigger.SCHEDULED,
) -> EvaluationRun:
    run = EvaluationRun(
        store_id=tenant.store.id,
        trigger=trigger,
        status=status,
        as_of=started_at,
        rules=[],
        counts={},
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=2),
        duration_ms=2000,
    )
    db.add(run)
    db.commit()
    return run


def all_pages(fetch: Callable[[int], dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield every item across pages of a list endpoint (``fetch(page) -> body``)."""
    page = 1
    while True:
        body = fetch(page)
        yield from body["items"]
        if page * body["page_size"] >= body["total"]:
            return
        page += 1
