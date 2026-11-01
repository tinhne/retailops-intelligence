"""Ten fictional Vietnamese shops as importable CSV templates, and a loader that onboards them.

The loader uses the product's own onboarding path for every shop: provision the organization,
store and owner, then import the four CSV files (each import triggers an evaluation). Nothing is
written to the database directly, so a successful load also proves the templates are valid input.

    python -m app.demo.sample_stores generate --out ../../sample-data/stores-vn
    python -m app.demo.sample_stores load [--only moc-lan-fashion] [--replace]

Timestamps are generated relative to "now", so the data always looks current. Set
SAMPLE_OWNER_PASSWORD to give every sample owner the same password (local use only).
"""

import argparse
import csv
import hashlib
import io
import os
import random
import sys
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.demo.purge import purge_organization
from app.demo.vn_store_data import STORES, StoreDef, SupplierDef
from app.domains.exceptions import engine
from app.domains.exceptions.models import EvaluationTrigger, OperationalException
from app.domains.identity import security
from app.domains.identity.models import Organization, User
from app.domains.identity.provisioning import ProvisionRequest, provision
from app.domains.identity.service import store_context
from app.domains.imports import service as imports
from app.domains.imports.models import ImportMode, ImportStatus, ImportType
from app.domains.imports.parsing import Upload

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
CURRENCY = "VND"
DAYS = 30
FREE_SHIPPING = Decimal("500000")
SHIPPING_FEE = Decimal("30000")
VOUCHER_FROM = Decimal("1000000")
EXPOSURE_CAP = Decimal("100000000")
IMPORT_ORDER = ("products", "inventory_adjustments", "orders", "order_items")
SCENARIO_KEYS = (
    "INVENTORY_OVERSOLD",
    "INVENTORY_OVERSELL_RISK",
    "INVENTORY_OUT_OF_STOCK",
    "INVENTORY_BELOW_REORDER_POINT",
    "ORDER_FULFILLMENT_OVERDUE",
    "ORDER_STALLED_AFTER_PAYMENT",
    "ORDER_REFUND_PENDING",
    "DATA_ORDER_TOTAL_MISMATCH",
)
CENT = Decimal("0.01")


@dataclass
class Product:
    sku: str
    name: str
    category: str
    price: Decimal
    cost: Decimal
    reorder_point: int
    reorder_quantity: int
    supplier: SupplierDef
    status: str = "ACTIVE"


@dataclass
class Line:
    product: Product
    quantity: int


@dataclass
class Order:
    number: str
    placed: datetime
    lines: list[Line]
    channel: str
    customer: str
    status: str = "CREATED"
    payment: str = "PENDING"
    fulfillment: str = "UNFULFILLED"
    paid: datetime | None = None
    shipped: datetime | None = None
    delivered: datetime | None = None
    cancelled: datetime | None = None
    total_adjustment: Decimal = Decimal("0")


@dataclass
class StoreCsv:
    store: StoreDef
    files: dict[str, str]
    scenarios: dict[str, list[str]] = field(default_factory=dict)
    product_count: int = 0
    order_count: int = 0


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(TZ).isoformat(timespec="seconds") if moment else ""


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def _vnd(thousands: int) -> Decimal:
    return Decimal(thousands * 1000)


def _round_thousands(value: Decimal) -> Decimal:
    """VND amounts are quoted in whole thousands."""
    return (value / 1000).quantize(Decimal("1"), ROUND_HALF_UP) * 1000


