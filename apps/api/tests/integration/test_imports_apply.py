"""Apply, discard, expiry, idempotency and atomicity (STATE_MACHINES §4, BR-110..113, BR-606)."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.domains.audit.models import AuditLog
from app.domains.catalog import service as catalog
from app.domains.catalog.models import Product
from app.domains.exceptions import engine
from app.domains.exceptions.models import EvaluationRun, EvaluationTrigger
from app.domains.imports.models import DataImport, ImportStatus
from app.domains.inventory import service as inventory
from app.domains.inventory.models import (
    InventoryBalance,
    InventoryMovement,
    ReservationStatus,
    StockReservation,
)
from app.domains.orders.models import Order, OrderStatus
from tests.factories_imports import (
    ADJUSTMENT_HEADER,
    ITEM_HEADER,
    ORDER_HEADER,
    PRODUCT_HEADER,
    adjustment_row,
    csv_bytes,
    item_row,
    manager_api,
    order_row,
    product_row,
)

pytestmark = pytest.mark.integration

MIXED_PRODUCTS = csv_bytes(
    PRODUCT_HEADER,
    product_row("KHK-1"),
    product_row("KHK-2", price="-1.00"),
    product_row("KHK-3"),
    product_row("KHK-4", status="GONE"),
)


def _record(db: Session, import_id: str) -> DataImport:
    db.expire_all()
    record = db.get(DataImport, uuid.UUID(import_id))
    assert record is not None
    return record


def _skus(db: Session) -> list[str]:
    db.expire_all()
    return sorted(db.scalars(select(Product.sku)).all())


def _actions(db: Session) -> list[str]:
    return list(db.scalars(select(AuditLog.action).where(AuditLog.action.like("import.%"))).all())


def test_br606_strict_mode_is_blocked_while_rows_have_errors(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", MIXED_PRODUCTS)

    response = api.apply(body["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "IMPORT_HAS_ERRORS"
    assert error["details"] == [{"rows_with_errors": 2}]
    assert _record(db, body["id"]).status is ImportStatus.VALIDATED
    assert _skus(db) == []


@pytest.mark.parametrize("confirm", [None, 0, 1, 3])
def test_br606_valid_rows_only_requires_the_exact_skipped_count(
    client: TestClient, db: Session, confirm: int | None
) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", MIXED_PRODUCTS)

    response = api.apply(body["id"], mode="VALID_ROWS_ONLY", confirm=confirm)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "SKIPPED_ROWS_NOT_CONFIRMED"
    assert error["details"][0]["expected_confirm_skipped_rows"] == 2
    assert _record(db, body["id"]).status is ImportStatus.VALIDATED


def test_br606_valid_rows_only_applies_valid_rows_and_keeps_skipped_rows_visible(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", MIXED_PRODUCTS)

    response = api.apply(body["id"], mode="VALID_ROWS_ONLY", confirm=2)

    assert response.status_code == 200, response.text
    applied = response.json()
    assert applied["status"] == "COMPLETED_WITH_ERRORS"
    assert applied["mode"] == "VALID_ROWS_ONLY"
    assert applied["summary"]["applied"] == {
        "mode": "VALID_ROWS_ONLY",
        "creates": 2,
        "updates": 0,
        "unchanged": 0,
        "skipped": 2,
    }
    assert _skus(db) == ["KHK-1", "KHK-3"]
    # Skipped rows stay downloadable (STATE_MACHINES §4: nothing is skipped silently).
    assert {row for row, _ in api.codes(body["id"])} == {3, 5}
    record = _record(db, body["id"])
    assert record.content is None
    assert record.applied_at is not None
    assert _actions(db) == ["import.applied"]


def test_valid_rows_only_without_errors_completes(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    response = api.apply(body["id"], mode="VALID_ROWS_ONLY")

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


def test_apply_writes_audit_and_triggers_import_evaluation(client: TestClient, db: Session) -> None:
    """STATE_MACHINES §4: after COMPLETED an evaluation run with trigger IMPORT starts."""
    tenant, api = manager_api(client, db)

    body = api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    assert body["status"] == "COMPLETED"
    assert body["evaluation_run_id"] is not None
    run = db.get(EvaluationRun, uuid.UUID(body["evaluation_run_id"]))
    assert run is not None
    assert run.trigger is EvaluationTrigger.IMPORT
    assert str(run.import_id) == body["id"]
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "import.applied")).one()
    assert audit.store_id == tenant.store.id
    assert audit.target_id == body["id"]
    assert audit.details["creates"] == 1


def test_failing_evaluation_never_undoes_the_import(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, api = manager_api(client, db)

    def broken(*args: Any, **kwargs: Any) -> EvaluationRun:
        raise RuntimeError("engine down")

    monkeypatch.setattr(engine, "run_evaluation", broken)

    body = api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    assert body["status"] == "COMPLETED"
    assert body["evaluation_run_id"] is None
    assert "did not complete" in body["summary"]["evaluation_error"]
    assert _skus(db) == ["KHK-1"]


def test_preview_expires_after_24_hours(client: TestClient, db: Session) -> None:
    """STATE_MACHINES §4: VALIDATED → DISCARDED when the preview expires."""
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    record = _record(db, body["id"])
    record.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    response = api.apply(body["id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMPORT_EXPIRED"
    record = _record(db, body["id"])
    assert record.status is ImportStatus.DISCARDED
    assert record.content is None
    assert api.apply(body["id"]).json()["error"]["code"] == "IMPORT_NOT_APPLICABLE"
    assert _skus(db) == []


def test_expired_previews_are_discarded_lazily_on_read(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    first = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    second = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-2")))
    db.execute(
        update(DataImport)
        .where(DataImport.id.in_([uuid.UUID(first["id"]), uuid.UUID(second["id"])]))
        .values(expires_at=utcnow() - timedelta(minutes=1))
    )
    db.commit()

    detail = api.get(first["id"]).json()
    listing = api.client.get(api.base, params={"status": "VALIDATED"}).json()

    assert detail["status"] == "DISCARDED"
    assert listing["total"] == 0
    assert _record(db, second["id"]).content is None


def test_interrupted_apply_is_reported_as_failed_on_read(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    record = _record(db, body["id"])
    record.status = ImportStatus.APPLYING
    db.commit()
    record.updated_at = utcnow() - timedelta(minutes=16)
    db.commit()

    detail = api.get(body["id"]).json()

    assert detail["status"] == "FAILED"
    assert detail["failure_reason"].startswith("IMPORT_INTERRUPTED")
    assert detail["can_revalidate"] is True  # nothing was applied; the file is still stored


def test_discard_purges_bytes_and_is_audited(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    discarded = api.discard(body["id"])
    again = api.discard(body["id"])

    assert discarded.status_code == 200
    assert discarded.json()["status"] == "DISCARDED"
    assert again.status_code == 200
    assert _record(db, body["id"]).content is None
    assert _actions(db) == ["import.discarded"]
    assert api.apply(body["id"]).json()["error"]["code"] == "IMPORT_NOT_APPLICABLE"
    assert _skus(db) == []


def test_only_validated_imports_can_be_discarded_or_applied(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    completed = api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    rejected = api.validated("products", b"")

    assert api.discard(completed["id"]).json()["error"]["code"] == "IMPORT_NOT_DISCARDABLE"
    assert api.apply(completed["id"]).json()["error"]["code"] == "IMPORT_NOT_APPLICABLE"
    assert api.apply(rejected["id"]).status_code == 409


def test_idempotency_key_replays_the_stored_result(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    first = api.apply(body["id"], key="apply-7f3c")
    replay = api.apply(body["id"], key="apply-7f3c")
    other_key = api.apply(body["id"], key="apply-other")
    no_key = api.apply(body["id"])
    other_mode = api.apply(body["id"], mode="VALID_ROWS_ONLY", key="apply-7f3c")

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["status"] == "COMPLETED"
    assert replay.json()["evaluation_run_id"] == first.json()["evaluation_run_id"]
    assert "apply_idempotency_key" not in replay.json()["summary"]
    assert other_key.json()["error"]["code"] == "IMPORT_NOT_APPLICABLE"
    assert no_key.status_code == 409
    assert other_mode.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _actions(db) == ["import.applied"]
    assert db.scalar(select(func.count()).select_from(EvaluationRun)) == 1


def test_apply_request_body_is_validated(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    url = f"{api.base}/{body['id']}/apply"
    headers = {"X-CSRF-Token": api.csrf}

    unknown = client.post(url, json={"mode": "STRICT", "force": True}, headers=headers)
    negative = client.post(
        url, json={"mode": "VALID_ROWS_ONLY", "confirm_skipped_rows": -1}, headers=headers
    )
    bad_mode = client.post(url, json={"mode": "YOLO"}, headers=headers)

    assert [r.status_code for r in (unknown, negative, bad_mode)] == [422, 422, 422]


def test_br606_failure_mid_apply_rolls_back_every_business_change(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure on the 3rd row leaves no product or supplier behind; the import is FAILED."""
    _, api = manager_api(client, db)
    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", supplier="Harbor Ceramics Co."),
            product_row("KHK-2", supplier="Northfield Blades"),
            product_row("KHK-3"),
            product_row("KHK-4"),
        ),
    )
    real = catalog.upsert_product
    calls = {"n": 0}

    def flaky(*args: Any, **kwargs: Any) -> tuple[Product, bool]:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(catalog, "upsert_product", flaky)

    response = api.apply(body["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "IMPORT_APPLY_FAILED"
    assert "disk full" not in response.text  # internals are logged, never returned
    assert error["request_id"]
    assert _skus(db) == []
    assert db.scalar(select(func.count()).select_from(catalog.Supplier)) == 0
    record = _record(db, body["id"])
    assert record.status is ImportStatus.FAILED
    assert record.failure_reason is not None
    assert record.failure_reason.startswith("IMPORT_APPLY_FAILED")
    # A failed import keeps its bytes until the preview expiry, so it can be validated again.
    assert record.content is not None
    assert api.get(body["id"]).json()["can_revalidate"] is True
    assert record.evaluation_run_id is None
    assert _actions(db) == ["import.failed"]


def test_adjustment_failure_mid_apply_leaves_ledger_untouched(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    body = api.validated(
        "inventory_adjustments",
        csv_bytes(
            ADJUSTMENT_HEADER,
            adjustment_row("CC-1", "KHK-1", qty="10"),
            adjustment_row("RCV-1", "KHK-1", "RECEIPT", "5", "2026-10-21T08:00:00-04:00"),
            adjustment_row("DMG-1", "KHK-1", "DAMAGE", "1", "2026-10-22T08:00:00-04:00"),
        ),
    )
    real = inventory.record_movement
    calls = {"n": 0}

    def flaky(*args: Any, **kwargs: Any) -> InventoryMovement:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("lost connection")
        return real(*args, **kwargs)

    monkeypatch.setattr(inventory, "record_movement", flaky)

    assert api.apply(body["id"]).status_code == 409
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 0
    assert db.scalar(select(func.count()).select_from(InventoryBalance)) == 0
    assert _record(db, body["id"]).status is ImportStatus.FAILED


def test_revalidation_detects_data_changed_since_preview(client: TestClient, db: Session) -> None:
    """Apply re-validates: an order that became DELIVERED meanwhile cannot go back to PAID."""
    _, api = manager_api(client, db)
    api.run("orders", csv_bytes(ORDER_HEADER, order_row("KHK-1", status="PAID")))
    pending = api.validated(
        "orders",
        csv_bytes(ORDER_HEADER, order_row("KHK-1", status="PROCESSING", fulfillment="IN_PROGRESS")),
    )
    api.run(
        "orders",
        csv_bytes(
            ORDER_HEADER,
            order_row(
                "KHK-1",
                status="DELIVERED",
                fulfillment="DELIVERED",
                shipped_at="2026-10-29T10:00:00-04:00",
                delivered_at="2026-10-30T10:00:00-04:00",
            ),
        ),
    )

    response = api.apply(pending["id"])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "IMPORT_DATA_CHANGED"
    assert error["details"][0]["code"] == "ORDER_TRANSITION_NOT_ALLOWED"
    db.expire_all()
    assert db.scalars(select(Order.status)).one() is OrderStatus.DELIVERED
    assert _record(db, pending["id"]).status is ImportStatus.FAILED


def test_validate_again_checks_the_stored_file_against_current_data(
    client: TestClient, db: Session
) -> None:
    """STATE_MACHINES §4 FAILED → VALIDATING (retry): the stale row now shows as an error."""
    _, api = manager_api(client, db)
    api.run("orders", csv_bytes(ORDER_HEADER, order_row("KHK-1", status="PAID")))
    pending = api.validated(
        "orders",
        csv_bytes(
            ORDER_HEADER,
            order_row("KHK-1", status="PROCESSING", fulfillment="IN_PROGRESS"),
            order_row("KHK-2", status="PAID"),
        ),
    )
    api.run(
        "orders",
        csv_bytes(
            ORDER_HEADER,
            order_row(
                "KHK-1",
                status="DELIVERED",
                fulfillment="DELIVERED",
                shipped_at="2026-10-29T10:00:00-04:00",
                delivered_at="2026-10-30T10:00:00-04:00",
            ),
        ),
    )
    assert api.apply(pending["id"]).json()["error"]["code"] == "IMPORT_DATA_CHANGED"
    assert api.get(pending["id"]).json()["can_revalidate"] is True

    response = api.revalidate(pending["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "VALIDATED"
    assert (body["mode"], body["failure_reason"], body["can_revalidate"]) == (None, None, False)
    assert body["summary"]["rows_with_errors"] == 1
    assert body["summary"]["creates"] == 1
    assert api.codes(pending["id"]) == {(2, "ORDER_TRANSITION_NOT_ALLOWED")}
    assert "import.revalidated" in _actions(db)
    again = api.revalidate(pending["id"])
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "IMPORT_NOT_APPLICABLE"

    applied = api.apply(pending["id"], mode="VALID_ROWS_ONLY", confirm=1)

    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "COMPLETED_WITH_ERRORS"
    db.expire_all()
    rows = db.execute(select(Order.order_number, Order.status)).all()
    assert {number: status for number, status in rows} == {
        "KHK-1": OrderStatus.DELIVERED,
        "KHK-2": OrderStatus.PAID,
    }


def test_validate_again_after_a_failed_apply_then_apply(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, api = manager_api(client, db)
    body = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    def broken(*args: Any, **kwargs: Any) -> tuple[Product, bool]:
        raise RuntimeError("disk full")

    monkeypatch.setattr(catalog, "upsert_product", broken)
    assert api.apply(body["id"]).json()["error"]["code"] == "IMPORT_APPLY_FAILED"
    monkeypatch.undo()

    revalidated = api.revalidate(body["id"])

    assert revalidated.status_code == 200, revalidated.text
    assert revalidated.json()["status"] == "VALIDATED"
    assert revalidated.json()["applied_by"] is None
    assert api.apply(body["id"]).json()["status"] == "COMPLETED"
    assert _skus(db) == ["KHK-1"]
    assert _record(db, body["id"]).content is None  # purged once applied


def test_a_failed_import_keeps_its_file_only_until_the_preview_expiry(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, api = manager_api(client, db)
    first = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    second = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-2")))

    def broken(*args: Any, **kwargs: Any) -> tuple[Product, bool]:
        raise RuntimeError("disk full")

    monkeypatch.setattr(catalog, "upsert_product", broken)
    for body in (first, second):
        assert api.apply(body["id"]).status_code == 409
    monkeypatch.undo()
    db.execute(
        update(DataImport)
        .where(DataImport.id.in_([uuid.UUID(first["id"]), uuid.UUID(second["id"])]))
        .values(expires_at=utcnow() - timedelta(minutes=1))
    )
    db.commit()

    detail = api.get(first["id"]).json()  # lazy purge of one record
    listing = client.get(api.base, params={"status": "FAILED"}).json()  # bulk purge
    refused = api.revalidate(first["id"])

    assert (detail["status"], detail["can_revalidate"]) == ("FAILED", False)
    assert [item["can_revalidate"] for item in listing["items"]] == [False, False]
    assert _record(db, first["id"]).content is None
    assert _record(db, second["id"]).content is None
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "IMPORT_CONTENT_MISSING"


def test_br112_reimporting_adjustments_changes_stock_once(client: TestClient, db: Session) -> None:
    tenant, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    content = csv_bytes(
        ADJUSTMENT_HEADER,
        adjustment_row("CC-1", "KHK-1", qty="10"),
        adjustment_row("RCV-1", "KHK-1", "RECEIPT", "5", "2026-10-21T08:00:00-04:00"),
    )
    api.run("inventory_adjustments", content)

    again = api.validated("inventory_adjustments", content)

    assert api.codes(again["id"]) == {
        (2, "ALREADY_APPLIED"),
        (3, "ALREADY_APPLIED"),
        (None, "DUPLICATE_FILE"),
    }
    assert again["summary"]["unchanged"] == 2
    assert again["summary"]["rows_with_errors"] == 0
    assert api.apply(again["id"]).json()["status"] == "COMPLETED"
    db.expire_all()
    balance = db.scalars(select(InventoryBalance)).one()
    assert balance.on_hand == 15
    assert db.scalar(select(func.count()).select_from(InventoryMovement)) == 2
    assert inventory.reconcile(db, tenant.store.id) == []


def test_br113_stale_cycle_counts_and_quantity_semantics(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), product_row("KHK-2")))
    api.run(
        "inventory_adjustments",
        csv_bytes(
            ADJUSTMENT_HEADER,
            adjustment_row("CC-1", "KHK-1", occurred_at="2026-10-20T08:00:00-04:00"),
        ),
    )

    body = api.validated(
        "inventory_adjustments",
        csv_bytes(
            ADJUSTMENT_HEADER,
            adjustment_row("CC-OLD", "KHK-1", occurred_at="2026-10-19T08:00:00-04:00"),
            adjustment_row("CC-B", "KHK-2", occurred_at="2026-10-25T08:00:00-04:00"),
            adjustment_row("CC-C", "KHK-2", occurred_at="2026-10-24T08:00:00-04:00"),
            adjustment_row("CC-NEG", "KHK-2", qty="-1", occurred_at="2026-10-26T08:00:00-04:00"),
            adjustment_row("RCV-NEG", "KHK-2", "RECEIPT", "-4"),
            adjustment_row("DMG-0", "KHK-2", "DAMAGE", "0"),
            adjustment_row("COR-0", "KHK-2", "CORRECTION", "0"),
            adjustment_row("COR-NEG", "KHK-2", "CORRECTION", "-3", "2026-10-27T08:00:00-04:00"),
            adjustment_row("SHP-1", "KHK-2", "SHIPMENT", "1"),
            adjustment_row("X-1", "KHK-404", "DAMAGE", "1"),
        ),
    )

    assert api.codes(body["id"]) == {
        (2, "STALE_CYCLE_COUNT"),
        (4, "STALE_CYCLE_COUNT"),
        (5, "NEGATIVE_VALUE"),
        (6, "NEGATIVE_VALUE"),
        (7, "INVALID_INTEGER"),
        (8, "INVALID_INTEGER"),
        (10, "INVALID_ENUM"),
        (11, "UNKNOWN_SKU"),
    }
    assert body["summary"]["creates"] == 2  # CC-B and the signed correction


def test_reserved_order_item_references_are_rejected(client: TestClient, db: Session) -> None:
    """Shipment movements own the ``order_item:`` reference space (BR-131)."""
    _, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))

    body = api.validated(
        "inventory_adjustments",
        csv_bytes(
            ADJUSTMENT_HEADER,
            adjustment_row(f"order_item:{uuid.uuid4()}", "KHK-1", "DAMAGE", "1"),
            adjustment_row("ORDER_ITEM:legacy-7", "KHK-1", "DAMAGE", "1"),
            adjustment_row("order-item-7", "KHK-1", "DAMAGE", "1"),
        ),
    )

    assert api.codes(body["id"]) == {(2, "RESERVED_REFERENCE"), (3, "RESERVED_REFERENCE")}
    assert body["summary"]["creates"] == 1


def _reserved(db: Session) -> dict[str, tuple[int, int, int]]:
    db.expire_all()
    rows = db.execute(
        select(Product.sku, InventoryBalance.on_hand, InventoryBalance.reserved).join(
            InventoryBalance, InventoryBalance.product_id == Product.id
        )
    ).all()
    return {sku: (on_hand, reserved, on_hand - reserved) for sku, on_hand, reserved in rows}


def test_reservations_and_available_after_full_import_sequence(
    client: TestClient, db: Session
) -> None:
    """products → adjustments → orders → items, then a status update (BR-101, BR-120..122)."""
    tenant, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-MUG"), product_row("KHK-JAR")))
    api.run(
        "inventory_adjustments",
        csv_bytes(
            ADJUSTMENT_HEADER,
            adjustment_row("CC-MUG", "KHK-MUG", qty="20"),
            adjustment_row("CC-JAR", "KHK-JAR", qty="5"),
        ),
    )
    api.run(
        "orders",
        csv_bytes(
            ORDER_HEADER,
            order_row("KHK-1", status="PAID"),
            order_row("KHK-2", status="PAYMENT_PENDING", payment="PENDING", paid_at=""),
            order_row("KHK-3", status="PROCESSING", fulfillment="IN_PROGRESS"),
        ),
    )
    api.run(
        "order_items",
        csv_bytes(
            ITEM_HEADER,
            item_row("KHK-1", 1, "KHK-MUG", qty="2"),
            item_row("KHK-1", 2, "KHK-JAR", qty="1"),
            item_row("KHK-2", 1, "KHK-MUG", qty="4"),
            item_row("KHK-3", 1, "KHK-JAR", qty="6"),
        ),
    )

    # Pending demand (KHK-2) is never reserved; KHK-JAR is oversold (BR-102: not clamped).
    assert _reserved(db) == {"KHK-MUG": (20, 2, 18), "KHK-JAR": (5, 7, -2)}

    api.run(
        "orders",
        csv_bytes(
            ORDER_HEADER,
            order_row("KHK-1", status="CANCELLED", cancelled_at="2026-10-29T09:00:00-04:00"),
        ),
    )

    assert _reserved(db) == {"KHK-MUG": (20, 0, 20), "KHK-JAR": (5, 6, -1)}
    statuses = db.scalars(select(StockReservation.status).order_by(StockReservation.quantity)).all()
    assert statuses == [
        ReservationStatus.RELEASED,
        ReservationStatus.RELEASED,
        ReservationStatus.ACTIVE,
    ]
    assert inventory.reconcile(db, tenant.store.id) == []
