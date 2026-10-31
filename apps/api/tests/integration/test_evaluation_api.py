"""Evaluation run API: manual trigger, idempotency, lock contention, history (T-053, ADR-0009)."""

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.domains.audit.models import AuditLog
from app.domains.exceptions.engine import EVALUATION_LOCK_NAMESPACE, advisory_lock_key
from app.domains.exceptions.models import EvaluationRun, OperationalException
from app.domains.identity import permissions
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission, Role
from tests.factories import Tenant, create_tenant, create_user
from tests.factories_exceptions import T0, evaluate, make_product, user_client

pytestmark = pytest.mark.integration


@pytest.fixture
def tenant(db: Session) -> Tenant:
    tenant = create_tenant(db, "acme")
    make_product(db, tenant, "A-1", reorder_point=0)  # out of stock: one finding
    db.commit()
    return tenant


@pytest.fixture
def manager(db: Session, tenant: Tenant) -> User:
    return create_user(db, tenant, Role.MANAGER)


def _url(tenant: Tenant) -> str:
    return f"/api/v1/stores/{tenant.store.id}/evaluations"


def test_manager_triggers_a_manual_run(
    app: FastAPI, db: Session, tenant: Tenant, manager: User
) -> None:
    client, csrf = user_client(app, manager.email)

    response = client.post(_url(tenant), headers=csrf)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["trigger"] == "MANUAL"
    assert body["status"] == "SUCCEEDED"
    assert body["counts"]["created"] == 1
    assert len(body["rules"]) == 9
    assert body["triggered_by"] == {"id": str(manager.id), "full_name": "Manager User"}
    assert body["finished_at"] is not None
    assert db.scalars(select(OperationalException.reference)).all() == ["EXC-1001"]
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "evaluation.run")).one()
    assert entry.target_id == body["id"]
    assert entry.details["counts"]["created"] == 1


def test_rule_subset_and_unknown_rules(app: FastAPI, tenant: Tenant, manager: User) -> None:
    client, csrf = user_client(app, manager.email)

    subset = client.post(_url(tenant), json={"rule_ids": ["ORD-OVERDUE@1"]}, headers=csrf)
    assert subset.status_code == 201
    assert subset.json()["rules"] == ["ORD-OVERDUE@1"]
    assert subset.json()["counts"]["created"] == 0

    unknown = client.post(_url(tenant), json={"rule_ids": ["NOPE@1"]}, headers=csrf)
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "UNKNOWN_RULE"


def test_idempotency_key_replays_the_original_run(
    app: FastAPI, db: Session, tenant: Tenant, manager: User
) -> None:
    client, csrf = user_client(app, manager.email)
    headers = {**csrf, "Idempotency-Key": "run-2026-11-02T08:15"}

    first = client.post(_url(tenant), headers=headers)
    second = client.post(_url(tenant), headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json()["id"] == first.json()["id"]
    assert len(db.scalars(select(EvaluationRun.id)).all()) == 1

    other_key = client.post(_url(tenant), headers={**csrf, "Idempotency-Key": "another-key"})
    assert other_key.status_code == 201
    assert other_key.json()["id"] != first.json()["id"]

    bad = client.post(_url(tenant), headers={**csrf, "Idempotency-Key": "spaces are bad"})
    assert bad.status_code == 422


def test_manual_run_while_the_store_lock_is_held_returns_the_skipped_run(
    app: FastAPI, engine: Engine, tenant: Tenant, manager: User
) -> None:
    client, csrf = user_client(app, manager.email)
    headers = {**csrf, "Idempotency-Key": "double-click"}
    with engine.connect() as other, other.begin():
        other.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:ns AS integer), CAST(:key AS integer))"),
            {"ns": EVALUATION_LOCK_NAMESPACE, "key": advisory_lock_key(tenant.store.id)},
        )
        skipped = client.post(_url(tenant), headers=headers)

    assert skipped.status_code == 200
    assert skipped.json()["status"] == "SKIPPED"
    assert skipped.json()["error"] == "Another evaluation is running for this store."
    # A skipped run does not consume the idempotency key: the retry runs.
    retry = client.post(_url(tenant), headers=headers)
    assert retry.status_code == 201
    assert retry.json()["status"] == "SUCCEEDED"


@pytest.mark.parametrize("role", [Role.STAFF, Role.ANALYST, Role.VIEWER])
def test_trigger_requires_evaluations_run(
    app: FastAPI, db: Session, tenant: Tenant, role: Role
) -> None:
    user = create_user(db, tenant, role)
    client, csrf = user_client(app, user.email)

    response = client.post(_url(tenant), headers=csrf)

    assert response.status_code == 403
    assert response.json()["error"]["details"] == [{"missing_permission": "evaluations.run"}]


def test_trigger_on_another_tenants_store_is_404(
    app: FastAPI, db: Session, tenant: Tenant, manager: User
) -> None:
    other = create_tenant(db, "zenith")
    client, csrf = user_client(app, manager.email)
    assert client.post(_url(other), headers=csrf).status_code == 404


def test_list_and_get_runs(app: FastAPI, db: Session, tenant: Tenant, manager: User) -> None:
    viewer = create_user(db, tenant, Role.VIEWER)
    evaluate(db, tenant, T0)
    manual_client, csrf = user_client(app, manager.email)
    manual = manual_client.post(_url(tenant), headers=csrf).json()
    client, _ = user_client(app, viewer.email)

    listed = client.get(_url(tenant))

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 2
    assert body["items"][0]["id"] == manual["id"]  # newest first
    assert [i["trigger"] for i in body["items"]] == ["MANUAL", "SCHEDULED"]
    filtered = client.get(_url(tenant), params={"trigger": "SCHEDULED"}).json()
    assert [i["trigger"] for i in filtered["items"]] == ["SCHEDULED"]
    assert client.get(_url(tenant), params={"sort": "duration_ms"}).status_code == 422

    one = client.get(f"{_url(tenant)}/{manual['id']}")
    assert one.status_code == 200
    assert one.json() == manual
    assert client.get(f"{_url(tenant)}/{uuid.uuid4()}").status_code == 404


def test_runs_are_tenant_scoped(app: FastAPI, db: Session, tenant: Tenant, manager: User) -> None:
    other = create_tenant(db, "zenith")
    foreign_run = evaluate(db, other, T0)
    client, _ = user_client(app, manager.email)

    assert client.get(_url(other)).status_code == 404
    assert client.get(f"{_url(other)}/{foreign_run.id}").status_code == 404
    assert client.get(f"{_url(tenant)}/{foreign_run.id}").status_code == 404
    assert client.get(_url(tenant)).json()["total"] == 0


def test_run_history_requires_exceptions_read(
    app: FastAPI, db: Session, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    viewer = create_user(db, tenant, Role.VIEWER)
    run = evaluate(db, tenant, T0)
    monkeypatch.setitem(
        permissions.ROLE_PERMISSIONS,
        Role.VIEWER,
        permissions.ROLE_PERMISSIONS[Role.VIEWER] - {Permission.EXCEPTIONS_READ},
    )
    client, _ = user_client(app, viewer.email)

    for url in (_url(tenant), f"{_url(tenant)}/{run.id}"):
        response = client.get(url)
        assert response.status_code == 403
        assert response.json()["error"]["details"] == [{"missing_permission": "exceptions.read"}]
