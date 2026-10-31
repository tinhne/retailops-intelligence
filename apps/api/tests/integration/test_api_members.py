"""Organization member administration (ROLE_AND_PERMISSION_WORKFLOW.md §8, API_CONVENTIONS §12.1).

Covers the permission matrix (users.read / users.manage), tenancy (404 for other organizations),
the last-owner guard (U1), session revocation on deactivation (§8.3) and the audit rows (§11).
"""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.audit.models import AuditLog
from app.domains.identity.models import Membership, User, UserSession
from app.domains.identity.permissions import Role
from tests.factories import Tenant, create_tenant, create_user, login, pre_session_csrf

pytestmark = pytest.mark.integration


def _members(org_id: Any, path: str = "") -> str:
    return f"/api/v1/organizations/{org_id}/members{path}"


def _membership_id(db: Session, user: User) -> uuid.UUID:
    membership_id = db.scalar(select(Membership.id).where(Membership.user_id == user.id))
    assert membership_id is not None
    return membership_id


def _audit(db: Session, action: str) -> list[AuditLog]:
    db.expire_all()
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


def _owner_session(client: TestClient, db: Session, tenant: Tenant) -> tuple[User, str]:
    owner = create_user(db, tenant, Role.OWNER)
    return owner, login(client, f"owner@{tenant.organization.slug}.example")


# --- listing --------------------------------------------------------------------------------


def test_owner_lists_members_with_email_role_and_status(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    owner, _ = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)
    staff.is_active = False
    db.commit()

    response = client.get(_members(tenant.organization.id))

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [m["full_name"] for m in items] == ["Owner User", "Staff User"]
    by_email = {m["email"]: m for m in items}
    assert by_email["owner@acme.example"]["role"] == "OWNER"
    assert by_email["owner@acme.example"]["status"] == "ACTIVE"
    assert by_email["owner@acme.example"]["user_id"] == str(owner.id)
    assert by_email["owner@acme.example"]["last_login_at"] is not None
    assert by_email["staff@acme.example"]["status"] == "DEACTIVATED"
    assert by_email["staff@acme.example"]["id"] == str(_membership_id(db, staff))
    assert set(items[0]) == {
        "id",
        "user_id",
        "full_name",
        "email",
        "role",
        "status",
        "joined_at",
        "last_login_at",
    }


def test_manager_reads_members_but_cannot_manage_them(client: TestClient, db: Session) -> None:
    """U6: MANAGER has users.read but not users.manage."""
    tenant = create_tenant(db)
    create_user(db, tenant, Role.MANAGER)
    staff = create_user(db, tenant, Role.STAFF)
    csrf = login(client, "manager@acme.example")
    headers = {"X-CSRF-Token": csrf}

    listed = client.get(_members(tenant.organization.id))
    created = client.post(
        _members(tenant.organization.id),
        json={"email": "new@acme.example", "full_name": "New Person", "role": "STAFF"},
        headers=headers,
    )
    patched = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, staff)}"),
        json={"role": "ANALYST"},
        headers=headers,
    )

    assert listed.status_code == 200
    for response in (created, patched):
        assert response.status_code == 403
        assert response.json()["error"]["details"] == [{"missing_permission": "users.manage"}]


@pytest.mark.parametrize("role", [Role.STAFF, Role.ANALYST, Role.VIEWER])
def test_roles_without_users_read_are_forbidden(
    client: TestClient, db: Session, role: Role
) -> None:
    tenant = create_tenant(db)
    create_user(db, tenant, role)
    login(client, f"{role.value.lower()}@acme.example")

    response = client.get(_members(tenant.organization.id))

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "users.read"}]


