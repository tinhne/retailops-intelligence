"""Permissions, tenancy, listing, issue export and templates for the imports API (ADR-0007)."""

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.identity.permissions import Role
from app.domains.imports.models import ImportType
from app.domains.imports.templates import render_template
from tests.factories import create_tenant, create_user, login
from tests.factories_imports import (
    PRODUCT_HEADER,
    ImportApi,
    csv_bytes,
    manager_api,
    product_row,
)

pytestmark = pytest.mark.integration

GOOD = csv_bytes(PRODUCT_HEADER, product_row("KHK-1"))


def _endpoints(base: str, import_id: str) -> list[tuple[str, str]]:
    return [
        ("GET", base),
        ("GET", f"{base}/templates/products"),
        ("GET", f"{base}/{import_id}"),
        ("GET", f"{base}/{import_id}/issues"),
        ("GET", f"{base}/{import_id}/issues.csv"),
        ("POST", f"{base}/{import_id}/apply"),
        ("POST", f"{base}/{import_id}/discard"),
        ("POST", f"{base}/{import_id}/revalidate"),
    ]


@pytest.mark.parametrize("role", [Role.STAFF, Role.VIEWER, Role.ANALYST])
def test_read_only_roles_can_read_but_not_run_imports(
    client: TestClient, db: Session, role: Role
) -> None:
    tenant, manager = manager_api(client, db)
    body = manager.validated("products", GOOD)
    client.cookies.clear()
    create_user(db, tenant, role)
    api = ImportApi(
        client, str(tenant.store.id), login(client, f"{role.value.lower()}@kestrel.example")
    )

    upload = api.upload("products", GOOD)
    apply = api.apply(body["id"])
    discard = api.discard(body["id"])
    revalidate = api.revalidate(body["id"])

    for response in (upload, apply, discard, revalidate):
        assert response.status_code == 403
        assert response.json()["error"]["details"] == [{"missing_permission": "imports.run"}]
    for method, url in _endpoints(api.base, body["id"])[:5]:
        assert client.request(method, url).status_code == 200, url
    assert manager.get(body["id"]).json()["status"] == "VALIDATED"


def test_other_tenants_imports_are_not_found(client: TestClient, db: Session) -> None:
    globex = create_tenant(db, "globex")
    create_user(db, globex, Role.OWNER)
    globex_api = ImportApi(client, str(globex.store.id), login(client, "owner@globex.example"))
    foreign = globex_api.validated("products", GOOD)
    client.cookies.clear()
    _, api = manager_api(client, db)
    own = api.validated("products", GOOD)

    # Another tenant's store: 404 on every endpoint, including the upload.
    for method, url in [*_endpoints(globex_api.base, foreign["id"]), ("POST", globex_api.base)]:
        response = client.request(method, url, headers={"X-CSRF-Token": api.csrf})
        assert response.status_code == 404, url
        assert response.json()["error"]["code"] == "NOT_FOUND"
    # Another tenant's import id under the caller's own store: also 404.
    for method, url in _endpoints(api.base, foreign["id"])[2:]:
        response = client.request(
            method, url, headers={"X-CSRF-Token": api.csrf}, json={"mode": "STRICT"}
        )
        assert response.status_code == 404, url
    listing = client.get(api.base).json()
    assert [item["id"] for item in listing["items"]] == [own["id"]]


