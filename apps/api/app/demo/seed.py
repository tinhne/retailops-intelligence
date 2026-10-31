"""Deterministic demo dataset for the fictional store "Kestrel Home & Kitchen" (T-056).

The dataset is generated relative to ``now`` so it always looks current, and it is internally
consistent: every order passes the order state machine, stock flows through the inventory ledger
and reservations, and exceptions come from the real rule engine, never inserted by hand. Scenario
products are engineered so every exception type in EXCEPTION_CATALOG.md appears at least once.

Usage: ``python -m app.demo`` (see ``app/demo/__main__.py``).
"""

import random
import secrets
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.demo.catalog_data import CATEGORIES, STAFF, SUPPLIERS
from app.demo.purge import purge_organization
from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.identity.models import Membership, Organization, Store, StoreSettings, User
from app.domains.identity.permissions import Role
from app.domains.identity.security import hash_password
from app.domains.inventory import service as inventory
from app.domains.inventory.models import InventoryMovement, MovementSource, MovementType
from app.domains.orders import service as orders
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    Order,
    OrderStatus,
    PaymentStatus,
    SalesChannel,
)

DEMO_ORG_SLUG = "kestrel-commerce"
DEMO_TIMEZONE = "America/New_York"
CENT = Decimal("0.01")
TAX_RATE = Decimal("0.08")
FREE_SHIPPING_THRESHOLD = Decimal("75.00")
FLAT_SHIPPING = Decimal("6.95")

S = OrderStatus
P = PaymentStatus
F = FulfillmentStatus


class DemoSeedRefusedError(RuntimeError):
    """The seed would have to delete data that is not demo data."""


@dataclass
class DemoSummary:
    organization_id: uuid.UUID
    store_id: uuid.UUID
    products: int
    orders: int
    order_lines: int
    movements: int
    scenarios: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class _Line:
    product: Product
    quantity: int


@dataclass
class _OrderPlan:
    number: str
    placed_at: datetime
    status: OrderStatus
    payment: PaymentStatus
    fulfillment: FulfillmentStatus
    lines: list[_Line]
    paid_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    channel: SalesChannel = SalesChannel.WEB
    total_adjustment: Decimal = Decimal("0")  # injected data-quality defect


