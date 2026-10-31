"""The files in sample-data/ behave as sample-data/README.md describes (BR-601..609)."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product
from app.domains.inventory import service as inventory
from tests.factories_imports import SAMPLE_DATA, ImportApi, manager_api, sample_file

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.path.isdir(SAMPLE_DATA), reason="sample-data/ is not available"),
]

VALID_SEQUENCE = ("products", "inventory_adjustments", "orders", "order_items")


def _import_valid_set(api: ImportApi) -> None:
    for import_type in VALID_SEQUENCE:
        body = api.run(import_type, sample_file("examples", "valid", f"{import_type}.csv"))
        assert body["status"] == "COMPLETED", body
        assert body["summary"]["rows_with_errors"] == 0


def test_valid_examples_import_cleanly_and_reconcile(client: TestClient, db: Session) -> None:
    """Products -> adjustments -> orders -> items; balances match the README (BR-101, BR-130)."""
    tenant, api = manager_api(client, db)

    _import_valid_set(api)

    def position(sku: str) -> tuple[int, int, int]:
        product = db.query(Product).filter_by(store_id=tenant.store.id, sku=sku).one()
        balance = inventory.get_balance(db, tenant.store.id, product.id)
        return balance.on_hand, balance.reserved, balance.available

    assert position("KHK-MUG-12OZ-SAGE") == (46, 2, 44)
    assert position("KHK-MUG-12OZ-CHAR") == (28, 3, 25)
    assert position("KHK-PAN-CI-10") == (14, 1, 13)
    assert position("KHK-TWL-LIN-2PK") == (40, 2, 38)
    assert inventory.reconcile(db, tenant.store.id) == []


@pytest.mark.parametrize(
    ("filename", "import_type", "code"),
    [
        ("empty.csv", "products", "FILE_EMPTY"),
        ("orders_header_only.csv", "orders", "FILE_EMPTY"),
        ("products_wrong_extension.txt", "products", "FILE_TYPE"),
        ("products_cp1252.csv", "products", "FILE_ENCODING"),
        ("products_missing_columns.csv", "products", "MISSING_COLUMNS"),
    ],
)
def test_invalid_examples_rejected_at_file_level(
    client: TestClient, db: Session, filename: str, import_type: str, code: str
) -> None:
    _, api = manager_api(client, db)

    response = api.upload(import_type, sample_file("examples", "invalid", filename), filename)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "REJECTED"
    assert [issue["code"] for issue in body["file_issues"]] == [code]


@pytest.mark.parametrize(
    ("filename", "import_type", "expected"),
    [
        (
            "products_row_errors.csv",
            "products",
            {
                (3, "DUPLICATE_KEY_IN_FILE"),
                (4, "NEGATIVE_VALUE"),
                (5, "INVALID_ENUM"),
                (6, "INVALID_NUMBER"),
                (7, "NEGATIVE_VALUE"),
                (8, "PRICE_ZERO"),
                (9, "NEGATIVE_MARGIN"),
            },
        ),
        (
            "orders_row_errors.csv",
            "orders",
            {
                (2, "CURRENCY_MISMATCH"),
                (3, "ORDER_INVALID_STATUS_COMBINATION"),
                (4, "ORDER_MISSING_TIMESTAMP"),
                (5, "INVALID_DATETIME"),
                (6, "ORDER_TIMESTAMP_SEQUENCE"),
                (7, "INVALID_ENUM"),
                (8, "REQUIRED"),
            },
        ),
        (
            "orders_unreachable_transition.csv",
            "orders",
            {(2, "ORDER_TRANSITION_NOT_ALLOWED")},
        ),
        (
            "order_items_row_errors.csv",
            "order_items",
            {
                (2, "UNKNOWN_ORDER"),
                (3, "UNKNOWN_SKU"),
                (4, "INVALID_INTEGER"),
                (5, "NEGATIVE_VALUE"),
                (6, "LINE_DISCOUNT_EXCEEDS_LINE"),
                (7, "ORDER_LINE_LOCKED"),
                (9, "DUPLICATE_KEY_IN_FILE"),
            },
        ),
        (
            "inventory_adjustments_row_errors.csv",
            "inventory_adjustments",
            {
                (2, "ALREADY_APPLIED"),
                (3, "NEGATIVE_VALUE"),
                (4, "INVALID_INTEGER"),
                (5, "STALE_CYCLE_COUNT"),
                (6, "UNKNOWN_SKU"),
                (7, "INVALID_ENUM"),
                (8, "RESERVED_REFERENCE"),
                (9, "INVALID_DATETIME"),
            },
        ),
    ],
)
def test_invalid_examples_report_documented_row_issues(
    client: TestClient,
    db: Session,
    filename: str,
    import_type: str,
    expected: set[tuple[int, str]],
) -> None:
    _, api = manager_api(client, db)
    _import_valid_set(api)

    body = api.validated(import_type, sample_file("examples", "invalid", filename))

    assert body["status"] == "VALIDATED"
    assert api.codes(body["id"]) == expected