def test_requires_authentication_and_csrf(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    assert client.get(_members(tenant.organization.id)).status_code == 401
    _owner_session(client, db, tenant)

    response = client.post(
        _members(tenant.organization.id),
        json={"email": "new@acme.example", "full_name": "New Person", "role": "STAFF"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
    assert db.scalar(select(User).where(User.email == "new@acme.example")) is None


# --- tenancy --------------------------------------------------------------------------------


def test_other_organizations_members_are_not_found(client: TestClient, db: Session) -> None:
    """BR-003: another tenant's organization and memberships answer 404, never 403."""
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    _, csrf = _owner_session(client, db, acme)
    globex_staff = create_user(db, globex, Role.STAFF)
    headers = {"X-CSRF-Token": csrf}
    foreign_membership = _membership_id(db, globex_staff)

    responses = [
        client.get(_members(globex.organization.id)),
        client.get(_members(uuid.uuid4())),
        client.post(
            _members(globex.organization.id),
            json={"email": "x@globex.example", "full_name": "X", "role": "STAFF"},
            headers=headers,
        ),
        client.patch(
            _members(globex.organization.id, f"/{foreign_membership}"),
            json={"role": "OWNER"},
            headers=headers,
        ),
        # Own organization in the path, another tenant's membership id.
        client.patch(
            _members(acme.organization.id, f"/{foreign_membership}"),
            json={"status": "DEACTIVATED"},
            headers=headers,
        ),
    ]

    for response in responses:
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "NOT_FOUND"
    db.expire_all()
    assert db.get(Membership, foreign_membership).role is Role.STAFF
    assert db.get(User, globex_staff.id).is_active is True
    assert db.scalar(select(User).where(User.email == "x@globex.example")) is None


# --- adding a member ------------------------------------------------------------------------


def test_owner_adds_member_with_one_time_temporary_password(
    client: TestClient, app: FastAPI, db: Session
) -> None:
    """§8.1: the account is created with a random temporary password, shown once, never audited."""
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)

    response = client.post(
        _members(tenant.organization.id),
        json={"email": "  Sam.Ortiz@Acme.EXAMPLE ", "full_name": "  Sam Ortiz ", "role": "STAFF"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    member = body["member"]
    assert member["email"] == "sam.ortiz@acme.example"
    assert member["full_name"] == "Sam Ortiz"
    assert (member["role"], member["status"]) == ("STAFF", "ACTIVE")
    assert member["last_login_at"] is None
    password = body["temporary_password"]
    assert len(password) >= 16
    stored = db.scalar(select(User).where(User.email == "sam.ortiz@acme.example"))
    assert stored is not None
    assert password not in stored.password_hash  # only the argon2id hash is stored

    [entry] = _audit(db, "user.create")
    assert entry.organization_id == tenant.organization.id
    assert entry.store_id is None
    assert entry.actor_user_id == owner.id
    assert (entry.target_type, entry.target_id) == ("user", str(stored.id))
    assert entry.details == {
        "membership_id": member["id"],
        "full_name": "Sam Ortiz",
        "role": "STAFF",
    }
    assert password not in str(entry.details)

    # The new member can sign in with the temporary password.
    with TestClient(app) as other:
        signed_in = other.post(
            "/api/v1/auth/login",
            json={"email": "sam.ortiz@acme.example", "password": password},
            headers=pre_session_csrf(other),
        )
        assert signed_in.status_code == 200
        assert signed_in.json()["memberships"][0]["role"] == "STAFF"


def test_adding_an_existing_email_is_refused(client: TestClient, db: Session) -> None:
    """O-35 is open: existing accounts are never attached or modified."""
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    _, csrf = _owner_session(client, db, acme)
    create_user(db, acme, Role.STAFF)
    outsider = create_user(db, globex, Role.STAFF)
    headers = {"X-CSRF-Token": csrf}

    same_org = client.post(
        _members(acme.organization.id),
        json={"email": "STAFF@acme.example", "full_name": "Again", "role": "MANAGER"},
        headers=headers,
    )
    other_org = client.post(
        _members(acme.organization.id),
        json={"email": "staff@globex.example", "full_name": "Borrowed", "role": "MANAGER"},
        headers=headers,
    )

    assert same_org.status_code == 409
    assert same_org.json()["error"]["code"] == "MEMBER_EXISTS"
    assert other_org.status_code == 409
    assert other_org.json()["error"]["code"] == "EMAIL_IN_USE"
    db.expire_all()
    outsider_orgs = db.scalars(
        select(Membership.organization_id).where(Membership.user_id == outsider.id)
    ).all()
    assert outsider_orgs == [globex.organization.id]
    assert db.get(User, outsider.id).full_name == "Staff User"
    assert _audit(db, "user.create") == []


@pytest.mark.parametrize(
    "body",
    [
        {"email": "not-an-email", "full_name": "X", "role": "STAFF"},
        {"email": "x@acme.example", "full_name": "   ", "role": "STAFF"},
        {"email": "x@acme.example", "full_name": "X", "role": "ADMIN"},
        {"email": "x@acme.example", "full_name": "X"},
        {"email": "x@acme.example", "full_name": "X", "role": "STAFF", "password": "chosen"},
    ],
)
def test_add_member_validation(client: TestClient, db: Session, body: dict[str, Any]) -> None:
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)

    response = client.post(
        _members(tenant.organization.id), json=body, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 422
    assert db.scalar(select(User).where(User.email == "x@acme.example")) is None


# --- changing a role ------------------------------------------------------------------------


def test_owner_changes_role_effective_on_next_request(
    client: TestClient, app: FastAPI, db: Session
) -> None:
    """§8.2: the role changes, sessions are kept, and the next request uses the new role."""
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)
    membership_id = _membership_id(db, staff)

    with TestClient(app) as staff_client:
        login(staff_client, "staff@acme.example")
        assert staff_client.get(_members(tenant.organization.id)).status_code == 403

        response = client.patch(
            _members(tenant.organization.id, f"/{membership_id}"),
            json={"role": "MANAGER"},
            headers={"X-CSRF-Token": csrf},
        )

        assert response.status_code == 200, response.text
        assert response.json()["role"] == "MANAGER"
        assert response.json()["status"] == "ACTIVE"
        assert staff_client.get(_members(tenant.organization.id)).status_code == 200

    [entry] = _audit(db, "user.role_change")
    assert entry.actor_user_id == owner.id
    assert entry.target_id == str(staff.id)
    assert entry.details == {
        "membership_id": str(membership_id),
        "full_name": "Staff User",
        "from_role": "STAFF",
        "to_role": "MANAGER",
    }
    assert _audit(db, "auth.session_revoked") == []


def test_unchanged_values_are_a_no_op_without_audit(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, staff)}"),
        json={"role": "STAFF", "status": "ACTIVE"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "STAFF"
    assert _audit(db, "user.role_change") == []


@pytest.mark.parametrize(
    "body",
    [{}, {"role": None}, {"status": None}, {"role": "ADMIN"}, {"status": "SUSPENDED"}, {"x": 1}],
)
def test_update_member_validation(client: TestClient, db: Session, body: dict[str, Any]) -> None:
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, staff)}"),
        json=body,
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422


def test_last_owner_cannot_demote_or_deactivate_themselves(client: TestClient, db: Session) -> None:
    """U1: refused with 409 LAST_OWNER (state check before the own-membership rule)."""
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)
    path = _members(tenant.organization.id, f"/{_membership_id(db, owner)}")

    demote = client.patch(path, json={"role": "MANAGER"}, headers={"X-CSRF-Token": csrf})
    deactivate = client.patch(path, json={"status": "DEACTIVATED"}, headers={"X-CSRF-Token": csrf})

    for response in (demote, deactivate):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LAST_OWNER"
    db.expire_all()
    assert db.get(Membership, _membership_id(db, owner)).role is Role.OWNER
    assert db.get(User, owner.id).is_active is True


