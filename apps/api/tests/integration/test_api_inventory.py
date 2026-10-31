"""Inventory read API: positions, movements, reconciliation (BUSINESS_RULES.md §2, T-051).

Also checks that the SQL twins of ``classify_health`` and ``days_of_cover`` (used to filter, sort
and paginate in the database) agree with the Python functions on a grid of inputs.
"""

import itertools
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Integer, column, literal, select, values
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus
from app.domains.identity.permissions import Permission, Role
from app.domains.inventory import queries as inventory_queries
from app.domains.inventory import service as inventory
from app.domains.inventory.calculations import avg_daily_units, days_of_cover
from app.domains.inventory.models import MovementType
from app.domains.orders.models import Order, OrderStatus
from tests.factories import Tenant, create_tenant, create_user, login
from tests.factories_commerce import (
    Line,
    count_stock,
    create_order,
    create_product,
    freeze_now,
    move_stock,
    strip_permission,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 28, 16, tzinfo=UTC)
DAY = timedelta(days=1)


@dataclass
class Stock:
    tenant: Tenant
    products: dict[str, Product]


def _seed(db: Session) -> Stock:
    tenant = create_tenant(db)
    p = {
        "A": create_product(db, tenant, "A-MUG", name="Mug", category="Kitchen", reorder_point=5),
        "B": create_product(db, tenant, "B-PAN", name="Pan", category="Kitchen", reorder_point=10),
        "C": create_product(db, tenant, "C-KNIFE", name="Knife", category="Kitchen"),
        "D": create_product(db, tenant, "D-BOWL", name="Bowl", category="Kitchen", reorder_point=2),
        "E": create_product(db, tenant, "E-OLD", name="Retired", status=ProductStatus.ARCHIVED),
        "F": create_product(db, tenant, "F-TOWEL", name="Towel", category="Linen", reorder_point=1),
    }
    for key, qty in (("A", 20), ("B", 12), ("C", 3), ("D", 40), ("E", 5), ("F", 0)):
        count_stock(db, tenant, p[key], qty, NOW - 30 * DAY)
    move_stock(
        db,
        tenant,
        p["B"],
        MovementType.INCOMING_EXPECTED,
        30,
        NOW - 2 * DAY,
        expected_at=NOW + 3 * DAY,
    )
    db.commit()
    create_order(
        db,
        tenant,
        "S-1",
        status=OrderStatus.SHIPPED,
        lines=[Line(p["A"], 14)],
        placed_at=NOW - 14 * DAY,
        shipped_at=NOW - 13 * DAY,
    )
    create_order(
        db, tenant, "S-2", status=OrderStatus.PAID, lines=[Line(p["A"], 2)], placed_at=NOW - DAY
    )
    create_order(
        db, tenant, "S-3", status=OrderStatus.PAID, lines=[Line(p["C"], 5)], placed_at=NOW - DAY
    )
    create_order(
        db,
        tenant,
        "S-4",
        status=OrderStatus.DELIVERED,
        lines=[Line(p["D"], 28)],
        placed_at=NOW - 20 * DAY,
        shipped_at=NOW - 19 * DAY,
        delivered_at=NOW - 17 * DAY,
    )
    return Stock(tenant, p)