class _Builder:
    def __init__(self, store: StoreDef, now: datetime) -> None:
        self.store = store
        self.now = now
        self.rng = random.Random(f"{store.slug}/v1")  # noqa: S311 - reproducible sample data
        self.seq = 1000
        self.products: list[Product] = []
        self.orders: list[Order] = []
        self.scenarios: dict[str, list[str]] = {key: [] for key in SCENARIO_KEYS}

    # -- catalog -------------------------------------------------------------------------------
    def catalog(self) -> None:
        for line in self.store.lines:
            number = 1
            for item in line.items:
                for variant in line.variants:
                    low, high = line.price_k
                    price = _vnd(self.rng.randint(low, high))
                    cost = _round_thousands(price * Decimal(self.rng.uniform(0.42, 0.62)))
                    rop = self.rng.choice((5, 8, 10, 12, 15))
                    self.products.append(
                        Product(
                            sku=f"{self.store.code}-{line.code}-{number:02d}",
                            name=f"{item} {variant}",
                            category=line.category,
                            price=price,
                            cost=cost,
                            reorder_point=rop,
                            reorder_quantity=rop * 3,
                            supplier=self.store.suppliers[line.supplier],
                        )
                    )
                    number += 1
        self.products[-1].status = "DRAFT"  # one unpublished product, never sold

    @property
    def active(self) -> list[Product]:
        return [p for p in self.products if p.status == "ACTIVE"]

    # -- orders --------------------------------------------------------------------------------
    def _number(self) -> str:
        self.seq += 1
        return f"{self.store.code}-{self.seq}"

    def _customer(self) -> str:
        return f"KH-{self.rng.randint(10000, 99999)}"

    def _lines(self, weights: list[float]) -> list[Line]:
        count = self.rng.choices((1, 2, 3), weights=(65, 27, 8))[0]
        chosen: dict[str, Line] = {}
        for product in self.rng.choices(self.active, weights=weights, k=count):
            quantity = self.rng.choices((1, 2), weights=(85, 15))[0]
            if product.sku in chosen:
                chosen[product.sku].quantity += quantity
            else:
                chosen[product.sku] = Line(product, quantity)
        return list(chosen.values())

    def _lifecycle(self, order: Order) -> None:
        rng, now, age = self.rng, self.now, self.now - order.placed
        roll = rng.random()
        if age < timedelta(hours=2) and roll < 0.3:
            order.status = "PAYMENT_PENDING"
            return
        if roll < 0.03:
            order.status = "CANCELLED"
            order.cancelled = min(
                order.placed + timedelta(hours=rng.uniform(0.5, 5)), now - timedelta(minutes=5)
            )
            return
        paid = order.placed + timedelta(minutes=rng.randint(2, 30))
        if paid >= now:
            order.status = "PAYMENT_PENDING"
            return
        order.paid, order.payment = paid, "PAID"
        shipped = paid + timedelta(hours=rng.uniform(4, 30))
        if shipped >= now:
            since = now - paid
            if since < timedelta(hours=3):
                order.status = "PAID"
            elif since < timedelta(hours=10):
                order.status, order.fulfillment = "PROCESSING", "IN_PROGRESS"
            else:
                order.status, order.fulfillment = "READY_TO_SHIP", "IN_PROGRESS"
            return
        order.shipped = shipped
        delivered = shipped + timedelta(days=rng.uniform(1, 4))
        if delivered >= now:
            order.status, order.fulfillment = "SHIPPED", "SHIPPED"
            return
        order.delivered = delivered
        order.status, order.fulfillment = "DELIVERED", "DELIVERED"
        if age > timedelta(days=8) and roll > 0.975:
            order.status, order.payment, order.fulfillment = "REFUNDED", "REFUNDED", "RETURNED"

    def history(self) -> None:
        weights = [1 / (rank + 2) ** 0.8 for rank in range(len(self.active))]
        self.rng.shuffle(weights)
        start = (self.now - timedelta(days=DAYS)).astimezone(TZ).date()
        for day in range(DAYS + 1):
            midnight = datetime.combine(start + timedelta(days=day), time(0), tzinfo=TZ)
            boost = 1.2 if midnight.weekday() >= 5 else 1.0
            mean = self.store.orders_per_day
            for _ in range(max(1, int(self.rng.gauss(mean, mean * 0.25) * boost))):
                placed = midnight + timedelta(hours=min(23.5, max(7.0, self.rng.gauss(14, 4))))
                if placed >= self.now - timedelta(minutes=10):
                    continue
                order = Order(
                    self._number(), placed, self._lines(weights), self._channel(), self._customer()
                )
                self._lifecycle(order)
                self.orders.append(order)

    def _channel(self) -> str:
        return self.rng.choices(("WEB", "MARKETPLACE", "POS"), weights=(45, 50, 5))[0]

    def _scenario_order(
        self, lines: list[Line], status: str, placed_hours_ago: float, **extra: object
    ) -> Order:
        placed = self.now - timedelta(hours=placed_hours_ago)
        order = Order(
            self._number(), placed, lines, self._channel(), self._customer(), status=status
        )
        if status not in ("CREATED", "PAYMENT_PENDING"):
            order.payment = "PAID"
            order.paid = placed + timedelta(minutes=8)
        if status in ("PROCESSING", "READY_TO_SHIP"):
            order.fulfillment = "IN_PROGRESS"
        for key, value in extra.items():
            setattr(order, key, value)
        self.orders.append(order)
        return order

    # -- engineered situations, one per exception type -------------------------------------------
    def scenarios_and_stock(self) -> list[list[str]]:
        rng = self.rng
        picks = rng.sample(self.active, 6)
        oversold, out_of_stock, low_incoming, low, risk, damaged = picks
        others = [p for p in self.active if p not in picks]

        for hours_ago in (6.0, 3.0):
            self._scenario_order([Line(oversold, 2)], "PROCESSING", hours_ago)
        for hours_ago in (1.0, 0.7):
            self._scenario_order([Line(risk, 2)], "PAYMENT_PENDING", hours_ago)
        self.scenarios["INVENTORY_OVERSOLD"].append(oversold.sku)
        self.scenarios["INVENTORY_OVERSELL_RISK"].append(risk.sku)
        self.scenarios["INVENTORY_OUT_OF_STOCK"].append(out_of_stock.sku)
        self.scenarios["INVENTORY_BELOW_REORDER_POINT"] += [low_incoming.sku, low.sku]

        for hours, status in ((60, "PROCESSING"), (125, "READY_TO_SHIP")):
            order = self._scenario_order([Line(rng.choice(others), 1)], status, hours)
            self.scenarios["ORDER_FULFILLMENT_OVERDUE"].append(order.number)
        order = self._scenario_order([Line(rng.choice(others), 1)], "PAID", 16)
        self.scenarios["ORDER_STALLED_AFTER_PAYMENT"].append(order.number)
        order = self._scenario_order(
            [Line(rng.choice(others), 1)], "CANCELLED", 40, cancelled=self.now - timedelta(hours=30)
        )
        self.scenarios["ORDER_REFUND_PENDING"].append(order.number)
        placed = self.now - timedelta(days=6)
        order = self._scenario_order(
            [Line(rng.choice(others), 1)],
            "DELIVERED",
            6 * 24,
            fulfillment="DELIVERED",
            shipped=placed + timedelta(hours=20),
            delivered=placed + timedelta(days=3),
            total_adjustment=Decimal("15000"),
        )
        self.scenarios["DATA_ORDER_TOTAL_MISMATCH"].append(order.number)

        # Unpaid demand must not turn the low-stock products into oversell risks.
        quiet = {out_of_stock.sku, low_incoming.sku, low.sku}
        for order in self.orders:
            if (
                order.status in ("CREATED", "PAYMENT_PENDING")
                and order.number not in self._scenario_numbers()
            ):
                order.lines = [
                    Line(rng.choice(others), line.quantity) if line.product.sku in quiet else line
                    for line in order.lines
                ]

        shipped: Counter[str] = Counter()
        committed: Counter[str] = Counter()
        for order in self.orders:
            for line in order.lines:
                if order.fulfillment in ("SHIPPED", "DELIVERED", "RETURNED"):
                    shipped[line.product.sku] += line.quantity
                elif order.status in ("PAID", "PROCESSING", "READY_TO_SHIP"):
                    committed[line.product.sku] += line.quantity

        def target(product: Product) -> int:
            rop = product.reorder_point
            if product is oversold:
                return -1
            if product is out_of_stock:
                return 0
            if product in (low_incoming, low):
                return rng.randint(1, max(1, rop - 1))
            if product is risk:
                return 2
            return rng.randint(2 * rop + 3, 6 * rop + 10)

        opening_at = self.now - timedelta(days=DAYS + 2)
        rows: list[list[str]] = []
        for product in self.products:
            if product.status != "ACTIVE":
                quantity = rng.randint(5, 20)
            else:
                quantity = shipped[product.sku] + committed[product.sku] + target(product)
                if product is damaged:
                    quantity += 2
            rows.append(
                [
                    f"{self.store.code}-OPEN-{product.sku}",
                    product.sku,
                    "CYCLE_COUNT",
                    str(quantity),
                    _iso(opening_at),
                    "",
                    "Kiểm kê đầu kỳ",
                ]
            )
        rows.append(
            [
                f"{self.store.code}-PO-{low_incoming.sku}",
                low_incoming.sku,
                "INCOMING_EXPECTED",
                str(low_incoming.reorder_quantity),
                _iso(self.now - timedelta(days=2)),
                _iso(self.now + timedelta(days=5)),
                "Đơn đặt hàng nhà cung cấp đã xác nhận",
            ]
        )
        rows.append(
            [
                f"{self.store.code}-DMG-{damaged.sku}",
                damaged.sku,
                "DAMAGE",
                "2",
                _iso(self.now - timedelta(days=1)),
                "",
                "Hàng vỡ khi đóng gói",
            ]
        )
        return rows

    def _scenario_numbers(self) -> set[str]:
        return {
            number
            for key in SCENARIO_KEYS
            if key.startswith("ORDER") or key.startswith("DATA")
            for number in self.scenarios[key]
        }

    # -- CSV -------------------------------------------------------------------------------------
    def csv_files(self, adjustments: list[list[str]]) -> dict[str, str]:
        def render(header: list[str], rows: list[list[str]]) -> str:
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)
            return buffer.getvalue()

        products = render(
            [
                "sku",
                "name",
                "category",
                "status",
                "unit_price",
                "unit_cost",
                "reorder_point",
                "reorder_quantity",
                "supplier_name",
                "supplier_lead_time_days",
            ],
            [
                [
                    p.sku,
                    p.name,
                    p.category,
                    p.status,
                    _money(p.price),
                    _money(p.cost),
                    str(p.reorder_point),
                    str(p.reorder_quantity),
                    p.supplier.name,
                    str(p.supplier.lead_time_days),
                ]
                for p in self.products
            ],
        )
        adjustments_csv = render(
            [
                "reference",
                "sku",
                "adjustment_type",
                "quantity",
                "occurred_at",
                "expected_at",
                "note",
            ],
            adjustments,
        )
        order_rows: list[list[str]] = []
        item_rows: list[list[str]] = []
        for order in sorted(self.orders, key=lambda o: o.placed):
            subtotal = sum(
                (line.product.price * line.quantity for line in order.lines), Decimal("0")
            )
            discount = (
                _round_thousands(subtotal * Decimal("0.1"))
                if subtotal >= VOUCHER_FROM
                else Decimal("0")
            )
            shipping = Decimal("0") if subtotal >= FREE_SHIPPING else SHIPPING_FEE
            total = subtotal - discount + shipping + order.total_adjustment
            shipped = order.shipped is not None
            order_rows.append(
                [
                    order.number,
                    order.channel,
                    order.customer,
                    _iso(order.placed),
                    order.status,
                    order.payment,
                    order.fulfillment,
                    _iso(order.paid),
                    "",
                    _iso(order.shipped),
                    _iso(order.delivered),
                    _iso(order.cancelled),
                    CURRENCY,
                    _money(subtotal),
                    _money(discount),
                    _money(shipping),
                    "0.00",
                    _money(total),
                    "Giao Hàng Sao Việt" if shipped else "",
                    f"SV{self.rng.randint(10**8, 10**9 - 1)}" if shipped else "",
                ]
            )
            for number, line in enumerate(order.lines, start=1):
                item_rows.append(
                    [
                        order.number,
                        str(number),
                        line.product.sku,
                        str(line.quantity),
                        _money(line.product.price),
                        "0.00",
                    ]
                )
        orders_csv = render(
            [
                "order_number",
                "channel",
                "customer_ref",
                "placed_at",
                "status",
                "payment_status",
                "fulfillment_status",
                "paid_at",
                "ship_by",
                "shipped_at",
                "delivered_at",
                "cancelled_at",
                "currency",
                "subtotal",
                "discount_total",
                "shipping_total",
                "tax_total",
                "total",
                "carrier",
                "tracking_number",
            ],
            order_rows,
        )
        items_csv = render(
            ["order_number", "line_number", "sku", "quantity", "unit_price", "line_discount"],
            item_rows,
        )
        return {
            "products": products,
            "inventory_adjustments": adjustments_csv,
            "orders": orders_csv,
            "order_items": items_csv,
        }