def test_a_deactivated_owner_does_not_count_as_another_owner(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)
    dormant = create_user(db, tenant, Role.OWNER, email="dormant-owner@acme.example")
    dormant.is_active = False
    db.commit()

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, owner)}"),
        json={"role": "MANAGER"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_OWNER"


def test_another_owner_can_be_demoted_while_one_owner_remains(
    client: TestClient, db: Session
) -> None:
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)
    second = create_user(db, tenant, Role.OWNER, email="second-owner@acme.example")

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, second)}"),
        json={"role": "MANAGER", "status": "DEACTIVATED"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    assert (response.json()["role"], response.json()["status"]) == ("MANAGER", "DEACTIVATED")


def test_members_cannot_change_their_own_membership(client: TestClient, db: Session) -> None:
    """MVP assumption (§8.2): an owner cannot change their own role, even with another owner."""
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)
    create_user(db, tenant, Role.OWNER, email="second-owner@acme.example")

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, owner)}"),
        json={"role": "MANAGER"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "OWN_MEMBERSHIP"
    assert _audit(db, "user.role_change") == []


# --- deactivation ---------------------------------------------------------------------------


def test_deactivation_revokes_sessions_and_reactivation_restores_sign_in(
    client: TestClient, app: FastAPI, db: Session
) -> None:
    """§8.3: all sessions revoked at once, the next request gets 401, sign-in is refused."""
    tenant = create_tenant(db)
    owner, csrf = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)
    membership_id = _membership_id(db, staff)
    path = _members(tenant.organization.id, f"/{membership_id}")
    store_path = f"/api/v1/stores/{tenant.store.id}"

    with TestClient(app) as staff_client, TestClient(app) as staff_phone:
        login(staff_client, "staff@acme.example")
        login(staff_phone, "staff@acme.example")
        assert staff_client.get(store_path).status_code == 200

        response = client.patch(
            path, json={"status": "DEACTIVATED"}, headers={"X-CSRF-Token": csrf}
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "DEACTIVATED"
        assert staff_client.get(store_path).status_code == 401
        assert staff_phone.get(store_path).status_code == 401
        refused = staff_client.post(
            "/api/v1/auth/login",
            json={"email": "staff@acme.example", "password": "correct-horse-battery-staple"},
            headers=pre_session_csrf(staff_client),
        )
        assert refused.status_code == 401

    db.expire_all()
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == staff.id)).all()
    assert len(sessions) == 2
    assert all(s.revoked_at is not None for s in sessions)
    [deactivated] = _audit(db, "user.deactivate")
    assert deactivated.actor_user_id == owner.id
    assert deactivated.details == {
        "membership_id": str(membership_id),
        "full_name": "Staff User",
        "sessions_revoked": 2,
    }
    [revoked] = _audit(db, "auth.session_revoked")
    assert revoked.details["cause"] == "user.deactivate"
    # Deactivated members stay listed (their history keeps their name).
    listed = client.get(_members(tenant.organization.id)).json()["items"]
    assert {m["email"]: m["status"] for m in listed}["staff@acme.example"] == "DEACTIVATED"
    # ...but are no longer offered as assignees.
    picker = client.get(f"{store_path}/members").json()["items"]
    assert str(staff.id) not in {m["id"] for m in picker}

    reactivated = client.patch(path, json={"status": "ACTIVE"}, headers={"X-CSRF-Token": csrf})

    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "ACTIVE"
    assert len(_audit(db, "user.reactivate")) == 1
    with TestClient(app) as staff_client:
        login(staff_client, "staff@acme.example")


