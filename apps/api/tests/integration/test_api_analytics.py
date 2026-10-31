"""Analytics API (T-057): every number below is hand-computed from the seeded rows.

``NOW`` is 2026-11-03 17:00 UTC = 12:00 EST. US daylight saving time ended on 2026-11-01 at
02:00 local (06:00 UTC), so the store-local days in the 7-day window are:

    Oct 28 .. Oct 31   UTC−4 (EDT): local midnight = 04:00 UTC
    Nov 1              25 hours: 04:00 UTC .. 05:00 UTC next day
    Nov 2 .. Nov 3     UTC−5 (EST): local midnight = 05:00 UTC

Several rows sit just before or after a local midnight to pin the bucketing (BR-501).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus
from app.domains.exceptions.models import (
    ExceptionStatus,
    ExceptionType,
    ResolutionCode,
    Severity,
)
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission, Role
from app.domains.imports.models import ImportStatus, ImportType
from app.domains.orders.models import Order, OrderStatus, PaymentStatus
from tests.factories import Tenant, create_tenant, create_user, login
from tests.factories_commerce import (
    Line,
    count_stock,
    create_evaluation_run,
    create_exception,
    create_import,
    create_order,
    create_product,
    freeze_now,
    strip_permission,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 3, 17, tzinfo=UTC)


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


@dataclass
class Store:
    tenant: Tenant
    manager: User
    products: dict[str, Product]
    orders: dict[str, Order]


def _seed_products(db: Session, tenant: Tenant) -> dict[str, Product]:
    p = {
        "P": create_product(db, tenant, "P-HEALTHY"),
        "Q": create_product(db, tenant, "Q-OVERSOLD"),
        "R": create_product(db, tenant, "R-OUT"),
        "S": create_product(db, tenant, "S-BELOW", reorder_point=5),
        "U": create_product(db, tenant, "U-APPROACH", reorder_point=5),
        "V": create_product(db, tenant, "V-ARCHIVED", status=ProductStatus.ARCHIVED),
        "W": create_product(db, tenant, "W-DRAFT", status=ProductStatus.DRAFT),
        "X": create_product(db, tenant, "X-NO-BALANCE"),
    }
    for key, qty in (("P", 1000), ("Q", 2), ("R", 0), ("S", 3), ("U", 6), ("V", 0)):
        count_stock(db, tenant, p[key], qty, utc(9, 1, 12))
    db.commit()
    return p


def _seed_orders(db: Session, tenant: Tenant, p: dict[str, Product]) -> dict[str, Order]:
    main = p["P"]
    spec: list[tuple[str, dict[str, Any]]] = [
        # Today (Nov 3 local): placed 09:00 and 01:00 EST.
        ("T-01", dict(status=OrderStatus.PAID, lines=[Line(main, 3)], placed_at=utc(11, 3, 14))),
        ("T-02", dict(status=OrderStatus.PAYMENT_PENDING, lines=[Line(main, 2)],
                      placed_at=utc(11, 3, 6))),
        # Nov 3 04:30 UTC = Nov 2 23:30 EST: belongs to Nov 2, not today.
        ("T-03", dict(status=OrderStatus.PAID, lines=[Line(main, 1)], placed_at=utc(11, 3, 4, 30))),
        # Nov 1 03:30 UTC = Oct 31 23:30 EDT. Shipped Nov 1 10:00 EST, before ship_by (on time).
        ("T-04", dict(status=OrderStatus.DELIVERED, lines=[Line(main, 5)],
                      placed_at=utc(11, 1, 3, 30), shipped_at=utc(11, 1, 15),
                      delivered_at=utc(11, 2, 15))),
        # Paid then cancelled: in GMV (gross), not a sale for units (BR-150).
        ("T-05", dict(status=OrderStatus.CANCELLED, payment_status=PaymentStatus.PAID,
                      lines=[Line(main, 4)], placed_at=utc(10, 30, 16))),
        # Cancelled before payment: neither GMV nor units.
        ("T-06", dict(status=OrderStatus.CANCELLED, lines=[Line(main, 1, "15.00")],
                      placed_at=utc(10, 29, 16))),
        # Refunded before shipping: in GMV (gross), not in units (BR-150).
        ("T-07", dict(status=OrderStatus.REFUNDED, lines=[Line(main, 2, "12.50")],
                      placed_at=utc(10, 29, 18))),
        # Outside the 7-day window, inside 30 days: shipped late.
        ("T-08", dict(status=OrderStatus.SHIPPED, lines=[Line(main, 1)], placed_at=utc(10, 20, 16),
                      ship_by=utc(10, 22, 16), shipped_at=utc(10, 23, 16))),
        # Shipped Oct 4 23:00 EDT: one hour before the 30-day window starts.
        ("T-09", dict(status=OrderStatus.SHIPPED, lines=[Line(main, 1)], placed_at=utc(10, 1, 16),
                      ship_by=utc(10, 6, 16), shipped_at=utc(10, 5, 3))),
        # Overdue since Oct 27 16:00 (paid_at + 48 h); its Q line makes Q oversold.
        ("T-11", dict(status=OrderStatus.PROCESSING, lines=[Line(p["Q"], 3), Line(main, 4)],
                      placed_at=utc(10, 25, 16))),
        # ship_by == now: not overdue (BR-202 is strict).
        ("T-12", dict(status=OrderStatus.READY_TO_SHIP, lines=[Line(main, 1)],
                      placed_at=utc(11, 2, 16), ship_by=NOW)),
        # Shipped exactly at ship_by: on time (shipped_at ≤ ship_by).
        ("T-13", dict(status=OrderStatus.SHIPPED, lines=[Line(main, 1)], placed_at=utc(10, 26, 16),
                      ship_by=utc(10, 27, 16), shipped_at=utc(10, 27, 16))),
        # Both on Nov 1 local: 00:30 EDT and 23:30 EST of the 25-hour day.
        ("T-14", dict(status=OrderStatus.PAYMENT_PENDING, lines=[Line(main, 1)],
                      placed_at=utc(11, 1, 4, 30))),
        ("T-15", dict(status=OrderStatus.CREATED, lines=[Line(main, 1)],
                      placed_at=utc(11, 2, 4, 30))),
    ]  # fmt: skip
    return {number: create_order(db, tenant, number, **kwargs) for number, kwargs in spec}


def _seed_exceptions(db: Session, store: Store) -> None:
    t, p, o = store.tenant, store.products, store.orders
    kind = ExceptionType
    rows: list[tuple[ExceptionType, Product | Order, dict[str, Any]]] = [
        (kind.INVENTORY_OVERSOLD, p["Q"], dict(
            severity=Severity.CRITICAL, priority_score=81, first_detected_at=utc(11, 3, 15),
            due_at=utc(11, 3, 19), assignee=store.manager, title="Q-OVERSOLD oversold by 1")),
        (kind.ORDER_FULFILLMENT_OVERDUE, o["T-11"], dict(
            severity=Severity.HIGH, priority_score=62, status=ExceptionStatus.IN_PROGRESS,
            first_detected_at=utc(11, 1, 4, 30), due_at=utc(11, 2, 4, 30))),
        (kind.INVENTORY_BELOW_REORDER_POINT, p["S"], dict(
            severity=Severity.MEDIUM, priority_score=26, status=ExceptionStatus.REOPENED,
            first_detected_at=utc(10, 29, 3), due_at=utc(11, 1, 3),
            reopened_at=[utc(11, 2, 15)])),
        (kind.DATA_ORDER_TOTAL_MISMATCH, o["T-08"], dict(
            severity=Severity.LOW, priority_score=30, status=ExceptionStatus.ACKNOWLEDGED,
            first_detected_at=utc(10, 20, 16), due_at=utc(11, 10, 16))),
        # Resolved: E5/E6 automatic (12 h, 30 h), E11 manual (24 h), E7 manual (84 h).
        (kind.INVENTORY_OUT_OF_STOCK, p["R"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(10, 30, 16),
            resolved_at=utc(10, 31, 4), resolution_code=ResolutionCode.CONDITION_CLEARED)),
        (kind.INVENTORY_OUT_OF_STOCK, p["R"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(10, 29, 16),
            resolved_at=utc(10, 30, 22), resolution_code=ResolutionCode.CONDITION_CLEARED)),
        (kind.ORDER_REFUND_PENDING, o["T-05"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(10, 29, 16),
            resolved_at=utc(11, 2, 4), resolution_code=ResolutionCode.REFUND_ISSUED)),
        (kind.INVENTORY_OUT_OF_STOCK, p["X"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(11, 2, 16),
            resolved_at=utc(11, 3, 15), resolution_code=ResolutionCode.SUPERSEDED)),
        (kind.ORDER_STALLED_AFTER_PAYMENT, o["T-03"], dict(
            status=ExceptionStatus.DISMISSED, first_detected_at=utc(10, 31, 16))),
        (kind.INVENTORY_OUT_OF_STOCK, p["R"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(10, 1, 16),
            resolved_at=utc(10, 2, 16), resolution_code=ResolutionCode.CONDITION_CLEARED)),
        (kind.INVENTORY_OUT_OF_STOCK, p["R"], dict(
            status=ExceptionStatus.RESOLVED, first_detected_at=utc(10, 31, 12),
            resolved_at=utc(11, 1, 12), resolution_code=ResolutionCode.STOCK_REPLENISHED)),
    ]  # fmt: skip
    for exception_type, entity, kwargs in rows:
        create_exception(db, t, exception_type, entity=entity, **kwargs)


def _seed(db: Session) -> Store:
    tenant = create_tenant(db)
    manager = create_user(db, tenant, Role.MANAGER)
    products = _seed_products(db, tenant)
    orders = _seed_orders(db, tenant, products)
    store = Store(tenant, manager, products, orders)
    _seed_exceptions(db, store)
    create_import(db, tenant, ImportType.ORDERS, status=ImportStatus.COMPLETED,
                  applied_at=utc(11, 3, 11))  # fmt: skip
    create_evaluation_run(db, tenant, started_at=utc(11, 3, 11, 1))
    return store


@pytest.fixture
def store(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> Store:
    data = _seed(db)
    create_user(db, data.tenant, Role.VIEWER)
    login(client, "viewer@acme.example")
    freeze_now(monkeypatch, NOW)
    return data


def _get(client: TestClient, store: Store, path: str, **params: Any) -> dict[str, Any]:
    response = client.get(f"/api/v1/stores/{store.tenant.store.id}/analytics{path}", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_dashboard_numbers_reconcile_with_seeded_rows(client: TestClient, store: Store) -> None:
    body = _get(client, store, "/dashboard")

    assert (body["as_of"], body["timezone"], body["currency"]) == (
        "2026-11-03T17:00:00Z",
        "America/New_York",
        "USD",
    )
    assert body["active_exceptions"] == {
        "total": 4,
        "by_severity": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 1},
        "by_band": {"P1": 1, "P2": 1, "P3": 1, "P4": 1},
        "by_category": {"INVENTORY": 2, "FULFILLMENT": 1, "PAYMENT": 0, "DATA_QUALITY": 1},
        "unassigned": 3,
        "past_due": 2,  # due Nov 2 04:30 and Nov 1 03:00
        "reopened": 1,
    }
    attention = body["attention"]
    assert [(a["exception_type"], a["priority_score"]) for a in attention] == [
        ("INVENTORY_OVERSOLD", 81),
        ("ORDER_FULFILLMENT_OVERDUE", 62),
        ("DATA_ORDER_TOTAL_MISMATCH", 30),
        ("INVENTORY_BELOW_REORDER_POINT", 26),
    ]
    top = attention[0]
    assert (top["title"], top["severity"], top["priority_band"]) == (
        "Q-OVERSOLD oversold by 1",
        "CRITICAL",
        "P1",
    )
    assert (top["assignee_id"], top["assignee_name"]) == (str(store.manager.id), "Manager User")
    assert (top["due_at"], top["is_past_due"]) == ("2026-11-03T19:00:00Z", False)
    assert attention[1]["assignee_name"] is None
    assert attention[1]["is_past_due"] is True

    # BR-202: only T-11 (ship_by Oct 27); T-12 is due exactly now.
    assert body["orders"] == {"overdue_count": 1, "overdue_value": "70.00", "awaiting_shipment": 4}
    # From balances, not exceptions: Q −1, R and X 0, S 3 ≤ 5, U 6 ≤ ceil(6.25).
    assert body["inventory"] == {
        "active_products": 6,
        "oversold": 1,
        "out_of_stock": 2,
        "below_reorder_point": 1,
        "approaching_reorder_point": 1,
        "healthy": 1,
    }
    today = body["sales_today"]
    assert today["window"] == {
        "start": "2026-11-03T05:00:00Z",  # midnight EST
        "end": "2026-11-03T17:00:00Z",
        "days": 1,
        "timezone": "America/New_York",
    }
    # T-01 and T-02; T-03 (Nov 3 04:30 UTC) is Nov 2 locally.
    assert (today["orders_placed"], today["paid_orders"], today["gmv"]) == (2, 1, "30.00")
    week = body["sales_last_7_days"]
    assert week["window"]["start"] == "2026-10-28T04:00:00Z"  # midnight EDT
    # 10 orders placed; paid: T-01 30 + T-03 10 + T-04 50 + T-05 40 + T-07 25 + T-12 10.
    assert (week["orders_placed"], week["paid_orders"], week["gmv"]) == (10, 6, "165.00")
    on_time = body["on_time_shipment_30_days"]
    assert on_time["window"]["start"] == "2026-10-05T04:00:00Z"
    # T-04 and T-13 on time, T-08 late; T-09 shipped one hour before the window.
    assert {k: v for k, v in on_time.items() if k != "window"} == {
        "shipped_with_deadline": 3,
        "on_time": 2,
        "late": 1,
        "shipped_without_deadline": 0,
        "on_time_rate_pct": "66.7",
    }
    freshness = body["data_freshness"]
    assert freshness["last_evaluation_run"]["started_at"] == "2026-11-03T11:01:00Z"
    orders_import = next(i for i in freshness["imports"] if i["import_type"] == "orders")
    assert orders_import["applied_at"] == "2026-11-03T11:00:00Z"


def test_dashboard_is_deterministic_for_a_fixed_as_of(client: TestClient, store: Store) -> None:
    assert _get(client, store, "/dashboard") == _get(client, store, "/dashboard")


def test_trends_bucket_by_store_local_day_across_dst_br501(
    client: TestClient, store: Store
) -> None:
    body = _get(client, store, "/trends", days=7)

    assert body["window"] == {
        "start": "2026-10-28T04:00:00Z",
        "end": "2026-11-03T17:00:00Z",
        "days": 7,
        "timezone": "America/New_York",
    }
    assert body["partial_last_day"] is True
    columns = (
        "orders_placed", "units", "gmv", "exceptions_detected", "exceptions_resolved",
        "shipped_on_time", "shipped_late",
    )  # fmt: skip
    series = {day["date"]: tuple(day[c] for c in columns) for day in body["days"]}
    assert series == {
        "2026-10-28": (0, 0, "0.00", 1, 0, 0, 0),  # E3 at Oct 29 03:00 UTC = Oct 28 23:00 EDT
        "2026-10-29": (
            2,
            0,
            "25.00",
            2,
            0,
            0,
            0,
        ),  # T-06 unpaid; T-07 refunded unshipped
        "2026-10-30": (1, 0, "40.00", 1, 1, 0, 0),  # T-05 paid then cancelled: no units
        "2026-10-31": (1, 5, "50.00", 2, 1, 0, 0),  # T-04 at 23:30 EDT; E5 at 00:00 EDT
        "2026-11-01": (2, 0, "0.00", 1, 2, 1, 0),  # 25-hour day: T-14 00:30 EDT, T-15 23:30 EST
        "2026-11-02": (2, 2, "20.00", 1, 0, 0, 0),  # T-03 at 23:30 EST, T-12
        "2026-11-03": (2, 3, "30.00", 1, 0, 0, 0),  # T-01; T-02 pending has no units
    }
    assert body["totals"] == {
        "orders_placed": 10,
        "units": 10,
        "gmv": "165.00",
        "exceptions_detected": 9,
        "exceptions_resolved": 4,  # SUPERSEDED E8 and the DISMISSED one are not resolutions
        "shipped_on_time": 1,
        "shipped_late": 0,
    }


def test_trend_totals_cross_check_dashboard_and_breakdown(client: TestClient, store: Store) -> None:
    dashboard = _get(client, store, "/dashboard")
    week = _get(client, store, "/trends", days=7)
    month = _get(client, store, "/trends", days=30)
    breakdown = _get(client, store, "/exceptions-breakdown", days=7)

    assert week["totals"]["orders_placed"] == dashboard["sales_last_7_days"]["orders_placed"]
    assert week["totals"]["gmv"] == dashboard["sales_last_7_days"]["gmv"]
    assert week["days"][-1]["gmv"] == dashboard["sales_today"]["gmv"]
    assert month["window"] == dashboard["on_time_shipment_30_days"]["window"]
    assert month["totals"]["shipped_on_time"] == dashboard["on_time_shipment_30_days"]["on_time"]
    assert month["totals"]["shipped_late"] == dashboard["on_time_shipment_30_days"]["late"]
    items = breakdown["items"]
    assert sum(i["detected_in_window"] for i in items) == week["totals"]["exceptions_detected"]
    assert sum(i["resolved_in_window"] for i in items) == week["totals"]["exceptions_resolved"]
    assert sum(i["active"] for i in items) == dashboard["active_exceptions"]["total"]


def test_exception_breakdown_counts_and_median_resolution_hours_m10(
    client: TestClient, store: Store
) -> None:
    body = _get(client, store, "/exceptions-breakdown", days=7)

    assert body["window"]["start"] == "2026-10-28T04:00:00Z"
    rows = {item["exception_type"]: item for item in body["items"]}
    assert list(rows) == [t.value for t in ExceptionType]  # every type, zeros included
    assert rows["INVENTORY_OUT_OF_STOCK"] == {
        "exception_type": "INVENTORY_OUT_OF_STOCK",
        "category": "INVENTORY",
        "active": 0,
        "detected_in_window": 4,  # the Oct 1 occurrence is outside the window
        "resolved_in_window": 3,
        "resolved_manually": 1,
        "auto_resolved": 2,
        "superseded_in_window": 1,
        "median_hours_to_resolve_manual": "24.0",
        "median_hours_to_resolve_auto": "21.0",  # median of 12 h and 30 h
        "reopened_in_window": 0,
    }
    refund = rows["ORDER_REFUND_PENDING"]
    assert (refund["category"], refund["resolved_manually"]) == ("PAYMENT", 1)
    assert refund["median_hours_to_resolve_manual"] == "84.0"
    assert refund["median_hours_to_resolve_auto"] is None
    below = rows["INVENTORY_BELOW_REORDER_POINT"]
    assert (below["active"], below["detected_in_window"], below["reopened_in_window"]) == (1, 1, 1)
    stalled = rows["ORDER_STALLED_AFTER_PAYMENT"]
    assert (stalled["active"], stalled["detected_in_window"], stalled["resolved_in_window"]) == (
        0,
        1,
        0,
    )
    mismatch = rows["DATA_ORDER_TOTAL_MISMATCH"]
    assert (mismatch["category"], mismatch["active"], mismatch["detected_in_window"]) == (
        "DATA_QUALITY",
        1,
        0,
    )
    assert rows["DATA_NEGATIVE_ON_HAND"]["active"] == 0

    month = _get(client, store, "/exceptions-breakdown")  # default 30 days
    assert month["window"]["days"] == 30
    month_rows = {item["exception_type"]: item for item in month["items"]}
    assert month_rows["DATA_ORDER_TOTAL_MISMATCH"]["detected_in_window"] == 1  # Oct 20


def test_attention_list_is_capped_at_eight_by_priority(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = create_tenant(db)
    product = create_product(db, tenant, "SKU-1")
    create_user(db, tenant, Role.STAFF)
    for i, score in enumerate([40, 90, 55, 90, 10, 75, 60, 20, 35, 85]):
        create_exception(db, tenant, ExceptionType.INVENTORY_OUT_OF_STOCK, entity=product,
                         priority_score=score, first_detected_at=NOW - timedelta(hours=10),
                         due_at=NOW + timedelta(hours=10 - i), title=f"item {i}")  # fmt: skip
    create_exception(db, tenant, ExceptionType.INVENTORY_OVERSOLD, entity=product,
                     priority_score=99, first_detected_at=NOW - timedelta(days=2),
                     status=ExceptionStatus.RESOLVED, resolved_at=NOW - timedelta(days=1),
                     resolution_code=ResolutionCode.CONDITION_CLEARED)  # fmt: skip
    login(client, "staff@acme.example")
    freeze_now(monkeypatch, NOW)

    response = client.get(f"/api/v1/stores/{tenant.store.id}/analytics/dashboard")

    attention = response.json()["attention"]
    # Ties on score: earliest due first (item 3 is due before item 1).
    assert [a["title"] for a in attention] == [
        "item 3", "item 1", "item 9", "item 5", "item 6", "item 2", "item 0", "item 8"
    ]  # fmt: skip


def test_analytics_on_an_empty_store_returns_zeros(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.ANALYST)
    login(client, "analyst@acme.example")
    freeze_now(monkeypatch, NOW)
    base = f"/api/v1/stores/{tenant.store.id}/analytics"

    dashboard = client.get(f"{base}/dashboard").json()
    trends = client.get(f"{base}/trends").json()

    assert dashboard["active_exceptions"]["total"] == 0
    assert dashboard["attention"] == []
    assert dashboard["on_time_shipment_30_days"]["on_time_rate_pct"] is None
    assert dashboard["sales_last_7_days"]["gmv"] == "0.00"
    assert dashboard["data_freshness"]["last_evaluation_run"] is None
    assert len(trends["days"]) == 30
    assert trends["days"][0]["date"] == "2026-10-05"
    assert trends["totals"]["orders_placed"] == 0


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/trends", {"days": 6}),
        ("/trends", {"days": 91}),
        ("/exceptions-breakdown", {"days": 0}),
        ("/exceptions-breakdown", {"days": 91}),
    ],
)
def test_window_length_is_validated(
    client: TestClient, store: Store, path: str, params: dict[str, Any]
) -> None:
    response = client.get(f"/api/v1/stores/{store.tenant.store.id}/analytics{path}", params=params)
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "permission"),
    [
        ("/dashboard", Permission.DASHBOARD_READ),
        ("/trends", Permission.ANALYTICS_READ),
        ("/exceptions-breakdown", Permission.ANALYTICS_READ),
    ],
)
def test_analytics_routes_require_their_permission(
    client: TestClient,
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    permission: Permission,
) -> None:
    strip_permission(monkeypatch, permission)

    response = client.get(f"/api/v1/stores/{store.tenant.store.id}/analytics{path}")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": permission.value}]


@pytest.mark.parametrize("path", ["/dashboard", "/trends", "/exceptions-breakdown"])
def test_analytics_of_another_tenant_are_not_found(
    client: TestClient, db: Session, store: Store, path: str
) -> None:
    other = create_tenant(db, "globex")

    response = client.get(f"/api/v1/stores/{other.store.id}/analytics{path}")

    assert response.status_code == 404


def test_other_stores_rows_never_count(client: TestClient, db: Session, store: Store) -> None:
    """BR-003: a second store in another organization with its own activity changes nothing."""
    before = _get(client, store, "/dashboard")
    other = create_tenant(db, "globex")
    product = create_product(db, other, "P-HEALTHY")
    count_stock(db, other, product, 0, utc(9, 1, 12))
    db.commit()
    order = create_order(db, other, "T-01", status=OrderStatus.PAID, lines=[Line(product, 9)],
                         placed_at=utc(11, 3, 14))  # fmt: skip
    create_exception(db, other, ExceptionType.INVENTORY_OVERSOLD, entity=order,
                     priority_score=99, first_detected_at=utc(11, 3, 15))  # fmt: skip

    after = _get(client, store, "/dashboard")

    assert after == before
