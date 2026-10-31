"""orders.csv and order_items.csv validation and apply (STATE_MACHINES §1, BR-201, BR-605..609)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.inventory.models import InventoryMovement, MovementType
from app.domains.orders.models import (
    ChangeSource,
    FulfillmentStatus,
    Order,
    OrderEvent,
    OrderStatus,
    SalesChannel,
    ShipBySource,
)
from tests.factories_imports import (
    ADJUSTMENT_HEADER,
    ITEM_HEADER,
    ORDER_HEADER,
    PRODUCT_HEADER,
    ImportApi,
    adjustment_row,
    csv_bytes,
    item_row,
    manager_api,
    order_row,
    product_row,
)

pytestmark = pytest.mark.integration

SHIPPED = {
    "status": "SHIPPED",
    "fulfillment": "SHIPPED",
    "shipped_at": "2026-10-29T10:00:00-04:00",
}
DELIVERED = {
    "status": "DELIVERED",
    "fulfillment": "DELIVERED",
    "shipped_at": "2026-10-29T10:00:00-04:00",
    "delivered_at": "2026-10-30T15:00:00-04:00",
}


def _orders(api: ImportApi, *rows: str) -> dict[str, object]:
    return api.run("orders", csv_bytes(ORDER_HEADER, *rows))


def _order(db: Session, number: str) -> Order:
    db.expire_all()
    return db.scalars(select(Order).where(Order.order_number == number)).one()


def test_orders_create_with_derived_fulfillment_and_sla_ship_by(
    client: TestClient, db: Session
) -> None:
    """STATE_MACHINES §1.3 derived fulfillment; BR-201 ship_by = paid_at + 48 h."""
    _, api = manager_api(client, db)

    body = _orders(api, order_row("KHK-1"))

    assert body["summary"]["applied"]["creates"] == 1
    order = _order(db, "KHK-1")
    assert order.fulfillment_status is FulfillmentStatus.UNFULFILLED
    assert order.channel is SalesChannel.WEB
    assert order.paid_at == datetime(2026, 10, 28, 18, 6, tzinfo=UTC)
    assert order.ship_by == order.paid_at + timedelta(hours=48)
    assert order.ship_by_source is ShipBySource.STORE_SLA
    assert order.last_import_id is not None
    assert str(order.last_import_id) == body["id"]


def test_reachable_transition_records_skipped_states(client: TestClient, db: Session) -> None:
    """STATE_MACHINES §1.2 import sync: PAID → SHIPPED via PROCESSING and READY_TO_SHIP."""
    _, api = manager_api(client, db)
    _orders(api, order_row("KHK-1"))

    body = api.validated("orders", csv_bytes(ORDER_HEADER, order_row("KHK-1", **SHIPPED)))
    assert body["summary"]["preview"][0]["changed_fields"] == [
        "status",
        "fulfillment_status",
        "shipped_at",
    ]
    assert api.apply(body["id"]).status_code == 200

    order = _order(db, "KHK-1")
    assert order.status is OrderStatus.SHIPPED
    event = db.scalars(select(OrderEvent).where(OrderEvent.to_status == OrderStatus.SHIPPED)).one()
    assert event.from_status is OrderStatus.PAID
    assert event.skipped_statuses == ["PROCESSING", "READY_TO_SHIP"]
    assert event.source is ChangeSource.IMPORT
    assert str(event.import_id) == body["id"]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (DELIVERED, {"status": "PAID"}),
        (
            {
                "status": "CANCELLED",
                "payment": "PENDING",
                "paid_at": "",
                "cancelled_at": "2026-10-29T10:00:00-04:00",
            },
            {**SHIPPED},
        ),
        (
            {
                "status": "CANCELLED",
                "payment": "PENDING",
                "paid_at": "",
                "cancelled_at": "2026-10-29T10:00:00-04:00",
            },
            {
                "status": "REFUNDED",
                "payment": "REFUNDED",
                "fulfillment": "UNFULFILLED",
                "cancelled_at": "2026-10-29T10:00:00-04:00",
            },
        ),
    ],
)
def test_unreachable_order_transition_is_a_row_error(
    client: TestClient, db: Session, first: dict[str, str], second: dict[str, str]
) -> None:
    """DELIVERED → PAID, CANCELLED → SHIPPED and unpaid CANCELLED → REFUNDED are rejected."""
    _, api = manager_api(client, db)
    _orders(api, order_row("KHK-1", **first))

    body = api.validated("orders", csv_bytes(ORDER_HEADER, order_row("KHK-1", **second)))

    assert (2, "ORDER_TRANSITION_NOT_ALLOWED") in api.codes(body["id"])
    assert body["summary"]["rows_with_errors"] == 1


@pytest.mark.parametrize(
    ("overrides", "code", "column"),
    [
        (
            {
                "status": "SHIPPED",
                "payment": "PENDING",
                "fulfillment": "SHIPPED",
                "paid_at": "",
                "shipped_at": "2026-10-29T10:00:00-04:00",
            },
            "ORDER_INVALID_STATUS_COMBINATION",
            "payment_status",
        ),
        (
            {"status": "PAID", "fulfillment": "SHIPPED", "shipped_at": "2026-10-29T10:00:00-04:00"},
            "ORDER_INVALID_STATUS_COMBINATION",
            "fulfillment_status",
        ),
        ({"paid_at": ""}, "ORDER_MISSING_TIMESTAMP", "paid_at"),
        (
            {"status": "CANCELLED", "payment": "PENDING", "paid_at": ""},
            "ORDER_MISSING_TIMESTAMP",
            "cancelled_at",
        ),
        ({**DELIVERED, "delivered_at": ""}, "ORDER_MISSING_TIMESTAMP", "delivered_at"),
        ({"paid_at": "2026-10-28T13:00:00-04:00"}, "ORDER_TIMESTAMP_SEQUENCE", "paid_at"),
        ({"placed_at": "2026-02-30T10:00:00"}, "INVALID_DATETIME", "placed_at"),
        ({"paid_at": "28/10/2026 14:06"}, "INVALID_DATETIME", "paid_at"),
        ({"currency": "EUR"}, "CURRENCY_MISMATCH", "currency"),
        ({"total": "-1.00"}, "NEGATIVE_VALUE", "total"),
        ({"status": "SENT"}, "INVALID_ENUM", "status"),
        ({"status": "REFUNDED", "payment": "REFUNDED"}, "REQUIRED", "fulfillment_status"),
    ],
)
def test_order_row_errors(
    client: TestClient, db: Session, overrides: dict[str, str], code: str, column: str
) -> None:
    _, api = manager_api(client, db)

    body = api.validated("orders", csv_bytes(ORDER_HEADER, order_row("KHK-1", **overrides)))

    issues = api.issues(body["id"], severity="ERROR")
    assert [(i["code"], i["column"]) for i in issues] == [(code, column)]
    assert body["summary"]["preview"] == [
        {"row_number": 2, "key": "KHK-1", "action": "SKIP", "changed_fields": []}
    ]


def test_lowercase_currency_and_absent_optional_columns_keep_order_values(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    header = (
        "order_number,channel,placed_at,status,payment_status,paid_at,currency,subtotal,total,"
        "carrier"
    )
    api.run(
        "orders",
        csv_bytes(
            header,
            "KHK-1,MARKETPLACE,2026-10-28T14:05:00-04:00,PAID,PAID,2026-10-28T14:06:00-04:00,usd,"
            "32.00,32.00,UPS",
        ),
    )

    body = api.run(
        "orders",
        csv_bytes(
            "order_number,placed_at,status,payment_status,paid_at,currency,subtotal,total",
            "KHK-1,2026-10-28T14:05:00-04:00,PROCESSING,PAID,2026-10-28T14:06:00-04:00,USD,32.00,32.00",
        ),
    )

    assert body["summary"]["preview"][0]["changed_fields"] == ["status", "fulfillment_status"]
    order = _order(db, "KHK-1")
    assert (order.channel, order.carrier, order.currency) == (
        SalesChannel.MARKETPLACE,
        "UPS",
        "USD",
    )


def _catalog(api: ImportApi) -> None:
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-MUG"), product_row("KHK-JAR")))
    api.run(
        "inventory_adjustments",
        csv_bytes(ADJUSTMENT_HEADER, adjustment_row("CC-1", "KHK-MUG", qty="20")),
    )


def test_order_items_unknown_references_and_quantities(client: TestClient, db: Session) -> None:
    """BR-605 referential integrity; quantity ≥ 1; line discount ≤ line value."""
    _, api = manager_api(client, db)
    _catalog(api)
    _orders(api, order_row("KHK-1"))

    body = api.validated(
        "order_items",
        csv_bytes(
            ITEM_HEADER,
            item_row("KHK-404", 1, "KHK-MUG"),
            item_row("KHK-1", 1, "KHK-NOPE"),
            item_row("KHK-1", 2, "KHK-MUG", qty="-1"),
            item_row("KHK-1", 3, "KHK-MUG", qty="0"),
            item_row("KHK-1", 4, "KHK-MUG", qty="1", price="16.00", discount="16.01"),
            item_row("KHK-1", 0, "KHK-MUG"),
            item_row("KHK-1", 5, "KHK-MUG"),
            item_row("KHK-1", 5, "KHK-JAR"),
        ),
    )

    assert api.codes(body["id"]) == {
        (2, "UNKNOWN_ORDER"),
        (3, "UNKNOWN_SKU"),
        (4, "NEGATIVE_VALUE"),
        (5, "INVALID_INTEGER"),
        (6, "LINE_DISCOUNT_EXCEEDS_LINE"),
        (7, "INVALID_INTEGER"),
        (9, "DUPLICATE_KEY_IN_FILE"),
    }
    assert body["summary"]["creates"] == 1


def test_br609_line_lock_applies_only_to_recorded_lines_of_shipped_orders(
    client: TestClient, db: Session
) -> None:
    """Recording a shipped order's line for the first time is allowed and writes the shipment
    (BR-130); changing it afterwards is ORDER_LINE_LOCKED; an identical row is UNCHANGED."""
    _, api = manager_api(client, db)
    _catalog(api)
    _orders(api, order_row("KHK-1", **SHIPPED))

    first = api.run("order_items", csv_bytes(ITEM_HEADER, item_row("KHK-1", 1, "KHK-MUG", qty="2")))
    changed = api.validated(
        "order_items",
        csv_bytes(
            ITEM_HEADER,
            item_row("KHK-1", 1, "KHK-MUG", qty="3"),
            item_row("KHK-1", 2, "KHK-JAR", qty="1"),
        ),
    )
    same = api.validated(
        "order_items", csv_bytes(ITEM_HEADER, item_row("KHK-1", 1, "KHK-MUG", qty="2"))
    )

    assert first["status"] == "COMPLETED"
    assert api.codes(changed["id"]) == {(2, "ORDER_LINE_LOCKED")}
    assert changed["summary"]["creates"] == 1  # a new line on a shipped order is allowed
    assert same["summary"]["unchanged"] == 1
    assert same["summary"]["rows_with_errors"] == 0
    shipments = db.scalars(
        select(InventoryMovement).where(InventoryMovement.movement_type == MovementType.SHIPMENT)
    ).all()
    assert [(m.on_hand_delta, m.on_hand_after) for m in shipments] == [(-2, 18)]


def test_line_lock_does_not_apply_before_shipping(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    _catalog(api)
    _orders(api, order_row("KHK-1"))
    api.run("order_items", csv_bytes(ITEM_HEADER, item_row("KHK-1", 1, "KHK-MUG", qty="2")))

    body = api.run("order_items", csv_bytes(ITEM_HEADER, item_row("KHK-1", 1, "KHK-MUG", qty="5")))

    assert body["summary"]["preview"][0]["changed_fields"] == ["quantity"]
    assert body["summary"]["applied"]["updates"] == 1
