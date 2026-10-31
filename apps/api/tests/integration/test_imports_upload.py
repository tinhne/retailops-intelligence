"""Upload, file-level rejection and products validation (BR-602..604, BR-607, STATE_MACHINES §4)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.catalog.models import Product, ProductStatus, Supplier
from app.domains.imports import parsing
from app.domains.imports.models import DataImport, ImportRowIssue
from tests.factories_imports import (
    PRODUCT_HEADER,
    csv_bytes,
    manager_api,
    product_row,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("products.txt", csv_bytes(PRODUCT_HEADER, product_row("KHK-1")), "FILE_TYPE"),
        ("products.csv", b"", "FILE_EMPTY"),
        ("products.csv", csv_bytes(PRODUCT_HEADER), "FILE_EMPTY"),
        ("products.csv", csv_bytes("sku,name", "KHK-1,Mug"), "MISSING_COLUMNS"),
        (
            "products.csv",
            csv_bytes("order_number,placed_at,status", "KHK-1,2026-10-01,PAID"),
            "MISSING_COLUMNS",
        ),
        (
            "products.csv",
            csv_bytes(PRODUCT_HEADER, product_row("KHK-1", name="Café Cup")).replace(
                "é".encode(), "é".encode("cp1252")
            ),
            "FILE_ENCODING",
        ),
        ("products.csv", b"x" * (parsing.MAX_FILE_BYTES + 1), "FILE_TOO_LARGE"),
        (
            "products.csv",
            csv_bytes(PRODUCT_HEADER, *(f"K{i},M,,ACTIVE,1,,0,,," for i in range(20_001))),
            "TOO_MANY_ROWS",
        ),
    ],
)
def test_br602_file_level_failures_reject_with_201_and_reason(
    client: TestClient, db: Session, filename: str, content: bytes, code: str
) -> None:
    """STATE_MACHINES §4: VALIDATING → REJECTED; the UI receives the import and the reason."""
    _, api = manager_api(client, db)

    response = api.upload("products", content, filename)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["size_bytes"] == len(content)
    [issue] = body["file_issues"]
    assert (issue["code"], issue["severity"], issue["row_number"]) == (code, "ERROR", None)
    assert body["summary"]["issue_counts_by_code"] == {code: 1}
    record = db.get(DataImport, body["id"])
    assert record is not None
    assert record.content is None
    assert db.scalar(select(Product.id)) is None


def test_validated_upload_keeps_bytes_and_expires_after_24h(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    content = csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), product_row("KHK-2"))

    body = api.validated("products", content)

    assert body["status"] == "VALIDATED"
    assert body["row_count"] == 2
    assert body["summary"]["creates"] == 2
    validated_at = body["validated_at"]
    record = db.get(DataImport, body["id"])
    assert record is not None
    assert record.content == content
    assert record.expires_at is not None
    assert record.validated_at is not None
    assert record.expires_at - record.validated_at == timedelta(hours=24)
    assert validated_at is not None
    assert db.scalar(select(Product.id)) is None  # validation never writes business data


def test_preview_lists_planned_changes_with_changed_fields(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), product_row("KHK-2")))

    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", price="18.00", status="ARCHIVED"),
            product_row("KHK-2"),
            product_row("KHK-3"),
            product_row("", name="No SKU"),
        ),
    )

    summary = body["summary"]
    assert (summary["creates"], summary["updates"], summary["unchanged"]) == (1, 1, 1)
    assert (summary["rows_total"], summary["rows_valid"], summary["rows_with_errors"]) == (4, 3, 1)
    assert summary["preview"] == [
        {
            "row_number": 2,
            "key": "KHK-1",
            "action": "UPDATE",
            "changed_fields": ["status", "unit_price"],
        },
        {"row_number": 4, "key": "KHK-3", "action": "CREATE", "changed_fields": []},
        {"row_number": 5, "key": "", "action": "SKIP", "changed_fields": []},
    ]


def test_br604_duplicate_sku_in_file_errors_on_later_rows(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)

    body = api.validated(
        "products",
        csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), product_row("KHK-2"), product_row("KHK-1")),
    )

    assert api.codes(body["id"]) == {(4, "DUPLICATE_KEY_IN_FILE")}
    assert body["summary"]["rows_with_errors"] == 1


def test_products_negative_values_and_warnings(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)

    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", price="-1.00"),
            product_row("KHK-2", reorder_point="-5"),
            product_row("KHK-3", price="0.00", cost=""),
            product_row("KHK-4", price="10.00", cost="12.00"),
            product_row("KHK-5", status="DRAFT", price="0.00", cost=""),
            product_row("KHK-6", lead_time="400"),
        ),
    )

    assert api.codes(body["id"]) == {
        (2, "NEGATIVE_VALUE"),
        (3, "NEGATIVE_VALUE"),
        (4, "PRICE_ZERO"),
        (5, "NEGATIVE_MARGIN"),
        (7, "INVALID_INTEGER"),
    }
    assert body["summary"]["rows_with_warnings"] == 2
    assert body["summary"]["rows_with_errors"] == 3


def test_unknown_column_and_timezone_warnings_do_not_flood(client: TestClient, db: Session) -> None:
    """BR-603 unknown columns; BR-502 naive timestamps produce one warning per column."""
    _, api = manager_api(client, db)
    rows = [
        f"KHK-{n},WEB,,2026-10-2{n % 9}T10:00:00,PAYMENT_PENDING,PENDING,,,,,,,USD,1.00,,,,1.00,,,x"
        for n in range(30)
    ]
    header = (
        "order_number,channel,customer_ref,placed_at,status,payment_status,fulfillment_status,"
        "paid_at,ship_by,shipped_at,delivered_at,cancelled_at,currency,subtotal,discount_total,"
        "shipping_total,tax_total,total,carrier,tracking_number,gift_note"
    )

    body = api.validated("orders", csv_bytes(header, *rows))

    issues = api.issues(body["id"])
    assert [(i["code"], i["column"], i["row_number"]) for i in issues] == [
        ("TIMEZONE_ASSUMED", "placed_at", None),
        ("UNKNOWN_COLUMN", "gift_note", None),
    ]
    assert issues[0]["message"].startswith("30 value(s) in placed_at")
    assert body["summary"]["rows_with_errors"] == 0
    assert {i["code"] for i in body["file_issues"]} == {"TIMEZONE_ASSUMED", "UNKNOWN_COLUMN"}


def test_br607_duplicate_file_is_flagged_but_can_still_be_applied(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    content = csv_bytes(PRODUCT_HEADER, product_row("KHK-1"))
    first = api.run("products", content)

    second = api.validated("products", content)

    assert first["file_issues"] == []
    assert [(i["code"], i["severity"]) for i in second["file_issues"]] == [
        ("DUPLICATE_FILE", "WARNING")
    ]
    assert second["summary"]["unchanged"] == 1
    assert api.apply(second["id"]).json()["status"] == "COMPLETED"
    # Same bytes but another import type is not a duplicate.
    rejected = api.upload("orders", content).json()
    assert "DUPLICATE_FILE" not in {i["code"] for i in rejected["file_issues"]}


def test_products_apply_upserts_by_sku_and_suppliers_by_name(
    client: TestClient, db: Session
) -> None:
    """BR-608: upsert by SKU; status changes allowed; supplier created then lead time updated."""
    tenant, api = manager_api(client, db)
    api.run(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", supplier="Harbor Ceramics Co.", lead_time="21"),
            product_row("KHK-2", supplier="Harbor Ceramics Co.", lead_time=""),
        ),
    )

    second = api.run(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", status="ARCHIVED", supplier="Harbor Ceramics Co.", lead_time="28"),
        ),
    )

    assert second["summary"]["applied"] == {
        "mode": "STRICT",
        "creates": 0,
        "updates": 1,
        "unchanged": 0,
        "skipped": 0,
    }
    db.expire_all()
    suppliers = db.scalars(select(Supplier).where(Supplier.store_id == tenant.store.id)).all()
    assert [(s.name, s.lead_time_days) for s in suppliers] == [("Harbor Ceramics Co.", 28)]
    products = {p.sku: p for p in db.scalars(select(Product)).all()}
    assert products["KHK-1"].status is ProductStatus.ARCHIVED
    assert products["KHK-1"].unit_price == Decimal("16.00")
    assert products["KHK-2"].supplier_id == suppliers[0].id


def test_absent_optional_columns_keep_stored_values_and_empty_cells_clear(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)
    api.run("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-1", cost="5.40")))

    unchanged = api.run(
        "products",
        csv_bytes(
            "sku,name,status,unit_price,reorder_point", "KHK-1,Stoneware Mug,ACTIVE,16.00,10"
        ),
    )
    cleared = api.run(
        "products",
        csv_bytes(
            "sku,name,status,unit_price,unit_cost,reorder_point",
            "KHK-1,Stoneware Mug,ACTIVE,16.00,,10",
        ),
    )

    assert unchanged["summary"]["unchanged"] == 1
    assert cleared["summary"]["preview"][0]["changed_fields"] == ["unit_cost"]
    db.expire_all()
    product = db.scalars(select(Product)).one()
    assert product.unit_cost is None
    assert product.supplier_id is not None
    assert product.category == "Drinkware"


def test_supplier_lead_time_rules(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)

    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row("KHK-1", supplier="Harbor", lead_time="21"),
            product_row("KHK-2", supplier="Harbor", lead_time="30"),
            product_row("KHK-3", supplier="", lead_time="10"),
        ),
    )

    assert api.codes(body["id"]) == {(3, "CONFLICTING_VALUE_IN_FILE"), (4, "REQUIRED")}


def test_row_issues_are_persisted_with_spreadsheet_row_numbers(
    client: TestClient, db: Session
) -> None:
    _, api = manager_api(client, db)

    body = api.validated(
        "products",
        csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), "", product_row("KHK-2", price="x")),
    )

    issue = db.scalars(select(ImportRowIssue).where(ImportRowIssue.import_id == body["id"])).one()
    assert (issue.row_number, issue.column, issue.code, issue.raw_value) == (
        4,
        "unit_price",
        "INVALID_NUMBER",
        "x",
    )