def test_imports_require_authentication(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    response = client.get(f"/api/v1/stores/{tenant.store.id}/imports")
    assert response.status_code == 401


def test_upload_requires_csrf_header(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    response = client.post(
        api.base, data={"import_type": "products"}, files={"file": ("p.csv", GOOD, "text/csv")}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_upload_rejects_unknown_import_type(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    response = api.upload("customers", GOOD)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_list_filters_sorts_and_paginates(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    first = api.run("products", GOOD)
    second = api.validated("orders", b"")
    third = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-2")))

    default = client.get(api.base).json()
    oldest_first = client.get(api.base, params={"sort": "created_at", "page_size": 2}).json()
    products = client.get(api.base, params={"import_type": "products"}).json()
    rejected = client.get(api.base, params={"status": "REJECTED"}).json()
    bad_sort = client.get(api.base, params={"sort": "file_sha256"})

    assert [i["id"] for i in default["items"]] == [third["id"], second["id"], first["id"]]
    assert (default["page"], default["page_size"], default["total"]) == (1, 25, 3)
    assert [i["id"] for i in oldest_first["items"]] == [first["id"], second["id"]]
    assert oldest_first["total"] == 3
    assert {i["id"] for i in products["items"]} == {first["id"], third["id"]}
    assert [i["id"] for i in rejected["items"]] == [second["id"]]
    assert bad_sort.status_code == 422
    assert "content" not in default["items"][0]
    assert default["items"][0]["can_revalidate"] is False


def test_list_filters_by_several_statuses(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    completed = api.run("products", GOOD)
    rejected = api.validated("orders", b"")
    validated = api.validated("products", csv_bytes(PRODUCT_HEADER, product_row("KHK-2")))

    def ids(*statuses: str) -> set[str]:
        response = client.get(api.base, params=[("status", status) for status in statuses])
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    assert ids("REJECTED", "VALIDATED") == {rejected["id"], validated["id"]}
    assert ids("COMPLETED") == {completed["id"]}
    assert ids("COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED") == {completed["id"]}
    assert ids() == {completed["id"], rejected["id"], validated["id"]}
    assert client.get(api.base, params={"status": "LOST"}).status_code == 422


def test_issues_are_paginated_and_filterable(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER + ",barcode",
            product_row("KHK-1", price="0.00", cost="") + ",x",
            product_row("KHK-2", price="-1") + ",x",
            product_row("KHK-3", status="NOPE") + ",x",
        ),
    )
    url = f"{api.base}/{body['id']}/issues"

    page = client.get(url, params={"page_size": 2}).json()
    errors = client.get(url, params={"severity": "ERROR"}).json()
    by_code = client.get(url, params={"code": "price_zero"}).json()
    descending = client.get(url, params={"sort": "-row_number"}).json()
    row_three = client.get(url, params={"row_number": 3}).json()
    row_absent = client.get(url, params={"row_number": 99}).json()
    row_invalid = client.get(url, params={"row_number": 0})

    assert [(i["row_number"], i["code"]) for i in row_three["items"]] == [(3, "NEGATIVE_VALUE")]
    assert row_absent["total"] == 0
    assert row_invalid.status_code == 422
    assert page["total"] == 4
    assert len(page["items"]) == 2
    assert page["items"][0]["code"] == "UNKNOWN_COLUMN"  # file-level issues first
    assert [i["code"] for i in errors["items"]] == ["NEGATIVE_VALUE", "INVALID_ENUM"]
    assert [(i["row_number"], i["severity"]) for i in by_code["items"]] == [(2, "WARNING")]
    assert [i["row_number"] for i in descending["items"]] == [4, 3, 2, None]


def test_issues_csv_escapes_formula_injection(client: TestClient, db: Session) -> None:
    """Cells starting with = + - @ tab or CR are prefixed with an apostrophe."""
    _, api = manager_api(client, db)
    body = api.validated(
        "products",
        csv_bytes(
            PRODUCT_HEADER,
            product_row('=HYPERLINK("http://evil.example")', status="@SUM(A1)"),
            product_row("KHK-2", price="-1.00"),
            product_row("KHK-3", price="+5e3"),
        ),
    )

    response = client.get(f"{api.base}/{body['id']}/issues.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == ["row_number", "column", "severity", "code", "message", "raw_value"]
    raw_values = {row[3]: row[5] for row in rows[1:]}
    assert raw_values["INVALID_ENUM"] == "'@SUM(A1)"
    assert raw_values["NEGATIVE_VALUE"] == "'-1.00"
    assert raw_values["INVALID_NUMBER"] == "'+5e3"
    assert len(rows) == 4
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(("=", "+", "-", "@", "\t", "\r"))


@pytest.mark.parametrize("import_type", list(ImportType))
def test_template_download_matches_contract(
    client: TestClient, db: Session, import_type: ImportType
) -> None:
    _, api = manager_api(client, db)

    response = client.get(f"{api.base}/templates/{import_type.value}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert f'filename="{import_type.value}_template.csv"' in response.headers["content-disposition"]
    assert response.text == render_template(import_type)
    # A template is itself a valid import file.
    assert api.validated(import_type.value, response.content)["status"] == "VALIDATED"


def test_unknown_template_type_is_rejected(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    assert client.get(f"{api.base}/templates/customers").status_code == 422


def test_unknown_import_id_is_not_found(client: TestClient, db: Session) -> None:
    _, api = manager_api(client, db)
    response = client.get(f"{api.base}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