@pytest.fixture
def stock(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> Stock:
    data = _seed(db)
    create_user(db, data.tenant, Role.ANALYST)
    login(client, "analyst@acme.example")
    freeze_now(monkeypatch, NOW)
    return data


def _positions(client: TestClient, stock: Stock, **params: Any) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/stores/{stock.tenant.store.id}/inventory/positions", params=params
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _skus(body: dict[str, Any]) -> list[str]:
    return [item["sku"] for item in body["items"]]


def test_positions_report_stock_health_and_estimates(client: TestClient, stock: Stock) -> None:
    body = _positions(client, stock, sort="sku")

    assert body["total"] == 5  # ARCHIVED excluded by default
    rows = {item["sku"]: item for item in body["items"]}
    a = rows["A-MUG"]
    # 20 counted − 14 shipped after the count = 6 on hand; 2 reserved (BR-101).
    assert (a["on_hand"], a["reserved"], a["available"]) == (6, 2, 4)
    assert a["health"] == "BELOW_REORDER_POINT"
    assert a["avg_daily_units"] == "0.57"  # 16 units ÷ 28 days (BR-150)
    assert a["days_of_cover"] == "7.0"  # 4 ÷ 0.57 (BR-151)
    assert a["last_cycle_count_at"] == "2026-09-28T16:00:00Z"
    b = rows["B-PAN"]
    assert (b["available"], b["health"]) == (12, "APPROACHING_REORDER_POINT")  # ≤ ceil(12.5)
    assert (b["incoming"], b["incoming_eta"]) == (30, "2026-10-31T16:00:00Z")
    assert (b["avg_daily_units"], b["days_of_cover"]) == ("0.00", None)
    c = rows["C-KNIFE"]
    assert (c["available"], c["health"], c["days_of_cover"]) == (-2, "OVERSOLD", "0.0")
    d = rows["D-BOWL"]
    assert (d["available"], d["health"], d["avg_daily_units"], d["days_of_cover"]) == (
        12,
        "HEALTHY",
        "1.00",
        "12.0",
    )
    assert rows["F-TOWEL"]["health"] == "OUT_OF_STOCK"


def test_positions_sorts_including_days_of_cover_with_nulls_last(
    client: TestClient, stock: Stock
) -> None:
    assert _skus(_positions(client, stock)) == ["C-KNIFE", "F-TOWEL", "A-MUG", "B-PAN", "D-BOWL"]
    assert _skus(_positions(client, stock, sort="days_of_cover")) == [
        "C-KNIFE",
        "A-MUG",
        "D-BOWL",
        "B-PAN",
        "F-TOWEL",
    ]
    assert _skus(_positions(client, stock, sort="-days_of_cover")) == [
        "D-BOWL",
        "A-MUG",
        "C-KNIFE",
        "B-PAN",
        "F-TOWEL",
    ]
    assert _skus(_positions(client, stock, sort="-sku"))[0] == "F-TOWEL"
    rejected = client.get(
        f"/api/v1/stores/{stock.tenant.store.id}/inventory/positions",
        params={"sort": "on_hand"},
    )
    assert rejected.status_code == 422


def test_positions_filters_and_pagination(client: TestClient, stock: Stock) -> None:
    both = _positions(client, stock, health=["OVERSOLD", "OUT_OF_STOCK"], sort="sku")
    assert _skus(both) == ["C-KNIFE", "F-TOWEL"]
    assert _skus(_positions(client, stock, category="Linen")) == ["F-TOWEL"]
    assert _skus(_positions(client, stock, q="mug")) == ["A-MUG"]
    assert _positions(client, stock, health="HEALTHY", category="Linen")["total"] == 0

    with_inactive = _positions(client, stock, include_inactive="true", sort="sku")
    assert with_inactive["total"] == 6
    assert with_inactive["items"][4]["sku"] == "E-OLD"
    assert with_inactive["items"][4]["health"] is None  # §2.5 applies to ACTIVE only

    page_two = _positions(client, stock, sort="sku", page=2, page_size=2)
    assert (page_two["total"], _skus(page_two)) == (5, ["C-KNIFE", "D-BOWL"])


def test_movements_list_ledger_rows_with_filters(
    client: TestClient, db: Session, stock: Stock
) -> None:
    store_id = stock.tenant.store.id
    url = f"/api/v1/stores/{store_id}/inventory/movements"
    product_a = str(stock.products["A"].id)

    newest = client.get(url, params={"product_id": product_a}).json()
    shipments = client.get(url, params={"movement_type": "SHIPMENT", "sort": "occurred_at"}).json()
    from_orders = client.get(url, params={"source": "ORDER"}).json()
    window = client.get(
        url,
        params={
            "movement_type": ["CYCLE_COUNT", "INCOMING_EXPECTED"],
            "from": "2026-09-28T16:00:00Z",
            "to": "2026-10-26T16:00:00Z",
        },
    ).json()

    # The shipment was recorded after the count, so it is listed first (sort -recorded_at).
    assert [
        (m["movement_type"], m["on_hand_delta"], m["on_hand_after"]) for m in newest["items"]
    ] == [
        ("SHIPMENT", -14, 6),
        ("CYCLE_COUNT", 20, 20),
    ]
    assert newest["items"][0]["sku"] == "A-MUG"
    assert newest["items"][0]["source"] == "ORDER"
    # BR-130: both shipments happened after the products' latest count.
    assert [(m["sku"], m["on_hand_delta"]) for m in shipments["items"]] == [
        ("D-BOWL", -28),
        ("A-MUG", -14),
    ]
    assert from_orders["total"] == 2
    # A shipment's order_item:{id} reference resolves to its order; other rows have no order.
    order_ids = dict(db.execute(select(Order.order_number, Order.id)).all())
    assert [m["order_id"] for m in shipments["items"]] == [
        str(order_ids["S-4"]),
        str(order_ids["S-1"]),
    ]
    assert {m["order_id"] for m in newest["items"][1:]} == {None}
    assert {m["import_filename"] for m in newest["items"]} == {None}
    # Six counts at the window start (inclusive); the incoming movement is 2 days ago (excluded).
    assert window["total"] == 6
    assert {m["movement_type"] for m in window["items"]} == {"CYCLE_COUNT"}
    assert client.get(url, params={"sort": "quantity"}).status_code == 422


def test_reconciliation_reports_drift_without_fixing_it_br104(
    client: TestClient, db: Session, stock: Stock
) -> None:
    url = f"/api/v1/stores/{stock.tenant.store.id}/inventory/reconciliation"
    clean = client.get(url).json()

    balance = inventory.get_balance(db, stock.tenant.store.id, stock.products["A"].id)
    balance.reserved = 99  # simulate a defect in the cached projection
    db.commit()
    drifted = client.get(url).json()

    assert clean == {
        "checked_at": "2026-10-28T16:00:00Z",
        "is_consistent": True,
        "drift_count": 0,
        "items": [],
    }
    assert drifted["is_consistent"] is False
    assert drifted["items"] == [
        {
            "product_id": str(stock.products["A"].id),
            "sku": "A-MUG",
            "field": "reserved",
            "stored": 99,
            "computed": 2,
        }
    ]
    db.refresh(balance)
    assert balance.reserved == 99  # reported, never silently fixed


def test_velocity_window_and_status_filter_br150(db: Session) -> None:
    tenant = create_tenant(db)
    mug = create_product(db, tenant, "MUG")
    count_stock(db, tenant, mug, 500, NOW - 60 * DAY)
    db.commit()
    window_start = NOW - 28 * DAY
    cases = [
        ("V-1", OrderStatus.PAID, window_start, 100),  # boundary: excluded (window is (start, now])
        ("V-2", OrderStatus.PAID, window_start + timedelta(minutes=1), 1),
        (
            "V-3",
            OrderStatus.REFUNDED,
            NOW - DAY,
            2,
        ),  # refunded unshipped: no sale (BR-150)
        ("V-4", OrderStatus.CANCELLED, NOW - DAY, 40),
        ("V-5", OrderStatus.PAYMENT_FAILED, NOW - DAY, 40),
        ("V-6", OrderStatus.CREATED, NOW - DAY, 40),
        ("V-7", OrderStatus.PAYMENT_PENDING, NOW - DAY, 40),
        ("V-8", OrderStatus.PROCESSING, NOW, 4),  # boundary: included
        ("V-9", OrderStatus.PAID, NOW + timedelta(minutes=1), 100),  # after as_of
    ]
    for number, status, placed, qty in cases:
        create_order(db, tenant, number, status=status, lines=[Line(mug, qty)], placed_at=placed)

    sold = inventory_queries.units_sold(db, tenant.store.id, as_of=NOW, window_days=28)
    speed = inventory_queries.velocity(db, tenant.store.id, as_of=NOW, window_days=28)

    assert sold == {mug.id: 5}
    assert speed == {mug.id: Decimal("0.18")}  # 5 / 28 rounded half-up


@pytest.mark.parametrize(
    "factor", [Decimal("1.00"), Decimal("1.25"), Decimal("1.50"), Decimal("3.00")]
)
def test_health_sql_matches_classify_health_section_2_5(db: Session, factor: Decimal) -> None:
    """BR-141: the SQL used for filtering classifies exactly like ``classify_health``."""
    grid = list(itertools.product(range(-3, 35), [0, 1, 2, 4, 5, 7, 10]))
    table = values(column("avail", Integer), column("rop", Integer), name="grid").data(grid)
    for status in ProductStatus:
        expression = inventory_queries.health_sql(
            table.c.avail, table.c.rop, literal(status.value), factor
        )
        rows = db.execute(select(table.c.avail, table.c.rop, expression)).all()
        assert len(rows) == len(grid)
        for avail, rop, sql_health in rows:
            expected = inventory_queries.product_health(status, avail, rop, factor)
            assert sql_health == (expected.value if expected else None), (status, avail, rop)


def test_days_of_cover_sql_matches_python_br151(db: Session) -> None:
    grid = list(itertools.product(range(-2, 40, 3), [0, 1, 3, 7, 16, 28, 100], [7, 28, 90]))
    table = values(
        column("avail", Integer), column("units", Integer), column("window", Integer), name="grid"
    ).data(grid)
    for window in (7, 28, 90):
        rows = db.execute(
            select(
                table.c.avail,
                table.c.units,
                inventory_queries.days_of_cover_sql(table.c.avail, table.c.units, window),
            ).where(table.c.window == window)
        ).all()
        for avail, units, sql_cover in rows:
            expected = days_of_cover(avail, avg_daily_units(units, window))
            assert sql_cover == expected, (avail, units, window)


INVENTORY_ROUTES = ["/positions", "/movements", "/reconciliation"]


@pytest.mark.parametrize("route", INVENTORY_ROUTES)
def test_inventory_routes_require_inventory_read(
    client: TestClient, stock: Stock, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    strip_permission(monkeypatch, Permission.INVENTORY_READ)

    response = client.get(f"/api/v1/stores/{stock.tenant.store.id}/inventory{route}")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "inventory.read"}]


@pytest.mark.parametrize("route", INVENTORY_ROUTES)
def test_inventory_routes_of_another_tenant_are_not_found(
    client: TestClient, db: Session, stock: Stock, route: str
) -> None:
    other = create_tenant(db, "globex")

    response = client.get(f"/api/v1/stores/{other.store.id}/inventory{route}")

    assert response.status_code == 404


def test_movements_filtered_by_another_stores_product_are_empty(
    client: TestClient, db: Session, stock: Stock
) -> None:
    other = create_tenant(db, "globex")
    foreign = create_product(db, other, "G-1")
    count_stock(db, other, foreign, 9, NOW - DAY)
    db.commit()

    body = client.get(
        f"/api/v1/stores/{stock.tenant.store.id}/inventory/movements",
        params={"product_id": str(foreign.id)},
    ).json()

    assert (body["total"], body["items"]) == (0, [])
