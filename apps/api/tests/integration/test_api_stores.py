"""Store details, operational settings (BUSINESS_RULES.md §7, PRIORITY_MODEL.md) and members."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.audit.models import AuditLog
from app.domains.exceptions.models import EvaluationStatus, EvaluationTrigger
from app.domains.identity.models import DEFAULT_PRIORITY_WEIGHTS, StoreSettings
from app.domains.identity.permissions import Permission, Role
from app.domains.identity.store_schemas import PriorityWeights
from app.domains.imports.models import ImportStatus, ImportType
from tests.factories import create_tenant, create_user, login
from tests.factories_commerce import create_evaluation_run, create_import, strip_permission

pytestmark = pytest.mark.integration
T0 = datetime(2026, 10, 20, 12, tzinfo=UTC)


def _url(store_id: Any, path: str = "") -> str:
    return f"/api/v1/stores/{store_id}{path}"


def test_store_detail_returns_settings_defaults_and_data_freshness(
    client: TestClient, db: Session
) -> None:
    """Freshness = latest COMPLETED(_WITH_ERRORS) import per type (M-05) + latest run."""
    tenant = create_tenant(db)
    create_user(db, tenant, Role.VIEWER)
    create_import(db, tenant, ImportType.ORDERS, status=ImportStatus.COMPLETED, applied_at=T0)
    newest_orders = create_import(
        db,
        tenant,
        ImportType.ORDERS,
        status=ImportStatus.COMPLETED_WITH_ERRORS,
        applied_at=T0 + timedelta(hours=3),
    )
    # A failed or not-yet-applied import never counts as fresh data.
    create_import(db, tenant, ImportType.ORDERS, status=ImportStatus.FAILED, applied_at=None)
    create_import(db, tenant, ImportType.PRODUCTS, status=ImportStatus.VALIDATED, applied_at=None)
    create_evaluation_run(db, tenant, started_at=T0)
    latest_run = create_evaluation_run(
        db,
        tenant,
        started_at=T0 + timedelta(hours=4),
        status=EvaluationStatus.FAILED,
        trigger=EvaluationTrigger.IMPORT,
    )
    login(client, "viewer@acme.example")

    response = client.get(_url(tenant.store.id))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["store"] == {
        "id": str(tenant.store.id),
        "name": "Acme Store",
        "code": "ACME",
        "currency": "USD",
        "timezone": "America/New_York",
        "organization": {
            "id": str(tenant.organization.id),
            "name": "Acme Commerce",
            "is_demo": False,
        },
    }
    settings = body["settings"]
    assert settings["fulfillment_sla_hours"] == 48
    assert settings["approaching_reorder_factor"] == "1.25"
    assert settings["exposure_cap"] == "5000.00"
    assert settings["velocity_window_days"] == 28
    assert settings["priority_weights"] == DEFAULT_PRIORITY_WEIGHTS

    imports = {i["import_type"]: i for i in body["data_freshness"]["imports"]}
    assert set(imports) == {t.value for t in ImportType}
    assert imports["orders"]["import_id"] == str(newest_orders.id)
    assert imports["orders"]["status"] == "COMPLETED_WITH_ERRORS"
    assert imports["orders"]["applied_at"] == "2026-10-20T15:00:00Z"
    assert imports["products"] == {
        "import_type": "products",
        "import_id": None,
        "status": None,
        "applied_at": None,
    }
    run = body["data_freshness"]["last_evaluation_run"]
    assert run["id"] == str(latest_run.id)
    assert (run["status"], run["trigger"]) == ("FAILED", "IMPORT")
    assert run["finished_at"] == "2026-10-20T16:00:02Z"


def test_store_detail_without_any_run_reports_null(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.STAFF)
    login(client, "staff@acme.example")

    body = client.get(_url(tenant.store.id)).json()

    assert body["data_freshness"]["last_evaluation_run"] is None


def test_manager_updates_settings_partially_and_audits_before_after(
    client: TestClient, db: Session
) -> None:
    """BUSINESS_RULES.md §7: settings.manage required, change written to the audit log."""
    tenant = create_tenant(db)
    manager = create_user(db, tenant, Role.MANAGER)
    csrf = login(client, "manager@acme.example")
    weights = {
        **DEFAULT_PRIORITY_WEIGHTS,
        "severity": {"CRITICAL": 45, "HIGH": 30, "MEDIUM": 20, "LOW": 5},
        "age_cap": 13,  # 45 + 15 + 15 + 12 + 13 = 100
    }

    response = client.patch(
        _url(tenant.store.id, "/settings"),
        json={
            "fulfillment_sla_hours": 36,
            "approaching_reorder_factor": "1.50",
            "velocity_window_days": 14,
            "exposure_cap": 2500,
            "priority_weights": weights,
            "stall_threshold_hours": 12,  # unchanged: not audited
        },
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fulfillment_sla_hours"] == 36
    assert body["approaching_reorder_factor"] == "1.50"
    assert body["velocity_window_days"] == 14
    assert body["exposure_cap"] == "2500.00"
    assert body["priority_weights"] == weights
    assert body["refund_overdue_hours"] == 24  # untouched

    db.expire_all()
    stored = db.scalars(select(StoreSettings)).one()
    assert stored.fulfillment_sla_hours == 36
    assert stored.priority_weights == weights
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "settings.update")).one()
    assert entry.actor_user_id == manager.id
    assert entry.store_id == tenant.store.id
    assert (entry.target_type, entry.target_id) == ("store", str(tenant.store.id))
    assert entry.details["before"] == {
        "fulfillment_sla_hours": 48,
        "approaching_reorder_factor": "1.25",
        "velocity_window_days": 28,
        "exposure_cap": "5000.00",
        "priority_weights": DEFAULT_PRIORITY_WEIGHTS,
    }
    assert entry.details["after"] == {
        "fulfillment_sla_hours": 36,
        "approaching_reorder_factor": "1.50",
        "velocity_window_days": 14,
        "exposure_cap": "2500.00",
        "priority_weights": weights,
    }


def test_settings_update_without_changes_writes_no_audit_row(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.OWNER)
    csrf = login(client, "owner@acme.example")

    for body in ({}, {"fulfillment_sla_hours": 48}):
        response = client.patch(
            _url(tenant.store.id, "/settings"), json=body, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["fulfillment_sla_hours"] == 48

    assert db.scalars(select(AuditLog).where(AuditLog.action == "settings.update")).all() == []


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"fulfillment_sla_hours": 0}, "fulfillment_sla_hours"),
        ({"stall_threshold_hours": -3}, "stall_threshold_hours"),
        ({"refund_overdue_hours": 1.5}, "refund_overdue_hours"),
        ({"reopen_window_hours": "72"}, "reopen_window_hours"),
        ({"fulfillment_sla_hours": True}, "fulfillment_sla_hours"),
        ({"fulfillment_sla_hours": None}, None),
        ({"approaching_reorder_factor": "0.99"}, "approaching_reorder_factor"),
        ({"approaching_reorder_factor": "3.01"}, "approaching_reorder_factor"),
        ({"approaching_reorder_factor": "1.255"}, "approaching_reorder_factor"),
        ({"velocity_window_days": 6}, "velocity_window_days"),
        ({"velocity_window_days": 91}, "velocity_window_days"),
        ({"exposure_cap": 0}, "exposure_cap"),
        ({"exposure_cap": "-10.00"}, "exposure_cap"),
        ({"unknown_setting": 1}, "unknown_setting"),
    ],
)
def test_settings_validation_rejects_invalid_values(
    client: TestClient, db: Session, body: dict[str, Any], field: str | None
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.OWNER)
    csrf = login(client, "owner@acme.example")

    response = client.patch(
        _url(tenant.store.id, "/settings"), json=body, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    if field is not None:
        assert any(field in d["loc"] for d in error["details"]), error["details"]
    db.expire_all()
    assert db.scalars(select(StoreSettings)).one().fulfillment_sla_hours == 48


def _weights(**overrides: Any) -> dict[str, Any]:
    weights: dict[str, Any] = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in DEFAULT_PRIORITY_WEIGHTS.items()
    }
    weights.update(overrides)
    return weights


@pytest.mark.parametrize(
    "weights",
    [
        _weights(age_cap=9),  # max total 101 (PRIORITY_MODEL.md: at most 100)
        _weights(deadline={"overdue": 13, "within_24h": 8, "within_72h": 4}),  # 101
        _weights(severity={"CRITICAL": 50, "HIGH": 35, "MEDIUM": 20}),  # missing LOW
        _weights(severity={"CRITICAL": 50, "HIGH": 35, "MEDIUM": 20, "LOW": 8, "INFO": 1}),
        _weights(affected_orders_per_order=-1),
        _weights(exposure_cap_points=7.5),
        _weights(bonus=1),
        {k: v for k, v in DEFAULT_PRIORITY_WEIGHTS.items() if k != "age_cap"},
    ],
)
def test_priority_weights_must_keep_shape_and_max_total(
    client: TestClient, db: Session, weights: dict[str, Any]
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.MANAGER)
    csrf = login(client, "manager@acme.example")

    response = client.patch(
        _url(tenant.store.id, "/settings"),
        json={"priority_weights": weights},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422, response.text


def test_priority_weights_schema_matches_default_shape() -> None:
    """The validated schema and DEFAULT_PRIORITY_WEIGHTS describe the same document."""
    parsed = PriorityWeights.model_validate(DEFAULT_PRIORITY_WEIGHTS)
    assert parsed.model_dump() == DEFAULT_PRIORITY_WEIGHTS
    assert parsed.max_possible_score == 100


@pytest.mark.parametrize("role", [Role.STAFF, Role.ANALYST, Role.VIEWER])
def test_roles_without_settings_manage_cannot_patch_settings(
    client: TestClient, db: Session, role: Role
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, role)
    csrf = login(client, f"{role.value.lower()}@acme.example")

    response = client.patch(
        _url(tenant.store.id, "/settings"),
        json={"fulfillment_sla_hours": 24},
        headers={"X-CSRF-Token": csrf},
    )
    readable = client.get(_url(tenant.store.id, "/settings"))

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "settings.manage"}]
    assert readable.status_code == 200
    assert readable.json()["fulfillment_sla_hours"] == 48


def test_settings_patch_requires_csrf_header(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.OWNER)
    login(client, "owner@acme.example")

    response = client.patch(_url(tenant.store.id, "/settings"), json={"fulfillment_sla_hours": 24})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


def test_members_list_names_roles_and_work_permission_without_emails(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    other = create_tenant(db, "globex")
    create_user(db, tenant, Role.MANAGER)
    staff = create_user(db, tenant, Role.STAFF)
    create_user(db, tenant, Role.VIEWER)
    inactive = create_user(db, tenant, Role.ANALYST)
    inactive.is_active = False
    create_user(db, other, Role.STAFF)
    db.commit()
    login(client, "staff@acme.example")

    response = client.get(_url(tenant.store.id, "/members"))

    assert response.status_code == 200
    items = response.json()["items"]
    assert items == [
        {
            "id": items[0]["id"],
            "full_name": "Manager User",
            "role": "MANAGER",
            "can_work_exceptions": True,
        },
        {
            "id": str(staff.id),
            "full_name": "Staff User",
            "role": "STAFF",
            "can_work_exceptions": True,
        },
        {
            "id": items[2]["id"],
            "full_name": "Viewer User",
            "role": "VIEWER",
            "can_work_exceptions": False,
        },
    ]
    assert "acme.example" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "permission"),
    [
        ("GET", "", Permission.DASHBOARD_READ),
        ("GET", "/settings", Permission.SETTINGS_READ),
        ("GET", "/members", Permission.EXCEPTIONS_READ),
    ],
)
def test_store_reads_require_their_permission(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    permission: Permission,
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.VIEWER)
    login(client, "viewer@acme.example")
    strip_permission(monkeypatch, permission)

    response = client.request(method, _url(tenant.store.id, path))

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": permission.value}]


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", ""), ("GET", "/settings"), ("PATCH", "/settings"), ("GET", "/members")],
)
def test_other_tenants_store_routes_are_not_found(
    client: TestClient, db: Session, method: str, path: str
) -> None:
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    create_user(db, acme, Role.OWNER)
    csrf = login(client, "owner@acme.example")

    response = client.request(
        method,
        _url(globex.store.id, path),
        json={"fulfillment_sla_hours": 24} if method == "PATCH" else None,
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    db.expire_all()
    assert all(s.fulfillment_sla_hours == 48 for s in db.scalars(select(StoreSettings)))
