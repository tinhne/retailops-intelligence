"""Catalog read API: products with stock and health, suppliers, categories (T-050 read side).

Stock is produced by the real ledger and reservation code, so the expected numbers below follow
BR-101 (available), §2.5 (health), BR-130 (shipment after the latest count) and BR-150..152.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.exceptions.models import ExceptionStatus, ExceptionType, ResolutionCode
from app.domains.identity.permissions import Permission, Role
from app.domains.inventory.models import MovementType
from app.domains.orders.models import OrderStatus
from tests.factories import Tenant, create_tenant, create_user, login
from tests.factories_commerce import (
    Line,
    count_stock,
    create_exception,
    create_order,
    create_product,
    create_supplier,
    freeze_now,
    move_stock,
    strip_permission,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 28, 16, tzinfo=UTC)
DAY = timedelta(days=1)


@dataclass
class Catalog:
    tenant: Tenant
    supplier: Supplier
    mug: Product
    pan: Product
    board: Product
    towel: Product
    archived: Product
    draft: Product
    no_balance: Product


def _seed(db: Session) -> Catalog:
    tenant = create_tenant(db)
    northfield = create_supplier(db, tenant, "Northfield Cookware", lead_time_days=14)
    create_supplier(db, tenant, "Alder Linen", lead_time_days=None)
    mug = create_product(
        db,
        tenant,
        "MUG-01",
        name="Stoneware Mug",
        category="Kitchen",
        reorder_point=5,
        supplier=northfield,
        unit_cost="4.10",
    )
    pan = create_product(
        db,
        tenant,
        "PAN-02",
        name="Cast Iron Pan",
        category="Cookware",
        reorder_point=4,
        supplier=northfield,
    )
    board = create_product(db, tenant, "BOARD-03", name="Bamboo_Board 100%", category="Kitchen")
    towel = create_product(db, tenant, "TOWEL-04", name="Linen Towel", reorder_point=10)
    archived = create_product(
        db, tenant, "OLD-05", category="Kitchen", status=ProductStatus.ARCHIVED
    )
    draft = create_product(db, tenant, "DRAFT-06", status=ProductStatus.DRAFT)
    no_balance = create_product(db, tenant, "NOBAL-07", name="Never Counted")

    count_stock(db, tenant, mug, 10, NOW - 30 * DAY)
    move_stock(
        db, tenant, mug, MovementType.INCOMING_EXPECTED, 12, NOW - DAY, expected_at=NOW + 5 * DAY
    )
    count_stock(db, tenant, pan, 2, NOW - 5 * DAY)
    count_stock(db, tenant, board, 0, NOW - 5 * DAY)
    count_stock(db, tenant, towel, 50, NOW - 5 * DAY)
    count_stock(db, tenant, archived, 0, NOW - 5 * DAY)
    db.commit()

    # Shipped before the latest count: the count already reflects it (BR-130), outside the
    # velocity window anyway.
    create_order(
        db,
        tenant,
        "O-0999",
        status=OrderStatus.DELIVERED,
        lines=[Line(mug, 10)],
        placed_at=NOW - 40 * DAY,
        shipped_at=NOW - 39 * DAY,
        delivered_at=NOW - 37 * DAY,
    )
    # Shipped after the count: one SHIPMENT movement of −4; counts as 4 units sold.
    create_order(
        db,
        tenant,
        "O-1001",
        status=OrderStatus.SHIPPED,
        lines=[Line(mug, 4)],
        placed_at=NOW - 10 * DAY,
        shipped_at=NOW - 9 * DAY,
    )
    create_order(
        db, tenant, "O-1002", status=OrderStatus.PAID, lines=[Line(mug, 3)], placed_at=NOW - 2 * DAY
    )
    # Not sales under BR-150 and not reserved.
    create_order(
        db,
        tenant,
        "O-1003",
        status=OrderStatus.CANCELLED,
        lines=[Line(mug, 5)],
        placed_at=NOW - 3 * DAY,
    )
    create_order(
        db,
        tenant,
        "O-1004",
        status=OrderStatus.PAYMENT_PENDING,
        lines=[Line(mug, 2)],
        placed_at=NOW - DAY,
    )
    create_order(
        db, tenant, "O-1005", status=OrderStatus.PAID, lines=[Line(pan, 5)], placed_at=NOW - DAY
    )
    return Catalog(tenant, northfield, mug, pan, board, towel, archived, draft, no_balance)


def _products(client: TestClient, store_id: Any, **params: Any) -> dict[str, Any]:
    response = client.get(f"/api/v1/stores/{store_id}/products", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _skus(body: dict[str, Any]) -> list[str]:
    return [item["sku"] for item in body["items"]]


@pytest.fixture
def catalog(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> Catalog:
    data = _seed(db)
    create_user(db, data.tenant, Role.VIEWER)
    login(client, "viewer@acme.example")
    freeze_now(monkeypatch, NOW)
    return data


def test_product_list_reports_stock_and_health_per_br101_and_section_2_5(
    client: TestClient, catalog: Catalog
) -> None:
    body = _products(client, catalog.tenant.store.id)

    assert body["total"] == 7
    assert _skus(body) == [
        "BOARD-03",
        "DRAFT-06",
        "MUG-01",
        "NOBAL-07",
        "OLD-05",
        "PAN-02",
        "TOWEL-04",
    ]
    rows = {item["sku"]: item for item in body["items"]}
    mug = rows["MUG-01"]
    # 10 counted − 4 shipped after the count; 3 reserved by the PAID order (BR-101).
    assert (mug["on_hand"], mug["reserved"], mug["available"]) == (6, 3, 3)
    assert mug["health"] == "BELOW_REORDER_POINT"
    assert mug["supplier"] == {"id": str(catalog.supplier.id), "name": "Northfield Cookware"}
    assert (mug["unit_price"], mug["unit_cost"]) == ("10.00", "4.10")
    assert (rows["PAN-02"]["available"], rows["PAN-02"]["health"]) == (-3, "OVERSOLD")  # BR-102
    assert rows["BOARD-03"]["health"] == "OUT_OF_STOCK"
    assert rows["TOWEL-04"]["health"] == "HEALTHY"
    assert rows["NOBAL-07"]["health"] == "OUT_OF_STOCK"  # no balance row = 0 available
    assert rows["OLD-05"]["health"] is None  # §2.5 applies to ACTIVE products only
    assert rows["DRAFT-06"]["health"] is None


def test_product_search_escapes_like_wildcards(client: TestClient, catalog: Catalog) -> None:
    store_id = catalog.tenant.store.id
    assert _skus(_products(client, store_id, q="_")) == ["BOARD-03"]
    assert _skus(_products(client, store_id, q="100%")) == ["BOARD-03"]
    assert _skus(_products(client, store_id, q="mug")) == ["MUG-01"]  # case-insensitive name
    assert _skus(_products(client, store_id, q="pan-0")) == ["PAN-02"]  # SKU substring


def test_product_filters_combine(client: TestClient, catalog: Catalog) -> None:
    store_id = catalog.tenant.store.id
    assert _skus(_products(client, store_id, status="ARCHIVED")) == ["OLD-05"]
    assert _skus(_products(client, store_id, category="Kitchen")) == [
        "BOARD-03",
        "MUG-01",
        "OLD-05",
    ]
    assert _skus(_products(client, store_id, supplier_id=str(catalog.supplier.id))) == [
        "MUG-01",
        "PAN-02",
    ]
    assert _skus(_products(client, store_id, health="OUT_OF_STOCK", category="Kitchen")) == [
        "BOARD-03"
    ]
    both = _products(client, store_id, health=["OVERSOLD", "BELOW_REORDER_POINT"])
    assert _skus(both) == ["MUG-01", "PAN-02"]
    assert _products(client, store_id, q="mug", status="DRAFT")["total"] == 0


def test_health_filter_keeps_pagination_totals_exact(client: TestClient, catalog: Catalog) -> None:
    store_id = catalog.tenant.store.id
    first = _products(client, store_id, health="OUT_OF_STOCK", page_size=1)
    second = _products(client, store_id, health="OUT_OF_STOCK", page_size=1, page=2)
    third = _products(client, store_id, health="OUT_OF_STOCK", page_size=1, page=3)

    assert (first["total"], second["total"], third["total"]) == (2, 2, 2)
    assert _skus(first) + _skus(second) == ["BOARD-03", "NOBAL-07"]
    assert third["items"] == []


def test_product_sorts_follow_the_allowlist(client: TestClient, catalog: Catalog) -> None:
    store_id = catalog.tenant.store.id
    by_available = _skus(_products(client, store_id, sort="available"))
    assert by_available[0] == "PAN-02"  # −3
    assert by_available[-2:] == ["MUG-01", "TOWEL-04"]  # 3, 50
    assert _skus(_products(client, store_id, sort="-available"))[0] == "TOWEL-04"
    assert _skus(_products(client, store_id, sort="-name"))[0] == "MUG-01"  # "Stoneware Mug"

    rejected = client.get(f"/api/v1/stores/{store_id}/products", params={"sort": "unit_price"})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_FAILED"


def test_product_detail_labels_velocity_as_estimate_br150_br152(
    client: TestClient, db: Session, catalog: Catalog
) -> None:
    tenant = catalog.tenant
    create_exception(
        db,
        tenant,
        ExceptionType.INVENTORY_BELOW_REORDER_POINT,
        entity=catalog.mug,
        first_detected_at=NOW - DAY,
    )
    order = create_order(
        db,
        tenant,
        "O-2001",
        status=OrderStatus.PAID,
        lines=[Line(catalog.towel, 1)],
        placed_at=NOW - 5 * DAY,
    )
    # The product is AFFECTED by an order exception: still counts.
    create_exception(
        db,
        tenant,
        ExceptionType.ORDER_FULFILLMENT_OVERDUE,
        entity=order,
        affected=[catalog.mug],
        first_detected_at=NOW - DAY,
    )
    create_exception(
        db,
        tenant,
        ExceptionType.INVENTORY_OUT_OF_STOCK,
        entity=catalog.mug,
        first_detected_at=NOW - 20 * DAY,
        status=ExceptionStatus.RESOLVED,
        resolved_at=NOW - 19 * DAY,
        resolution_code=ResolutionCode.CONDITION_CLEARED,
    )

    response = client.get(f"/api/v1/stores/{tenant.store.id}/products/{catalog.mug.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sku"] == "MUG-01"
    assert body["supplier"] == {
        "id": str(catalog.supplier.id),
        "name": "Northfield Cookware",
        "lead_time_days": 14,
    }
    assert body["stock"] == {
        "on_hand": 6,
        "reserved": 3,
        "available": 3,
        "incoming": 12,
        "incoming_eta": "2026-11-02T16:00:00Z",
        "last_cycle_count_at": "2026-09-28T16:00:00Z",
    }
    assert body["health"] == "BELOW_REORDER_POINT"
    assert body["approaching_threshold"] == 7  # ceil(5 × 1.25)
    # 4 (shipped) + 3 (paid) units in 28 days; CANCELLED, PAYMENT_PENDING and the 40-day-old
    # order are excluded (BR-150).
    assert body["avg_daily_units"] == {
        "value": "0.25",
        "is_estimate": True,
        "basis": "BR-150",
        "window_days": 28,
        "note": "7 units sold in the last 28 days ÷ 28",
    }
    assert body["days_of_cover"]["value"] == "12.0"  # 3 ÷ 0.25 (BR-151)
    assert body["days_of_cover"]["is_estimate"] is True
    assert body["active_exception_count"] == 2


def test_product_without_sales_has_no_days_of_cover_br151(
    client: TestClient, catalog: Catalog
) -> None:
    body = client.get(
        f"/api/v1/stores/{catalog.tenant.store.id}/products/{catalog.towel.id}"
    ).json()

    assert body["avg_daily_units"]["value"] == "0.00"
    assert body["days_of_cover"]["value"] is None
    assert body["days_of_cover"]["note"] == "Not enough sales history"
    assert body["approaching_threshold"] == 13  # ceil(10 × 1.25)
    assert body["supplier"] is None
    assert body["active_exception_count"] == 0


def test_suppliers_and_categories_are_store_scoped(
    client: TestClient, db: Session, catalog: Catalog
) -> None:
    other = create_tenant(db, "globex")
    create_supplier(db, other, "Globex Supply")
    create_product(db, other, "G-1", category="Garden")
    db.commit()
    store_id = catalog.tenant.store.id

    suppliers = client.get(f"/api/v1/stores/{store_id}/suppliers").json()
    by_lead_time = client.get(
        f"/api/v1/stores/{store_id}/suppliers", params={"sort": "-lead_time_days"}
    ).json()
    categories = client.get(f"/api/v1/stores/{store_id}/categories").json()

    assert suppliers["total"] == 2
    assert [(s["name"], s["product_count"]) for s in suppliers["items"]] == [
        ("Alder Linen", 0),
        ("Northfield Cookware", 2),
    ]
    assert [s["name"] for s in by_lead_time["items"]] == ["Northfield Cookware", "Alder Linen"]
    assert categories == {"items": ["Cookware", "Kitchen"]}
    assert (
        client.get(
            f"/api/v1/stores/{store_id}/suppliers", params={"sort": "contact_ref"}
        ).status_code
        == 422
    )


def test_product_detail_of_another_store_is_not_found(
    client: TestClient, db: Session, catalog: Catalog
) -> None:
    other = create_tenant(db, "globex")
    foreign = create_product(db, other, "MUG-01")
    db.commit()

    foreign_product = client.get(f"/api/v1/stores/{catalog.tenant.store.id}/products/{foreign.id}")
    foreign_store = client.get(f"/api/v1/stores/{other.store.id}/products/{catalog.mug.id}")

    assert foreign_product.status_code == 404
    assert foreign_product.json()["error"]["code"] == "NOT_FOUND"
    assert foreign_store.status_code == 404


CATALOG_ROUTES = ["/products", "/products/{product_id}", "/suppliers", "/categories"]


@pytest.mark.parametrize("route", CATALOG_ROUTES)
def test_catalog_routes_require_catalog_read(
    client: TestClient, catalog: Catalog, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    strip_permission(monkeypatch, Permission.CATALOG_READ)
    path = route.format(product_id=catalog.mug.id)

    response = client.get(f"/api/v1/stores/{catalog.tenant.store.id}{path}")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "catalog.read"}]


@pytest.mark.parametrize("route", CATALOG_ROUTES)
def test_catalog_routes_of_another_tenant_are_not_found(
    client: TestClient, db: Session, catalog: Catalog, route: str
) -> None:
    other = create_tenant(db, "globex")
    foreign = create_product(db, other, "G-1")
    db.commit()

    response = client.get(f"/api/v1/stores/{other.store.id}{route.format(product_id=foreign.id)}")

    assert response.status_code == 404