class _Generator:
    def __init__(self, db: Session, now: datetime, seed: int) -> None:
        self.db = db
        self.now = now
        self.rng = random.Random(seed)  # noqa: S311 - reproducible demo data, not security
        self.tz = ZoneInfo(DEMO_TIMEZONE)
        self.order_seq = 10_480
        self.customer_seq = 20_150
        self.plans: list[_OrderPlan] = []

    # ------------------------------------------------------------------ tenancy and people
    def create_tenant(self, staff_password: str) -> tuple[Organization, Store, dict[str, User]]:
        org = Organization(name="Kestrel Commerce", slug=DEMO_ORG_SLUG, is_demo=True)
        self.db.add(org)
        self.db.flush()
        store = Store(
            organization_id=org.id,
            name="Kestrel Home & Kitchen",
            code="KHK",
            currency="USD",
            timezone=DEMO_TIMEZONE,
        )
        self.db.add(store)
        self.db.flush()
        self.db.add(StoreSettings(store_id=store.id))

        users: dict[str, User] = {}
        staff_hash = hash_password(staff_password)
        for spec in STAFF:
            user = User(email=spec.email, full_name=spec.full_name, password_hash=staff_hash)
            self.db.add(user)
            self.db.flush()
            self.db.add(Membership(user_id=user.id, organization_id=org.id, role=Role(spec.role)))
            users[spec.role if spec.role not in users else spec.email] = user
        # The shared public demo account signs in via /auth/demo only; its password is unusable.
        viewer = User(
            email="demo@kestrel.example",
            full_name="Demo Visitor",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        self.db.add(viewer)
        self.db.flush()
        self.db.add(Membership(user_id=viewer.id, organization_id=org.id, role=Role.VIEWER))
        self.db.flush()
        return org, store, users

    # ------------------------------------------------------------------ catalog
    def create_catalog(self, store: Store) -> list[Product]:
        suppliers = []
        for spec in SUPPLIERS:
            supplier = Supplier(
                store_id=store.id, name=spec.name, lead_time_days=spec.lead_time_days
            )
            self.db.add(supplier)
            suppliers.append(supplier)
        self.db.flush()

        products: list[Product] = []
        for category in CATEGORIES:
            number = 1
            for item in category.items:
                for variant in category.variants:
                    low, high = category.price_range
                    price = Decimal(self.rng.randint(low, high)) - Decimal("0.05")
                    cost = (price * Decimal(self.rng.uniform(0.38, 0.58))).quantize(CENT)
                    reorder_point = self.rng.choice((6, 8, 10, 12, 15, 20, 25))
                    status = ProductStatus.ACTIVE
                    roll = self.rng.random()
                    if roll < 0.03:
                        status = ProductStatus.DRAFT
                    elif roll < 0.06:
                        status = ProductStatus.ARCHIVED
                    product = Product(
                        store_id=store.id,
                        sku=f"KHK-{category.code}-{number:03d}",
                        name=f"{variant} {item}",
                        category=category.name,
                        status=status,
                        unit_price=price,
                        unit_cost=cost,
                        reorder_point=reorder_point,
                        reorder_quantity=reorder_point * 3,
                        supplier_id=suppliers[category.supplier_index].id,
                    )
                    self.db.add(product)
                    products.append(product)
                    number += 1
        self.db.flush()
        return products

    # ------------------------------------------------------------------ orders
    def _next_number(self) -> str:
        self.order_seq += 1
        return f"KHK-{self.order_seq}"

    def _lines(self, sellable: list[Product], weights: list[float]) -> list[_Line]:
        count = self.rng.choices((1, 2, 3, 4), weights=(55, 28, 12, 5))[0]
        chosen: dict[uuid.UUID, _Line] = {}
        for product in self.rng.choices(sellable, weights=weights, k=count):
            qty = self.rng.choices((1, 2, 3), weights=(80, 15, 5))[0]
            if product.id in chosen:
                chosen[product.id].quantity += qty
            else:
                chosen[product.id] = _Line(product, qty)
        return list(chosen.values())

    def _lifecycle(self, plan: _OrderPlan) -> None:
        """Fill status, payment, fulfillment and timestamps consistent with the order's age."""
        age = self.now - plan.placed_at
        rng = self.rng
        roll = rng.random()
        paid_at = plan.placed_at + timedelta(minutes=rng.randint(1, 20))
        handling = timedelta(hours=rng.uniform(5, 30))
        transit = timedelta(days=rng.uniform(1.5, 5))

        if roll < 0.02:
            plan.status, plan.payment = S.PAYMENT_FAILED, P.FAILED
            return
        if roll < 0.05:
            plan.status, plan.payment = S.CANCELLED, P.PENDING
            plan.cancelled_at = plan.placed_at + timedelta(hours=rng.uniform(0.5, 6))
            return

        plan.paid_at = paid_at
        shipped_at = paid_at + handling
        delivered_at = shipped_at + transit
        if shipped_at >= self.now:
            # Still in the warehouse: progress depends on time since payment.
            since_paid = self.now - paid_at
            if since_paid < timedelta(hours=3):
                plan.status, plan.payment, plan.fulfillment = S.PAID, P.PAID, F.UNFULFILLED
            elif since_paid < timedelta(hours=10):
                plan.status, plan.payment, plan.fulfillment = S.PROCESSING, P.PAID, F.IN_PROGRESS
            else:
                plan.status, plan.payment, plan.fulfillment = S.READY_TO_SHIP, P.PAID, F.IN_PROGRESS
            return
        plan.shipped_at = shipped_at
        if delivered_at >= self.now:
            plan.status, plan.payment, plan.fulfillment = S.SHIPPED, P.PAID, F.SHIPPED
            return
        plan.delivered_at = delivered_at
        plan.status, plan.payment, plan.fulfillment = S.DELIVERED, P.PAID, F.DELIVERED
        if age > timedelta(days=12) and roll > 0.965:
            plan.status, plan.payment, plan.fulfillment = S.REFUNDED, P.REFUNDED, F.RETURNED
        elif age > timedelta(days=8) and roll > 0.955:
            plan.status = S.RETURN_REQUESTED

    def plan_history(self, products: list[Product], days: int = 60) -> None:
        sellable = [p for p in products if p.status is ProductStatus.ACTIVE]
        # Long-tail popularity: a few best sellers, many slow movers.
        weights = [1 / (rank + 3) ** 0.9 for rank in range(len(sellable))]
        self.rng.shuffle(weights)
        start_local = (self.now - timedelta(days=days)).astimezone(self.tz)
        for day in range(days + 1):
            day_start = datetime.combine(
                (start_local + timedelta(days=day)).date(), time(0), tzinfo=self.tz
            )
            weekday_boost = 1.25 if day_start.weekday() in (5, 6) else 1.0
            for _ in range(int(self.rng.gauss(24, 4) * weekday_boost)):
                # Orders cluster in the daytime and evening (local time).
                hour = min(23.99, max(0.0, self.rng.gauss(14.5, 4.5)))
                placed = day_start + timedelta(hours=hour)
                placed_utc = placed.astimezone(self.now.tzinfo)
                if placed_utc >= self.now - timedelta(minutes=5):
                    continue
                plan = _OrderPlan(
                    number=self._next_number(),
                    placed_at=placed_utc,
                    status=S.CREATED,
                    payment=P.PENDING,
                    fulfillment=F.UNFULFILLED,
                    lines=self._lines(sellable, weights),
                    channel=self.rng.choices(
                        (SalesChannel.WEB, SalesChannel.MARKETPLACE, SalesChannel.POS),
                        weights=(70, 25, 5),
                    )[0],
                )
                self._lifecycle(plan)
                self.plans.append(plan)
        self.plans.sort(key=lambda p: p.placed_at)

    def add_scenario_order(
        self,
        lines: list[_Line],
        *,
        status: OrderStatus,
        placed_hours_ago: float,
        paid_after_minutes: float = 8,
        cancelled_hours_ago: float | None = None,
        payment: PaymentStatus | None = None,
        total_adjustment: Decimal = Decimal("0"),
    ) -> _OrderPlan:
        placed = self.now - timedelta(hours=placed_hours_ago)
        fulfillment = {
            S.PROCESSING: F.IN_PROGRESS,
            S.READY_TO_SHIP: F.IN_PROGRESS,
            S.SHIPPED: F.SHIPPED,
        }.get(status, F.UNFULFILLED)
        default_payment = {
            S.CREATED: P.PENDING,
            S.PAYMENT_PENDING: P.PENDING,
        }.get(status, P.PAID)
        plan = _OrderPlan(
            number=self._next_number(),
            placed_at=placed,
            status=status,
            payment=payment or default_payment,
            fulfillment=fulfillment,
            lines=lines,
            total_adjustment=total_adjustment,
        )
        if plan.payment is P.PAID:
            plan.paid_at = placed + timedelta(minutes=paid_after_minutes)
        if status is S.SHIPPED:
            assert plan.paid_at is not None
            plan.shipped_at = plan.paid_at + timedelta(hours=6)
        if cancelled_hours_ago is not None:
            plan.cancelled_at = self.now - timedelta(hours=cancelled_hours_ago)
        self.plans.append(plan)
        return plan

    def persist_orders(self, store: Store) -> list[uuid.UUID]:
        order_ids: list[uuid.UUID] = []
        for plan in self.plans:
            subtotal = Decimal("0")
            for line in plan.lines:
                subtotal += line.product.unit_price * line.quantity
            discount = (subtotal * Decimal("0.10")).quantize(CENT) if subtotal > 150 else Decimal(0)
            shipping = Decimal("0") if subtotal >= FREE_SHIPPING_THRESHOLD else FLAT_SHIPPING
            tax = ((subtotal - discount) * TAX_RATE).quantize(CENT)
            total = subtotal - discount + shipping + tax + plan.total_adjustment
            self.customer_seq += self.rng.randint(1, 3)
            snapshot = orders.OrderSnapshot(
                order_number=plan.number,
                channel=plan.channel,
                customer_ref=f"CUST-{self.customer_seq}",
                status=plan.status,
                payment_status=plan.payment,
                fulfillment_status=plan.fulfillment,
                placed_at=plan.placed_at,
                paid_at=plan.paid_at,
                ship_by=None,
                shipped_at=plan.shipped_at,
                delivered_at=plan.delivered_at,
                cancelled_at=plan.cancelled_at,
                currency="USD",
                subtotal=subtotal,
                discount_total=discount,
                shipping_total=shipping,
                tax_total=tax,
                total=total,
                carrier="UPS" if plan.shipped_at else None,
                tracking_number=f"1Z{self.rng.randint(10**9, 10**10 - 1)}"
                if plan.shipped_at
                else None,
            )
            order, _ = orders.upsert_order(
                self.db,
                store_id=store.id,
                snapshot=snapshot,
                fulfillment_sla_hours=48,
                source=ChangeSource.IMPORT,
            )
            for number, line in enumerate(plan.lines, start=1):
                orders.upsert_order_item(
                    self.db,
                    order=order,
                    line=orders.OrderLineSnapshot(
                        line_number=number,
                        product_id=line.product.id,
                        sku=line.product.sku,
                        quantity=line.quantity,
                        unit_price=line.product.unit_price,
                        line_discount=Decimal("0"),
                    ),
                )
            order_ids.append(order.id)
        return order_ids

    # ------------------------------------------------------------------ inventory
    def opening_counts(self, store: Store, products: list[Product]) -> None:
        opening = self.now - timedelta(days=62)
        for product in products:
            inventory.record_movement(
                self.db,
                store_id=store.id,
                product_id=product.id,
                movement_type=MovementType.CYCLE_COUNT,
                quantity=self.rng.randint(180, 420),
                occurred_at=opening,
                source=MovementSource.IMPORT,
                reference=f"COUNT-OPEN-{product.sku}",
                note="Opening stock count",
            )

    def morning_count_time(self) -> datetime:
        local_now = self.now.astimezone(self.tz)
        count_local = datetime.combine(local_now.date(), time(6, 30), tzinfo=self.tz)
        if count_local >= local_now:
            count_local -= timedelta(days=1)
        return count_local.astimezone(self.now.tzinfo)


def _units_shipped_after(db: Session, store_id: uuid.UUID, after: datetime) -> Counter[uuid.UUID]:
    rows = db.execute(
        select(InventoryMovement.product_id, func.sum(-InventoryMovement.on_hand_delta))
        .where(
            InventoryMovement.store_id == store_id,
            InventoryMovement.movement_type == MovementType.SHIPMENT,
            InventoryMovement.occurred_at > after,
        )
        .group_by(InventoryMovement.product_id)
    ).all()
    return Counter({pid: int(qty) for pid, qty in rows})


def seed_demo(
    db: Session, *, now: datetime, seed: int = 20261031, staff_password: str | None = None
) -> DemoSummary:
    """Replace the demo organization with a freshly generated dataset. Caller commits."""
    existing = db.scalar(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    if existing is not None:
        if not existing.is_demo:
            # ADR-0011: the reset may only ever delete a demo organization's data.
            raise DemoSeedRefusedError(
                f"Organization '{DEMO_ORG_SLUG}' exists but is not a demo organization."
            )
        purge_organization(db, existing.id)
    db.execute(delete(User).where(User.email.like("%@kestrel.example")))
    db.flush()

    gen = _Generator(db, now, seed)
    org, store, _users = gen.create_tenant(staff_password or secrets.token_urlsafe(18))
    products = gen.create_catalog(store)
    active = [p for p in products if p.status is ProductStatus.ACTIVE]
    gen.opening_counts(store, products)
    gen.plan_history(products)

    # ---- engineered scenarios (one product per condition, chosen deterministically)
    picks = gen.rng.sample(active, 12)
    oversold, oversold_2, risk, out_of_stock, low_1, low_2, low_3, negative = picks[:8]
    scenarios: dict[str, list[str]] = defaultdict(list)

    # Oversold: several committed orders exceed the stock left after this morning's count.
    for hours in (30, 20, 9, 4):
        gen.add_scenario_order([_Line(oversold, 2)], status=S.PROCESSING, placed_hours_ago=hours)
    for hours in (16, 6):
        gen.add_scenario_order([_Line(oversold_2, 1)], status=S.PAID, placed_hours_ago=hours)
    scenarios["INVENTORY_OVERSOLD"] += [oversold.sku, oversold_2.sku]
    # Oversell risk: unpaid orders exceed what is still available.
    for hours in (2, 1):
        gen.add_scenario_order([_Line(risk, 3)], status=S.PAYMENT_PENDING, placed_hours_ago=hours)
    scenarios["INVENTORY_OVERSELL_RISK"].append(risk.sku)
    scenarios["INVENTORY_OUT_OF_STOCK"].append(out_of_stock.sku)
    scenarios["INVENTORY_BELOW_REORDER_POINT"] += [low_1.sku, low_2.sku, low_3.sku]
    scenarios["DATA_NEGATIVE_ON_HAND"].append(negative.sku)

    others = [p for p in active if p not in picks]
    # Fulfillment overdue (48h SLA): ~10h, ~40h and ~90h past the ship-by deadline.
    for hours_ago, status in ((58, S.PAID), (88, S.PROCESSING), (138, S.READY_TO_SHIP)):
        plan = gen.add_scenario_order(
            [_Line(gen.rng.choice(others), 1)], status=status, placed_hours_ago=hours_ago
        )
        scenarios["ORDER_FULFILLMENT_OVERDUE"].append(plan.number)
    # Stalled after payment: paid 15h and 40h ago, still not in processing.
    for hours_ago in (15, 40):
        plan = gen.add_scenario_order(
            [_Line(gen.rng.choice(others), 1)], status=S.PAID, placed_hours_ago=hours_ago
        )
        scenarios["ORDER_STALLED_AFTER_PAYMENT"].append(plan.number)
    # Cancelled after payment, refund not yet issued (30h and 80h after cancellation).
    for placed, cancelled in ((40, 30), (100, 80)):
        plan = gen.add_scenario_order(
            [_Line(gen.rng.choice(others), 1)],
            status=S.CANCELLED,
            payment=P.PAID,
            placed_hours_ago=placed,
            cancelled_hours_ago=cancelled,
        )
        scenarios["ORDER_REFUND_PENDING"].append(plan.number)
    # Data quality: totals that do not reconcile with their lines.
    for adjustment in (Decimal("12.50"), Decimal("-0.40")):
        plan = gen.add_scenario_order(
            [_Line(gen.rng.choice(others), 1)],
            status=S.SHIPPED,
            placed_hours_ago=70,
            total_adjustment=adjustment,
        )
        scenarios["DATA_ORDER_TOTAL_MISMATCH"].append(plan.number)

    order_ids = gen.persist_orders(store)
    inventory.sync_reservations(db, store.id, order_ids, now=now)

    # ---- this morning's cycle count sets the engineered stock positions
    count_at = gen.morning_count_time()
    shipped_after = _units_shipped_after(db, store.id, count_at)
    targets: dict[uuid.UUID, int] = {}
    for product in products:
        balance = inventory.get_balance(db, store.id, product.id)
        reserved = balance.reserved
        rop = product.reorder_point
        if product is oversold:
            desired = max(0, reserved - 3)
        elif product is oversold_2:
            desired = max(0, reserved - 1)
        elif product is risk:
            desired = reserved + 4  # 4 available vs 6 pending
        elif product is out_of_stock:
            desired = reserved
        elif product in (low_1, low_2, low_3):
            desired = reserved + gen.rng.randint(1, max(1, rop - 1))
        elif product is negative:
            desired = reserved + 2
        else:
            desired = reserved + gen.rng.randint(int(rop * 1.6) + 2, rop * 6 + 10)
        targets[product.id] = desired
    for product in products:
        inventory.record_movement(
            db,
            store_id=store.id,
            product_id=product.id,
            movement_type=MovementType.CYCLE_COUNT,
            quantity=targets[product.id] + shipped_after[product.id],
            occurred_at=count_at,
            source=MovementSource.IMPORT,
            reference=f"COUNT-{count_at:%Y%m%d}-{product.sku}",
            note="Morning cycle count",
        )

    # Replenishment already on the way for two of the low-stock items.
    for product, days in ((low_1, 4), (out_of_stock, 9)):
        inventory.record_movement(
            db,
            store_id=store.id,
            product_id=product.id,
            movement_type=MovementType.INCOMING_EXPECTED,
            quantity=(product.reorder_quantity or 30),
            occurred_at=count_at + timedelta(minutes=30),
            expected_at=now + timedelta(days=days),
            source=MovementSource.IMPORT,
            reference=f"PO-{count_at:%m%d}-{product.sku}",
            note="Purchase order confirmed by supplier",
        )
    # A damage write-off larger than the counted stock: a data-quality defect.
    inventory.record_movement(
        db,
        store_id=store.id,
        product_id=negative.id,
        movement_type=MovementType.DAMAGE,
        quantity=targets[negative.id]
        + 3
        + inventory.get_balance(db, store.id, negative.id).reserved,
        occurred_at=min(now - timedelta(minutes=30), count_at + timedelta(hours=2)),
        source=MovementSource.IMPORT,
        reference=f"DMG-{count_at:%m%d}-{negative.sku}",
        note="Damaged in receiving (quantity entered per case, not per unit)",
    )
    db.flush()

    movements = db.scalar(
        select(func.count())
        .select_from(InventoryMovement)
        .where(InventoryMovement.store_id == store.id)
    )
    line_count = sum(len(p.lines) for p in gen.plans)
    return DemoSummary(
        organization_id=org.id,
        store_id=store.id,
        products=len(products),
        orders=db.scalar(select(func.count()).select_from(Order).where(Order.store_id == store.id))
        or 0,
        order_lines=line_count,
        movements=movements or 0,
        scenarios=dict(scenarios),
    )