def test_role_change_and_deactivation_in_one_request(client: TestClient, db: Session) -> None:
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)
    manager = create_user(db, tenant, Role.MANAGER)

    response = client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, manager)}"),
        json={"role": "ANALYST", "status": "DEACTIVATED"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200
    assert (response.json()["role"], response.json()["status"]) == ("ANALYST", "DEACTIVATED")
    assert len(_audit(db, "user.role_change")) == 1
    assert _audit(db, "user.deactivate")[0].details["sessions_revoked"] == 0
    assert _audit(db, "auth.session_revoked") == []  # no live session to revoke


def test_account_shared_with_another_organization_cannot_be_deactivated(
    client: TestClient, db: Session
) -> None:
    """``is_active`` is per account, so it must not be switched off from one tenant only."""
    acme = create_tenant(db, "acme")
    globex = create_tenant(db, "globex")
    _, csrf = _owner_session(client, db, acme)
    shared = create_user(db, acme, Role.STAFF)
    db.add(Membership(user_id=shared.id, organization_id=globex.organization.id, role=Role.OWNER))
    db.commit()

    response = client.patch(
        _members(acme.organization.id, f"/{_membership_id_in(db, shared, acme)}"),
        json={"status": "DEACTIVATED"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MEMBER_IN_OTHER_ORGANIZATION"
    db.expire_all()
    assert db.get(User, shared.id).is_active is True


def _membership_id_in(db: Session, user: User, tenant: Tenant) -> uuid.UUID:
    membership_id = db.scalar(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.organization_id == tenant.organization.id
        )
    )
    assert membership_id is not None
    return membership_id


# --- audit log view -------------------------------------------------------------------------


def test_member_changes_appear_in_the_store_audit_log_with_actor_names(
    client: TestClient, db: Session
) -> None:
    """Organization-level rows (store_id NULL) show in every store of the organization."""
    tenant = create_tenant(db)
    _, csrf = _owner_session(client, db, tenant)
    staff = create_user(db, tenant, Role.STAFF)
    client.patch(
        _members(tenant.organization.id, f"/{_membership_id(db, staff)}"),
        json={"role": "ANALYST"},
        headers={"X-CSRF-Token": csrf},
    )

    response = client.get(
        f"/api/v1/stores/{tenant.store.id}/audit-logs", params={"action": "user."}
    )

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["action"] == "user.role_change"
    assert item["actor_name"] == "Owner User"
    assert item["store_id"] is None
    assert item["details"]["to_role"] == "ANALYST"
