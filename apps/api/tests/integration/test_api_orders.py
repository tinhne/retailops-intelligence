"""Orders read API: filters, overdue (BR-202), reconciliation (BR-205) and history (§1.2)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product
from app.domains.exceptions.models import ExceptionStatus, ExceptionType, ResolutionCode, Severity
from app.domains.identity.permissions import Permission, Role
from app.domains.orders.models import Order, OrderStatus, PaymentStatus, SalesChannel
from tests.factories import Tenant, create_tenant, create_user, login
from tests.factories_commerce import (
    Line,
    all_pages,
    count_stock,
    create_exception,
    create_order,
    create_product,
    freeze_now,
    strip_permission,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 28, 16, tzinfo=UTC)
DAY = timedelta(days=1)


@dataclass
class OrderBook:
    tenant: Tenant
    mug: Product
    pan: Product
    orders: dict[str, Order]


def _seed(db: Session) -> OrderBook:
    tenant = create_tenant(db)
    mug = create_product(db, tenant, "MUG-01", name="Stoneware Mug")
    pan = create_product(db, tenant, "PAN-02", name="Cast Iron Pan")
    count_stock(db, tenant, mug, 100, NOW - 30 * DAY)
    count_stock(db, tenant, pan, 100, NOW - 30 * DAY)
    db.commit()
    made = {
        # ship_by = paid_at + 48 h = NOW − 1 d: overdue by 24 h.
        "KH-1001": create_order(
            db,
            tenant,
            "KH-1001",
            status=OrderStatus.PAID,
            lines=[Line(mug, 2)],
            placed_at=NOW - 3 * DAY,
            customer_ref="CUST-1",
        ),
        "KH-1002": create_order(
            db,
            tenant,
            "KH-1002",
            status=OrderStatus.PROCESSING,
            lines=[Line(pan, 1, "25.00"), Line(mug, 1)],
            placed_at=NOW - DAY,
            ship_by=NOW + DAY,
            channel=SalesChannel.MARKETPLACE,
            customer_ref="CUST-2",
        ),
        # Exactly at the deadline is not overdue (BR-202 is strict).
        "KH-1003": create_order(
            db,
            tenant,
            "KH-1003",
            status=OrderStatus.READY_TO_SHIP,
            lines=[Line(mug, 1)],
            placed_at=NOW - 4 * DAY,
            ship_by=NOW,
        ),
        "KH-1004": create_order(
            db,
            tenant,
            "KH-1004",
            status=OrderStatus.SHIPPED,
            lines=[Line(mug, 1)],
            placed_at=NOW - 5 * DAY,
            shipped_at=NOW - 4 * DAY,
            channel=SalesChannel.POS,
        ),
        "KH-1005": create_order(
            db,
            tenant,
            "KH-1005",
            status=OrderStatus.CANCELLED,
            lines=[Line(mug, 1)],
            placed_at=NOW - 2 * DAY,
            customer_ref="VIP_100%",
        ),
        "KH-1006": create_order(
            db,
            tenant,
            "KH-1006",
            status=OrderStatus.PAYMENT_PENDING,
            lines=[Line(pan, 1)],
            placed_at=NOW - timedelta(hours=6),
        ),
        # Recorded total 50.00 vs expected 48.30 (BR-205); overdue by 8 days.
        "KH-1007": create_order(
            db,
            tenant,
            "KH-1007",
            status=OrderStatus.PAID,
            lines=[Line(mug, 2, "10.00", "1.00"), Line(pan, 1, "25.00")],
            placed_at=NOW - 10 * DAY,
            discount_total="4.00",
            shipping_total="5.00",
            tax_total="3.30",
            total="50.00",
        ),
    }
    return OrderBook(tenant, mug, pan, made)


@pytest.fixture
def book(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> OrderBook:
    data = _seed(db)
    create_user(db, data.tenant, Role.STAFF)
    login(client, "staff@acme.example")
    freeze_now(monkeypatch, NOW)
    return data


def _list(client: TestClient, book: OrderBook, **params: Any) -> dict[str, Any]:
    response = client.get(f"/api/v1/stores/{book.tenant.store.id}/orders", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _numbers(body: dict[str, Any]) -> list[str]:
    return [item["order_number"] for item in body["items"]]


def test_order_list_defaults_to_newest_first_with_line_counts(
    client: TestClient, book: OrderBook
) -> None:
    body = _list(client, book)

    assert body["total"] == 7
    assert _numbers(body) == [
        "KH-1006",
        "KH-1002",
        "KH-1005",
        "KH-1001",
        "KH-1003",
        "KH-1004",
        "KH-1007",
    ]
    rows = {item["order_number"]: item for item in body["items"]}
    assert rows["KH-1002"]["line_count"] == 2
    assert rows["KH-1002"]["ship_by_source"] == "IMPORTED"
    assert rows["KH-1001"]["ship_by_source"] == "STORE_SLA"
    assert rows["KH-1001"]["ship_by"] == "2026-10-27T16:00:00Z"  # BR-201: paid_at + 48 h
    assert rows["KH-1007"]["total"] == "50.00"
    assert [n for n, r in rows.items() if r["is_overdue"]] == ["KH-1001", "KH-1007"]


def test_overdue_filter_applies_br202_strictly(client: TestClient, book: OrderBook) -> None:
    assert sorted(_numbers(_list(client, book, overdue="true"))) == ["KH-1001", "KH-1007"]
    not_overdue = _list(client, book, overdue="false")
    assert not_overdue["total"] == 5
    assert "KH-1003" in _numbers(not_overdue)  # ship_by == now is not overdue


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": ["PAID", "PROCESSING"]}, ["KH-1002", "KH-1001", "KH-1007"]),
        ({"payment_status": "PENDING"}, ["KH-1006", "KH-1005"]),
        ({"fulfillment_status": "SHIPPED"}, ["KH-1004"]),
        ({"channel": "MARKETPLACE"}, ["KH-1002"]),
        (
            {"placed_from": "2026-10-24T16:00:00Z", "placed_to": "2026-10-27T16:00:00Z"},
            ["KH-1005", "KH-1001", "KH-1003"],  # from inclusive, to exclusive
        ),
        ({"q": "1003"}, ["KH-1003"]),
        ({"q": "cust-2"}, ["KH-1002"]),
        ({"q": "%"}, ["KH-1005"]),  # LIKE wildcards are escaped
        ({"q": "_"}, ["KH-1005"]),
        ({"overdue": "true", "channel": "WEB", "q": "1007"}, ["KH-1007"]),
        ({"overdue": "true", "status": ["PROCESSING"]}, []),
        ({"status": ["PAID"], "payment_status": "PAID", "channel": "WEB"}, ["KH-1001", "KH-1007"]),
    ],
)
def test_order_filters_combine(
    client: TestClient, book: OrderBook, params: dict[str, Any], expected: list[str]
) -> None:
    body = _list(client, book, **params)
    assert _numbers(body) == expected
    assert body["total"] == len(expected)


def test_product_filter_finds_orders_with_a_line_for_the_product(
    client: TestClient, book: OrderBook
) -> None:
    body = _list(client, book, product_id=str(book.pan.id))
    assert _numbers(body) == ["KH-1006", "KH-1002", "KH-1007"]


def test_order_sorts_and_unknown_sort_is_rejected(client: TestClient, book: OrderBook) -> None:
    assert _numbers(_list(client, book, sort="-total"))[:2] == ["KH-1007", "KH-1002"]
    by_ship_by = _numbers(_list(client, book, sort="ship_by"))
    # Orders without ship_by sort last.
    assert by_ship_by[:3] == ["KH-1007", "KH-1004", "KH-1001"]
    assert by_ship_by[-2:] == ["KH-1005", "KH-1006"]
    assert _numbers(_list(client, book, sort="placed_at"))[0] == "KH-1007"

    for bad in ("customer_ref", "-status", "total;drop"):
        response = client.get(f"/api/v1/stores/{book.tenant.store.id}/orders", params={"sort": bad})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_naive_datetime_filters_are_rejected(client: TestClient, book: OrderBook) -> None:
    response = client.get(
        f"/api/v1/stores/{book.tenant.store.id}/orders",
        params={"placed_from": "2026-10-24T16:00:00"},
    )
    assert response.status_code == 422


def test_pagination_covers_every_order_once(client: TestClient, book: OrderBook) -> None:
    def fetch(page: int) -> dict[str, Any]:
        return _list(client, book, page=page, page_size=3, sort="order_number")

    first = fetch(1)
    seen = [item["order_number"] for item in all_pages(fetch)]

    assert (first["total"], first["page_size"], len(first["items"])) == (7, 3, 3)
    assert seen == sorted(book.orders)
    assert fetch(3)["items"][0]["order_number"] == "KH-1007"


def test_order_detail_reconciles_total_per_br205_and_links_exceptions(
    client: TestClient, db: Session, book: OrderBook
) -> None:
    order = book.orders["KH-1007"]
    tenant = book.tenant
    create_exception(
        db,
        tenant,
        ExceptionType.DATA_ORDER_TOTAL_MISMATCH,
        entity=order,
        severity=Severity.MEDIUM,
        first_detected_at=NOW - 9 * DAY,
        status=ExceptionStatus.RESOLVED,
        resolved_at=NOW - 8 * DAY,
        resolution_code=ResolutionCode.DATA_CORRECTED,
    )
    overdue = create_exception(
        db,
        tenant,
        ExceptionType.ORDER_FULFILLMENT_OVERDUE,
        entity=order,
        severity=Severity.CRITICAL,
        priority_score=81,
        first_detected_at=NOW - 7 * DAY,
    )
    create_exception(
        db,
        tenant,
        ExceptionType.INVENTORY_OVERSOLD,
        entity=book.pan,
        affected=[order],
        first_detected_at=NOW - 2 * DAY,
    )

    response = client.get(f"/api/v1/stores/{tenant.store.id}/orders/{order.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["payment_status"], body["fulfillment_status"]) == (
        "PAID",
        "PAID",
        "UNFULFILLED",
    )
    assert body["ship_by"] == "2026-10-20T16:00:00Z"
    assert body["ship_by_source"] == "STORE_SLA"
    assert body["is_overdue"] is True
    assert body["hours_overdue"] == "192.0"
    assert body["amounts"] == {
        "currency": "USD",
        "subtotal": "44.00",
        "discount_total": "4.00",
        "shipping_total": "5.00",
        "tax_total": "3.30",
        "total": "50.00",
        "lines_total": "44.00",  # 2 × 10.00 − 1.00 + 25.00
        "expected_total": "48.30",  # 44.00 − 4.00 + 5.00 + 3.30
        "difference": "1.70",
        "has_total_mismatch": True,
    }
    lines = body["lines"]
    assert [(ln["line_number"], ln["product_sku"], ln["product_name"]) for ln in lines] == [
        (1, "MUG-01", "Stoneware Mug"),
        (2, "PAN-02", "Cast Iron Pan"),
    ]
    assert lines[0]["line_total"] == "19.00"
    assert lines[0]["reservation"] == {"status": "ACTIVE", "quantity": 2}  # BR-120
    exceptions = body["exceptions"]
    assert [(e["exception_type"], e["is_active"], e["link_role"]) for e in exceptions] == [
        ("INVENTORY_OVERSOLD", True, "AFFECTED"),
        ("ORDER_FULFILLMENT_OVERDUE", True, "PRIMARY"),
        ("DATA_ORDER_TOTAL_MISMATCH", False, "PRIMARY"),
    ]
    assert exceptions[1] == {
        "id": str(overdue.id),
        "reference": overdue.reference,
        "exception_type": "ORDER_FULFILLMENT_OVERDUE",
        "severity": "CRITICAL",
        "status": "OPEN",
        "priority_band": "P1",
        "link_role": "PRIMARY",
        "is_active": True,
    }


def test_order_detail_timeline_records_skipped_statuses_section_1_2(
    client: TestClient, db: Session, book: OrderBook
) -> None:
    tenant = book.tenant
    placed = NOW - 3 * DAY
    for status in (OrderStatus.PAYMENT_PENDING, OrderStatus.PROCESSING):
        order = create_order(
            db, tenant, "KH-2001", status=status, lines=[Line(book.mug, 3)], placed_at=placed
        )
    order = create_order(
        db,
        tenant,
        "KH-2001",
        status=OrderStatus.SHIPPED,
        lines=[Line(book.mug, 3)],
        placed_at=placed,
        shipped_at=NOW - DAY,
    )

    body = client.get(f"/api/v1/stores/{tenant.store.id}/orders/{order.id}").json()

    timeline = [(e["from_status"], e["to_status"], e["skipped_statuses"]) for e in body["events"]]
    assert timeline == [
        (None, "PAYMENT_PENDING", []),
        ("PAYMENT_PENDING", "PROCESSING", ["PAID"]),
        ("PROCESSING", "SHIPPED", ["READY_TO_SHIP"]),
    ]
    assert all(e["source"] == "IMPORT" for e in body["events"])
    assert body["lines"][0]["reservation"] == {"status": "CONSUMED", "quantity": 3}  # BR-122
    assert body["is_overdue"] is False
    assert body["hours_overdue"] is None
    assert body["amounts"]["has_total_mismatch"] is False


def test_order_without_lines_has_nothing_to_reconcile(
    client: TestClient, db: Session, book: OrderBook
) -> None:
    order = create_order(
        db,
        book.tenant,
        "KH-3001",
        status=OrderStatus.PAYMENT_PENDING,
        lines=[],
        placed_at=NOW - DAY,
        total="12.00",
        payment_status=PaymentStatus.PENDING,
    )

    amounts = client.get(f"/api/v1/stores/{book.tenant.store.id}/orders/{order.id}").json()[
        "amounts"
    ]

    assert amounts["expected_total"] is None
    assert amounts["difference"] is None
    assert amounts["has_total_mismatch"] is False  # BR-205 needs at least one line


def test_order_of_another_store_is_not_found(
    client: TestClient, db: Session, book: OrderBook
) -> None:
    other = create_tenant(db, "globex")
    product = create_product(db, other, "G-1")
    foreign = create_order(
        db,
        other,
        "KH-1001",
        status=OrderStatus.PAYMENT_PENDING,
        lines=[Line(product, 1)],
        placed_at=NOW - DAY,
    )
    own = book.orders["KH-1001"]

    via_own_store = client.get(f"/api/v1/stores/{book.tenant.store.id}/orders/{foreign.id}")
    via_foreign_store = client.get(f"/api/v1/stores/{other.store.id}/orders/{own.id}")
    foreign_list = client.get(f"/api/v1/stores/{other.store.id}/orders")

    assert via_own_store.status_code == 404
    assert via_own_store.json()["error"]["code"] == "NOT_FOUND"
    assert via_foreign_store.status_code == 404
    assert foreign_list.status_code == 404
    # The same order number in another store never leaks into this store's list.
    assert _list(client, book, q="KH-1001")["total"] == 1


@pytest.mark.parametrize("route", ["", "/{order_id}"])
def test_order_routes_require_orders_read(
    client: TestClient, book: OrderBook, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    strip_permission(monkeypatch, Permission.ORDERS_READ)
    path = route.format(order_id=book.orders["KH-1001"].id)

    response = client.get(f"/api/v1/stores/{book.tenant.store.id}/orders{path}")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "orders.read"}]
