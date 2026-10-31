"""Authentication, sessions, CSRF, permissions and tenant isolation (SECURITY_ARCHITECTURE.md)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.domains.audit.models import AuditLog
from app.domains.identity.models import UserSession
from app.domains.identity.permissions import Role
from tests.factories import create_tenant, create_user, login

pytestmark = pytest.mark.integration


def test_login_sets_httponly_session_cookie_and_returns_profile(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.MANAGER, email="Manager@Acme.example")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  manager@acme.EXAMPLE ", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "manager@acme.example"
    membership = body["memberships"][0]
    assert membership["role"] == "MANAGER"
    assert "users.manage" not in membership["permissions"]
    assert membership["stores"][0]["id"] == str(tenant.store.id)
    set_cookie = ";".join(response.headers.get_list("set-cookie")).lower()
    assert "ro_session=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    stored = db.scalars(select(UserSession)).one()
    assert client.cookies.get("ro_session") != stored.token_hash  # only the hash is stored


def test_invalid_credentials_are_generic_and_audited(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.STAFF)

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "staff@acme.example", "password": "nope"}
    )
    unknown_user = client.post(
        "/api/v1/auth/login", json={"email": "ghost@acme.example", "password": "nope"}
    )

    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    actions = db.scalars(select(AuditLog.action)).all()
    assert actions.count("auth.login_failed") == 2


def test_login_is_rate_limited_per_ip_and_email(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.STAFF)
    payload = {"email": "staff@acme.example", "password": "wrong"}

    statuses = [client.post("/api/v1/auth/login", json=payload).status_code for _ in range(6)]

    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_mutating_request_without_csrf_header_is_rejected(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.OWNER)
    csrf = login(client, "owner@acme.example")

    rejected = client.post("/api/v1/auth/logout")
    forged = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"})
    accepted = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_FAILED"
    assert forged.status_code == 403
    assert accepted.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401  # session revoked server-side


def test_idle_session_expires(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.STAFF)
    login(client, "staff@acme.example")
    session = db.scalars(select(UserSession)).one()
    session.last_seen_at = utcnow() - timedelta(hours=13)
    db.commit()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_permission_denied_returns_403_with_missing_permission(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, Role.STAFF)
    login(client, "staff@acme.example")

    response = client.get(f"/api/v1/stores/{tenant.store.id}/audit-logs")

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "audit.read"}]


def test_other_tenants_store_is_not_found_not_forbidden(client: TestClient, db: Session) -> None:
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    create_user(db, acme, Role.OWNER)
    create_user(db, globex, Role.OWNER)
    login(client, "owner@acme.example")

    own = client.get(f"/api/v1/stores/{acme.store.id}/audit-logs")
    foreign = client.get(f"/api/v1/stores/{globex.store.id}/audit-logs")

    assert own.status_code == 200
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "NOT_FOUND"


def test_audit_log_lists_only_own_organization_events(client: TestClient, db: Session) -> None:
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    create_user(db, acme, Role.ANALYST)
    create_user(db, globex, Role.OWNER)
    login(client, "owner@globex.example")
    client.cookies.clear()
    login(client, "analyst@acme.example")

    response = client.get(f"/api/v1/stores/{acme.store.id}/audit-logs", params={"action": "auth."})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "auth.login"
    assert body["page"] == 1
    assert body["page_size"] == 25


def test_demo_login_signs_in_read_only_viewer(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db, "kestrel", is_demo=True)
    create_user(db, tenant, Role.VIEWER, email="demo@kestrel.example")

    response = client.post("/api/v1/auth/demo")

    assert response.status_code == 200
    membership = response.json()["memberships"][0]
    assert membership["role"] == "VIEWER"
    assert membership["is_demo"] is True
    assert "exceptions.work" not in membership["permissions"]


def test_demo_login_refuses_account_with_mutating_role(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db, "kestrel", is_demo=True)
    create_user(db, tenant, Role.MANAGER, email="demo@kestrel.example")

    response = client.post("/api/v1/auth/demo")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEMO_MISCONFIGURED"


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