def build_store(store: StoreDef, now: datetime) -> StoreCsv:
    builder = _Builder(store, now)
    builder.catalog()
    builder.history()
    adjustments = builder.scenarios_and_stock()
    files = builder.csv_files(adjustments)
    return StoreCsv(
        store=store,
        files=files,
        scenarios={k: v for k, v in builder.scenarios.items() if v},
        product_count=len(builder.products),
        order_count=len(builder.orders),
    )


def write_templates(out: Path, now: datetime) -> list[StoreCsv]:
    built = [build_store(store, now) for store in STORES]
    for item in built:
        folder = out / item.store.slug
        folder.mkdir(parents=True, exist_ok=True)
        for import_type, text in item.files.items():
            (folder / f"{import_type}.csv").write_text(text, encoding="utf-8")
    return built


def _evaluate(
    db: Session,
    *,
    store_id: uuid.UUID,
    import_id: uuid.UUID,
    as_of: datetime,
    triggered_by: uuid.UUID | None,
) -> uuid.UUID:
    run = engine.run_evaluation(
        db,
        store_id,
        trigger=EvaluationTrigger.IMPORT,
        as_of=as_of,
        triggered_by=triggered_by,
        import_id=import_id,
    )
    return run.id


@dataclass
class LoadedStore:
    slug: str
    store_name: str
    owner_email: str
    password: str
    orders: int
    exceptions: dict[str, int]


