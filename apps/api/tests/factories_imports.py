"""Test helpers for the import pipeline (CSV builders and an API client wrapper)."""

import csv
import io
import os
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.domains.identity.permissions import Role
from tests.factories import Tenant, create_tenant, create_user, login

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DATA = os.path.join(os.path.dirname(os.path.dirname(API_ROOT)), "sample-data")

PRODUCT_HEADER = (
    "sku,name,category,status,unit_price,unit_cost,reorder_point,reorder_quantity,"
    "supplier_name,supplier_lead_time_days"
)
ORDER_HEADER = (
    "order_number,channel,customer_ref,placed_at,status,payment_status,fulfillment_status,"
    "paid_at,ship_by,shipped_at,delivered_at,cancelled_at,currency,subtotal,discount_total,"
    "shipping_total,tax_total,total,carrier,tracking_number"
)
ITEM_HEADER = "order_number,line_number,sku,quantity,unit_price,line_discount"
ADJUSTMENT_HEADER = "reference,sku,adjustment_type,quantity,occurred_at,expected_at,note"


def csv_bytes(header: str, *rows: str) -> bytes:
    """Join a header and pre-formatted rows into a CSV file body."""
    return ("\n".join((header, *rows)) + "\n").encode("utf-8")


def rows_to_csv(header: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def product_row(
    sku: str,
    *,
    name: str = "Stoneware Mug",
    status: str = "ACTIVE",
    price: str = "16.00",
    cost: str = "5.40",
    reorder_point: str = "10",
    supplier: str = "Harbor Ceramics Co.",
    lead_time: str = "21",
) -> str:
    return (
        f"{sku},{name},Drinkware,{status},{price},{cost},{reorder_point},30,{supplier},{lead_time}"
    )


def order_row(
    number: str,
    *,
    status: str = "PAID",
    payment: str = "PAID",
    fulfillment: str = "",
    placed_at: str = "2026-10-28T14:05:00-04:00",
    paid_at: str = "2026-10-28T14:06:00-04:00",
    shipped_at: str = "",
    delivered_at: str = "",
    cancelled_at: str = "",
    currency: str = "USD",
    subtotal: str = "32.00",
    total: str = "32.00",
) -> str:
    return (
        f"{number},WEB,CUST-1,{placed_at},{status},{payment},{fulfillment},{paid_at},,"
        f"{shipped_at},{delivered_at},{cancelled_at},{currency},{subtotal},0.00,0.00,0.00,"
        f"{total},,"
    )


def item_row(
    number: str, line: int, sku: str, qty: str = "2", price: str = "16.00", discount: str = "0.00"
) -> str:
    return f"{number},{line},{sku},{qty},{price},{discount}"


def adjustment_row(
    reference: str,
    sku: str,
    kind: str = "CYCLE_COUNT",
    qty: str = "20",
    occurred_at: str = "2026-10-20T08:00:00-04:00",
) -> str:
    return f"{reference},{sku},{kind},{qty},{occurred_at},,"


def sample_file(*parts: str) -> bytes:
    with open(os.path.join(SAMPLE_DATA, *parts), "rb") as handle:
        return handle.read()


@dataclass
class ImportApi:
    """Calls the imports endpoints for one store as the signed-in user."""

    client: TestClient
    store_id: str
    csrf: str

    @property
    def base(self) -> str:
        return f"/api/v1/stores/{self.store_id}/imports"

    def upload(self, import_type: str, content: bytes, filename: str | None = None) -> Response:
        return self.client.post(
            self.base,
            data={"import_type": import_type},
            files={"file": (filename or f"{import_type}.csv", content, "text/csv")},
            headers={"X-CSRF-Token": self.csrf},
        )

    def validated(self, import_type: str, content: bytes) -> dict[str, Any]:
        response = self.upload(import_type, content)
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    def apply(
        self,
        import_id: str,
        mode: str = "STRICT",
        confirm: int | None = None,
        key: str | None = None,
    ) -> Response:
        headers = {"X-CSRF-Token": self.csrf}
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.client.post(
            f"{self.base}/{import_id}/apply",
            json={"mode": mode, "confirm_skipped_rows": confirm},
            headers=headers,
        )

    def discard(self, import_id: str) -> Response:
        return self.client.post(
            f"{self.base}/{import_id}/discard", headers={"X-CSRF-Token": self.csrf}
        )

    def revalidate(self, import_id: str) -> Response:
        return self.client.post(
            f"{self.base}/{import_id}/revalidate", headers={"X-CSRF-Token": self.csrf}
        )

    def run(self, import_type: str, content: bytes) -> dict[str, Any]:
        """Upload and apply in strict mode; the file must be valid."""
        body = self.validated(import_type, content)
        assert body["status"] == "VALIDATED", body
        assert body["summary"]["rows_with_errors"] == 0, self.issues(body["id"])
        response = self.apply(body["id"])
        assert response.status_code == 200, response.text
        applied: dict[str, Any] = response.json()
        return applied

    def get(self, import_id: str) -> Response:
        return self.client.get(f"{self.base}/{import_id}")

    def issues(self, import_id: str, **params: Any) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base}/{import_id}/issues", params={"page_size": 100, **params}
        )
        assert response.status_code == 200, response.text
        items: list[dict[str, Any]] = response.json()["items"]
        return items

    def codes(self, import_id: str) -> set[tuple[int | None, str]]:
        return {(issue["row_number"], issue["code"]) for issue in self.issues(import_id)}


def manager_api(client: TestClient, db: Session, slug: str = "kestrel") -> tuple[Tenant, ImportApi]:
    tenant = create_tenant(db, slug)
    create_user(db, tenant, Role.MANAGER)
    csrf = login(client, f"manager@{slug}.example")
    return tenant, ImportApi(client, str(tenant.store.id), csrf)