def load_store(
    db: Session,
    store: StoreDef,
    now: datetime,
    *,
    replace: bool,
    owner_password: str | None,
    clock: Callable[[], datetime] = utcnow,
) -> LoadedStore | None:
    owner_email = f"owner@{store.slug}.example"
    existing = db.scalar(select(Organization).where(Organization.slug == store.slug))
    if existing is not None:
        if not replace:
            return None
        purge_organization(db, existing.id)
        db.execute(delete(User).where(User.email == owner_email))
        db.commit()
    data = build_store(store, now)
    result = provision(
        db,
        ProvisionRequest(
            organization_name=store.org_name,
            slug=store.slug,
            store_name=store.store_name,
            store_code=store.code,
            currency=CURRENCY,
            timezone="Asia/Ho_Chi_Minh",
            owner_email=owner_email,
            owner_name=store.owner_name,
            exposure_cap=EXPOSURE_CAP,
        ),
    )
    owner = db.get(User, result.owner_id)
    assert owner is not None
    password = result.temporary_password
    if owner_password:
        owner.password_hash = security.hash_password(owner_password)
        db.commit()
        password = owner_password
    ctx = store_context(db, owner, result.store_id)
    for import_type in IMPORT_ORDER:
        content = data.files[import_type].encode("utf-8")
        upload = Upload(
            filename=f"{store.slug}-{import_type}.csv",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content=content,
        )
        detail = imports.create_import(
            db, ctx, import_type=ImportType(import_type), upload=upload, now=clock()
        )
        if detail.status is not ImportStatus.VALIDATED or detail.summary.rows_with_errors:
            raise RuntimeError(
                f"{store.slug} {import_type}: {detail.status} {detail.summary.issue_counts_by_code}"
            )
        applied = imports.apply_import(
            db,
            ctx,
            detail.id,
            mode=ImportMode.STRICT,
            confirm_skipped_rows=None,
            idempotency_key=None,
            now=clock(),
            on_applied=_evaluate,
        )
        if applied.status is not ImportStatus.COMPLETED:
            raise RuntimeError(f"{store.slug} {import_type}: apply ended {applied.status}")
    counts = dict(
        db.execute(
            select(OperationalException.exception_type, func.count())
            .where(OperationalException.store_id == result.store_id)
            .group_by(OperationalException.exception_type)
        ).all()
    )
    return LoadedStore(
        slug=store.slug,
        store_name=store.store_name,
        owner_email=owner_email,
        password=password,
        orders=data.order_count,
        exceptions={str(k.value): int(v) for k, v in counts.items()},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fictional Vietnamese sample shops")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="write the CSV templates")
    gen.add_argument("--out", type=Path, required=True)
    load = commands.add_parser("load", help="provision the shops and import their CSV files")
    load.add_argument("--only", action="append", help="slug of a shop (repeatable); default all")
    load.add_argument("--replace", action="store_true", help="remove and recreate shops that exist")
    args = parser.parse_args(argv)

    now = utcnow()
    if args.command == "generate":
        built = write_templates(args.out, now)
        for item in built:
            print(
                f"{item.store.slug:24} {item.product_count:3} products {item.order_count:4} orders"
            )
        return 0

    owner_password = os.environ.get("SAMPLE_OWNER_PASSWORD") or None
    if owner_password and get_settings().app_env == "production":
        print("error: SAMPLE_OWNER_PASSWORD is refused when APP_ENV=production", file=sys.stderr)
        return 2
    selected = [s for s in STORES if not args.only or s.slug in args.only]
    with get_session_factory()() as db:
        for store in selected:
            loaded = load_store(db, store, now, replace=args.replace, owner_password=owner_password)
            if loaded is None:
                print(f"{store.slug:24} exists, skipped (use --replace)")
                continue
            total = sum(loaded.exceptions.values())
            print(
                f"{loaded.slug:24} {loaded.orders:4} orders {total:3} exceptions  "
                f"{loaded.owner_email}  password: {loaded.password}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
