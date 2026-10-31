"""Exceptions API: listing, detail, history, lifecycle actions, permissions and tenancy
(STATE_MACHINES.md §3.2, T-054). Every endpoint has a permission-denied and a cross-tenant test."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.domains.audit.models import AuditLog
from app.domains.exceptions.models import (
    ExceptionAssignment,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionType,
    OperationalException,
)
from app.domains.identity import permissions
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission, Role
from app.domains.orders.models import OrderStatus
from tests.factories import Tenant, create_tenant, create_user
from tests.factories_exceptions import (
    LineSpec,
    OrderSpec,
    evaluate,
    make_order,
    make_product,
    set_stock,
    user_client,
)

pytestmark = pytest.mark.integration
H = timedelta(hours=1)
# Evaluations run in the recent past so that user actions (stamped with the real clock) follow
# the system events in the history.
T0 = utcnow().replace(microsecond=0) - 2 * H


@dataclass
class World:
    app: FastAPI
    tenant: Tenant
    other: Tenant
    manager: User
    staff: User
    staff2: User
    viewer: User
    analyst: User
    oversold_id: uuid.UUID
    overdue_id: uuid.UUID
    oos_id: uuid.UUID
    other_exception_id: uuid.UUID
    product_id: uuid.UUID
    order_id: uuid.UUID

    def base(self, tenant: Tenant | None = None) -> str:
        return f"/api/v1/stores/{(tenant or self.tenant).store.id}"

    def client(self, user: User) -> tuple[TestClient, dict[str, str]]:
        return user_client(self.app, user.email)


@pytest.fixture
def world(db: Session, app: FastAPI) -> World:
    tenant = create_tenant(db, "acme")
    other = create_tenant(db, "zenith")
    manager = create_user(db, tenant, Role.MANAGER)
    staff = create_user(db, tenant, Role.STAFF)
    staff2 = create_user(db, tenant, Role.STAFF, email="staff2@acme.example")
    viewer = create_user(db, tenant, Role.VIEWER)
    analyst = create_user(db, tenant, Role.ANALYST)

    mug = make_product(db, tenant, "KH-MUG-01", reorder_point=0, name="Stoneware Mug 100%")
    set_stock(db, tenant, mug, 1, T0 - 10 * H)
    make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-1001",
            OrderStatus.PAID,
            [LineSpec(mug, 1)],
            placed_at=T0 - 4 * H,
            paid_at=T0 - 3 * H,
            ship_by=T0 + 9 * H,
        ),
    )
    short = make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-1002",
            OrderStatus.PAID,
            [LineSpec(mug, 2)],
            placed_at=T0 - 4 * H,
            paid_at=T0 - 2 * H,
            ship_by=T0 + 9 * H,
        ),
    )
    bowl = make_product(db, tenant, "KH-BOWL-01", reorder_point=0)
    set_stock(db, tenant, bowl, 40, T0 - 10 * H)
    make_order(
        db,
        tenant,
        OrderSpec(
            "KHK-0999",
            OrderStatus.PROCESSING,
            [LineSpec(bowl, 1, "120.00")],
            placed_at=T0 - 81 * H,
            paid_at=T0 - 80 * H,
            ship_by=T0 - 30 * H,
        ),
    )
    make_product(db, tenant, "KH-JUG-01", reorder_point=0)  # out of stock, not selling
    evaluate(db, tenant, T0)

    make_product(db, other, "Z-1", reorder_point=0)
    evaluate(db, other, T0)

    def find(t: Tenant, exception_type: ExceptionType) -> uuid.UUID:
        return db.scalars(
            select(OperationalException.id).where(
                OperationalException.store_id == t.store.id,
                OperationalException.exception_type == exception_type,
            )
        ).one()

    return World(
        app=app,
        tenant=tenant,
        other=other,
        manager=manager,
        staff=staff,
        staff2=staff2,
        viewer=viewer,
        analyst=analyst,
        oversold_id=find(tenant, ExceptionType.INVENTORY_OVERSOLD),
        overdue_id=find(tenant, ExceptionType.ORDER_FULFILLMENT_OVERDUE),
        oos_id=find(tenant, ExceptionType.INVENTORY_OUT_OF_STOCK),
        other_exception_id=find(other, ExceptionType.INVENTORY_OUT_OF_STOCK),
        product_id=mug.id,
        order_id=short.id,
    )


def _audit_actions(db: Session, target: uuid.UUID) -> list[str]:
    db.expire_all()
    return list(
        db.scalars(
            select(AuditLog.action)
            .where(AuditLog.target_id == str(target))
            .order_by(AuditLog.occurred_at)
        ).all()
    )


def _events(db: Session, exception_id: uuid.UUID) -> list[ExceptionEventType]:
    db.expire_all()
    return list(
        db.scalars(
            select(ExceptionEvent.event_type)
            .where(ExceptionEvent.exception_id == exception_id)
            .order_by(ExceptionEvent.occurred_at)
        ).all()
    )


# --- list --------------------------------------------------------------------------------------


def test_list_defaults_to_active_sorted_by_priority(world: World) -> None:
    client, _ = world.client(world.viewer)

    response = client.get(f"{world.base()}/exceptions")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 1
    scores = [item["priority_score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)
    first = body["items"][0]
    assert first["reference"].startswith("EXC-")
    assert first["primary_entity"]["type"] in {"product", "order"}
    oversold = next(i for i in body["items"] if i["exception_type"] == "INVENTORY_OVERSOLD")
    assert oversold["primary_entity"] == {
        "type": "product",
        "id": str(world.product_id),
        "label": "KH-MUG-01",
        "name": "Stoneware Mug 100%",
    }
    assert oversold["exposure_amount"] == "40.00"
    assert oversold["assignee"] is None
    assert isinstance(oversold["age_hours"], int)


def test_list_filters(world: World, db: Session) -> None:
    client, _ = world.client(world.manager)
    url = f"{world.base()}/exceptions"

    def refs(**params: object) -> set[str]:
        response = client.get(url, params=params)
        assert response.status_code == 200, response.text
        return {item["exception_type"] for item in response.json()["items"]}

    assert refs(severity="CRITICAL") == {"INVENTORY_OVERSOLD"}
    assert refs(severity=["HIGH", "MEDIUM"]) == {
        "ORDER_FULFILLMENT_OVERDUE",  # 30 h overdue
        "INVENTORY_OUT_OF_STOCK",  # not selling
    }
    assert refs(exception_type="INVENTORY_OUT_OF_STOCK") == {"INVENTORY_OUT_OF_STOCK"}
    assert refs(category="FULFILLMENT") == {"ORDER_FULFILLMENT_OVERDUE"}
    assert refs(priority_band="P4") == {"INVENTORY_OUT_OF_STOCK"}
    assert refs(product_id=str(world.product_id)) == {"INVENTORY_OVERSOLD"}
    assert refs(order_id=str(world.order_id)) == {"INVENTORY_OVERSOLD"}  # via AFFECTED link
    assert refs(status="RESOLVED") == set()
    assert refs(assignee="unassigned") == {
        "INVENTORY_OVERSOLD",
        "ORDER_FULFILLMENT_OVERDUE",
        "INVENTORY_OUT_OF_STOCK",
    }
    assert refs(assignee="me") == set()
    oversold = db.get(OperationalException, world.oversold_id)
    assert oversold is not None
    assert refs(q=oversold.reference.lower()) == {"INVENTORY_OVERSOLD"}
    assert refs(q="100%") == {"INVENTORY_OVERSOLD"}  # LIKE wildcards are escaped
    assert refs(q="_") == set()
    multi = client.get(url, params=[("status", "OPEN"), ("status", "RESOLVED")])
    assert multi.json()["total"] == 3


def test_list_due_to_filter(world: World) -> None:
    client, _ = world.client(world.manager)
    url = f"{world.base()}/exceptions"
    items = client.get(url).json()["items"]
    dues = sorted(item["due_at"] for item in items)
    cutoff = dues[0]  # inclusive: the earliest due exception matches, later ones do not
    filtered = client.get(url, params={"due_to": cutoff}).json()["items"]
    assert [item["due_at"] for item in filtered] == [d for d in dues if d <= cutoff]
    assert len(filtered) < len(items)

    naive = client.get(url, params={"due_to": "2026-11-01T12:00:00"})
    assert naive.status_code == 422
    assert naive.json()["error"]["code"] == "VALIDATION_FAILED"


def test_list_sorting_and_validation(world: World) -> None:
    client, _ = world.client(world.manager)
    url = f"{world.base()}/exceptions"

    due = client.get(url, params={"sort": "due_at"}).json()["items"]
    assert [i["due_at"] for i in due] == sorted(i["due_at"] for i in due)
    assert client.get(url, params={"sort": "-first_detected_at"}).status_code == 200
    assert client.get(url, params={"sort": "-last_detected_at"}).status_code == 200

    bad_sort = client.get(url, params={"sort": "title; DROP TABLE x"})
    assert bad_sort.status_code == 422
    assert bad_sort.json()["error"]["code"] == "INVALID_SORT"
    bad_assignee = client.get(url, params={"assignee": "someone"})
    assert bad_assignee.status_code == 422
    paged = client.get(url, params={"page": 2, "page_size": 2}).json()
    assert (paged["total"], len(paged["items"])) == (3, 1)


def test_list_requires_read_permission_and_is_tenant_scoped(world: World, db: Session) -> None:
    anonymous = TestClient(world.app)
    assert anonymous.get(f"{world.base()}/exceptions").status_code == 401
    client, _ = world.client(world.manager)
    response = client.get(f"{world.base(world.other)}/exceptions")
    assert response.status_code == 404


# --- detail, events, notes ------------------------------------------------------------------------


def test_detail_includes_evidence_breakdown_links_and_actions(world: World) -> None:
    client, _ = world.client(world.staff)

    response = client.get(f"{world.base()}/exceptions/{world.oversold_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["rule_id"] == "INV-OVERSOLD@1"
    assert body["evidence"]["facts"][0]["source"]["type"] == "inventory_balance"
    assert body["calculation"]["outputs"]["available"] == -2
    breakdown = body["priority_breakdown"]
    assert breakdown["total"] == body["priority_score"]
    assert {c["key"] for c in breakdown["components"]} == {
        "severity",
        "affected_orders",
        "exposure",
        "deadline",
        "age",
    }
    assert breakdown["due"]["basis"] in {"SEVERITY", "DEADLINE"}
    assert {(link["role"], link["label"]) for link in body["links"]} == {
        ("PRIMARY", "KH-MUG-01"),
        ("AFFECTED", "KHK-1002"),
    }
    assert body["available_actions"] == ["acknowledge", "start", "claim", "add_note"]
    blocked = {b["action"]: b["code"] for b in body["blocked_actions"]}
    assert blocked["resolve"] == "NOT_ASSIGNEE"
    assert blocked["dismiss"] == "PERMISSION_DENIED"
    assert body["resolution"] is None
    assert body["superseded_by"] is None
    assert body["previous_occurrence"] is None
    assert body["version"] == 1


def test_detail_actions_depend_on_role(world: World) -> None:
    viewer, _ = world.client(world.viewer)
    manager, _ = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oversold_id}"

    assert viewer.get(url).json()["available_actions"] == []
    assert manager.get(url).json()["available_actions"] == [
        "acknowledge",
        "start",
        "resolve",
        "dismiss",
        "assign",
        "claim",
        "add_note",
        "set_due_date",
    ]


def test_detail_events_and_notes_are_tenant_scoped(world: World) -> None:
    client, _ = world.client(world.manager)
    for suffix in ("", "/events", "/notes"):
        foreign = client.get(f"{world.base()}/exceptions/{world.other_exception_id}{suffix}")
        assert foreign.status_code == 404, suffix
        assert foreign.json()["error"]["code"] == "NOT_FOUND"
        other_store = client.get(f"{world.base(world.other)}/exceptions/{world.oos_id}{suffix}")
        assert other_store.status_code == 404
        missing = client.get(f"{world.base()}/exceptions/{uuid.uuid4()}{suffix}")
        assert missing.status_code == 404


def test_read_endpoints_need_authentication_and_exceptions_read(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    anonymous = TestClient(world.app)
    urls = [f"{world.base()}/exceptions"] + [
        f"{world.base()}/exceptions/{world.oversold_id}{suffix}"
        for suffix in ("", "/events", "/notes")
    ]
    for url in urls:
        assert anonymous.get(url).status_code == 401
    # Every role has exceptions.read; remove it from VIEWER to prove the check is enforced.
    monkeypatch.setitem(
        permissions.ROLE_PERMISSIONS,
        Role.VIEWER,
        permissions.ROLE_PERMISSIONS[Role.VIEWER] - {Permission.EXCEPTIONS_READ},
    )
    viewer, _ = world.client(world.viewer)
    for url in urls:
        response = viewer.get(url)
        assert response.status_code == 403, url
        assert response.json()["error"]["details"] == [{"missing_permission": "exceptions.read"}]


def test_events_list_history(world: World) -> None:
    client, csrf = world.client(world.staff)
    url = f"{world.base()}/exceptions/{world.oos_id}"
    client.post(f"{url}/start", headers=csrf)

    body = client.get(f"{url}/events").json()

    assert [e["event_type"] for e in body["items"]] == ["DETECTED", "ASSIGNED", "STATUS_CHANGED"]
    assert body["items"][0]["actor_type"] == "SYSTEM"
    assert body["items"][0]["evaluation_run_id"] is not None
    assert body["items"][2]["actor"] == {"id": str(world.staff.id), "full_name": "Staff User"}
    assert body["items"][2]["from_status"] == "OPEN"
    assert body["items"][2]["to_status"] == "IN_PROGRESS"


# --- acknowledge / start ------------------------------------------------------------------------


def test_acknowledge_by_staff_writes_event_audit_and_bumps_version(
    world: World, db: Session
) -> None:
    client, csrf = world.client(world.staff)

    response = client.post(
        f"{world.base()}/exceptions/{world.oversold_id}/acknowledge",
        json={"expected_version": 1},
        headers=csrf,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACKNOWLEDGED"
    assert response.json()["version"] == 2
    assert _events(db, world.oversold_id)[-1] is ExceptionEventType.STATUS_CHANGED
    assert _audit_actions(db, world.oversold_id) == ["exception.acknowledge"]

    again = client.post(f"{world.base()}/exceptions/{world.oversold_id}/acknowledge", headers=csrf)
    assert again.status_code == 409
    error = again.json()["error"]
    assert error["code"] == "EXCEPTION_TRANSITION_NOT_ALLOWED"
    assert error["details"][0]["allowed_transitions"] == ["IN_PROGRESS", "RESOLVED", "DISMISSED"]
    assert error["details"][0]["current_status"] == "ACKNOWLEDGED"


def test_stale_expected_version_is_rejected(world: World) -> None:
    staff, staff_csrf = world.client(world.staff)
    manager, manager_csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oversold_id}"
    assert manager.post(f"{url}/acknowledge", json={"expected_version": 1}, headers=manager_csrf)

    stale = staff.post(f"{url}/start", json={"expected_version": 1}, headers=staff_csrf)

    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "STALE_VERSION"
    assert error["details"] == [{"current_version": 2, "expected_version": 1}]


def test_viewer_and_analyst_cannot_mutate(world: World) -> None:
    url = f"{world.base()}/exceptions/{world.oversold_id}"
    for user in (world.viewer, world.analyst):
        client, csrf = world.client(user)
        for action, body in (
            ("acknowledge", None),
            ("start", None),
            ("resolve", {"resolution_code": "OTHER", "resolution_note": "Handled elsewhere."}),
            ("dismiss", {"dismissal_reason": "DUPLICATE", "note": "Duplicate of another one."}),
            ("reopen", {"reason": "Not fixed"}),
            ("notes", {"body": "hello"}),
            ("assign", {"assignee_id": str(user.id)}),
        ):
            response = client.post(f"{url}/{action}", json=body, headers=csrf)
            assert response.status_code == 403, (user.email, action)
            assert response.json()["error"]["code"] == "PERMISSION_DENIED"
        due = client.patch(
            f"{url}/due-date", json={"due_at": (T0 + 5 * H).isoformat()}, headers=csrf
        )
        assert due.status_code == 403


def test_mutations_on_another_tenants_exception_are_404(world: World) -> None:
    client, csrf = world.client(world.manager)
    for base in (world.base(), world.base(world.other)):
        exception_id = world.other_exception_id if base == world.base() else world.oos_id
        url = f"{base}/exceptions/{exception_id}"
        for action, body in (
            ("acknowledge", None),
            ("start", None),
            ("resolve", {"resolution_code": "OTHER", "resolution_note": "Handled elsewhere."}),
            ("dismiss", {"dismissal_reason": "DUPLICATE", "note": "Duplicate of another one."}),
            ("reopen", {"reason": "Not fixed"}),
            ("notes", {"body": "hello"}),
            ("assign", {"assignee_id": str(world.manager.id)}),
        ):
            assert client.post(f"{url}/{action}", json=body, headers=csrf).status_code == 404
        due = client.patch(
            f"{url}/due-date", json={"due_at": (T0 + 5 * H).isoformat()}, headers=csrf
        )
        assert due.status_code == 404


def test_start_unassigned_assigns_the_actor(world: World, db: Session) -> None:
    client, csrf = world.client(world.staff)

    response = client.post(f"{world.base()}/exceptions/{world.oos_id}/start", headers=csrf)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["assignee"] == {"id": str(world.staff.id), "full_name": "Staff User"}
    assert db.scalars(
        select(ExceptionAssignment.assignee_id).where(
            ExceptionAssignment.exception_id == world.oos_id
        )
    ).all() == [world.staff.id]
    assert _audit_actions(db, world.oos_id) == ["exception.start"]


def test_staff_cannot_start_someone_elses_exception_but_a_manager_keeps_the_assignee(
    world: World,
) -> None:
    staff, staff_csrf = world.client(world.staff)
    staff2, staff2_csrf = world.client(world.staff2)
    manager, manager_csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oos_id}"
    claim = staff.post(
        f"{url}/assign", json={"assignee_id": str(world.staff.id)}, headers=staff_csrf
    )
    assert claim.status_code == 200

    denied = staff2.post(f"{url}/start", headers=staff2_csrf)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "ASSIGNED_TO_ANOTHER_USER"

    started = manager.post(f"{url}/start", headers=manager_csrf)
    assert started.status_code == 200
    assert started.json()["assignee"]["id"] == str(world.staff.id)


# --- resolve / dismiss / reopen -------------------------------------------------------------------


def test_resolve_requires_assignee_and_valid_input(world: World, db: Session) -> None:
    staff, csrf = world.client(world.staff)
    url = f"{world.base()}/exceptions/{world.overdue_id}"
    body = {"resolution_code": "ORDER_FULFILLED", "resolution_note": "Picked up by carrier."}

    not_assignee = staff.post(f"{url}/resolve", json=body, headers=csrf)
    assert not_assignee.status_code == 403
    assert not_assignee.json()["error"]["code"] == "NOT_ASSIGNEE"

    assert staff.post(f"{url}/start", headers=csrf).status_code == 200
    short = staff.post(
        f"{url}/resolve",
        json={"resolution_code": "ORDER_FULFILLED", "resolution_note": "  done     "},
        headers=csrf,
    )
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "VALIDATION_FAILED"
    system_code = staff.post(
        f"{url}/resolve", json={**body, "resolution_code": "CONDITION_CLEARED"}, headers=csrf
    )
    assert system_code.status_code == 422

    resolved = staff.post(f"{url}/resolve", json=body, headers=csrf)

    assert resolved.status_code == 200, resolved.text
    out = resolved.json()
    assert out["status"] == "RESOLVED"
    assert out["resolution"]["resolution_code"] == "ORDER_FULFILLED"
    assert out["resolution"]["resolved_by"]["id"] == str(world.staff.id)
    assert out["resolution"]["resolution_actor"] == "USER"
    assert out["resolution"]["verified_at"] is None
    assert _audit_actions(db, world.overdue_id) == ["exception.start", "exception.resolve"]


def test_manager_resolves_any_exception(world: World) -> None:
    manager, csrf = world.client(world.manager)
    response = manager.post(
        f"{world.base()}/exceptions/{world.oos_id}/resolve",
        json={"resolution_code": "STOCK_REPLENISHED", "resolution_note": "Stock counted again."},
        headers=csrf,
    )
    assert response.status_code == 200


def test_closed_list_items_carry_resolution_form_and_closing_time(world: World) -> None:
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions"
    resolved = manager.post(
        f"{url}/{world.oos_id}/resolve",
        json={"resolution_code": "STOCK_REPLENISHED", "resolution_note": "Stock counted again."},
        headers=csrf,
    ).json()
    dismissed = manager.post(
        f"{url}/{world.overdue_id}/dismiss",
        json={"dismissal_reason": "DUPLICATE", "note": "Tracked in the carrier claim."},
        headers=csrf,
    ).json()

    closed = manager.get(url, params=[("status", "RESOLVED"), ("status", "DISMISSED")]).json()
    by_id = {item["id"]: item for item in closed["items"]}
    # A manual resolution stays unverified until the next evaluation (STATE_MACHINES §3.4).
    assert by_id[resolved["id"]]["resolution_code"] == "STOCK_REPLENISHED"
    assert by_id[resolved["id"]]["verified_at"] is None
    assert by_id[resolved["id"]]["closed_at"] == resolved["resolution"]["resolved_at"]
    assert by_id[dismissed["id"]]["dismissed_reason"] == "DUPLICATE"
    assert by_id[dismissed["id"]]["closed_at"] == dismissed["dismissal"]["dismissed_at"]
    assert by_id[dismissed["id"]]["resolution_code"] is None

    active = manager.get(url).json()["items"]
    assert all(item["closed_at"] is None and item["resolution_code"] is None for item in active)


def test_dismiss_and_reopen_need_manage_permission(world: World, db: Session) -> None:
    staff, staff_csrf = world.client(world.staff)
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oos_id}"
    dismissal = {"dismissal_reason": "ACCEPTED_RISK", "note": "Seasonal item, not restocked."}

    assert staff.post(f"{url}/dismiss", json=dismissal, headers=staff_csrf).status_code == 403
    short_note = manager.post(
        f"{url}/dismiss", json={"dismissal_reason": "ACCEPTED_RISK", "note": "meh"}, headers=csrf
    )
    assert short_note.status_code == 422
    no_reason = manager.post(f"{url}/dismiss", json={"note": dismissal["note"]}, headers=csrf)
    assert no_reason.status_code == 422

    dismissed = manager.post(f"{url}/dismiss", json=dismissal, headers=csrf)
    assert dismissed.status_code == 200
    out = dismissed.json()
    assert out["status"] == "DISMISSED"
    assert out["dismissal"]["dismissed_reason"] == "ACCEPTED_RISK"
    assert out["dismissal"]["note"] == "Seasonal item, not restocked."
    assert out["dismissal"]["dismissed_by"]["id"] == str(world.manager.id)
    assert out["available_actions"] == ["reopen", "add_note"]

    assert staff.post(f"{url}/reopen", json={"reason": "x"}, headers=staff_csrf).status_code == 403
    blank = manager.post(f"{url}/reopen", json={"reason": "   "}, headers=csrf)
    assert blank.status_code == 422
    reopened = manager.post(f"{url}/reopen", json={"reason": "Supplier found stock."}, headers=csrf)
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["status"] == "REOPENED"
    assert body["reopen_count"] == 1
    assert body["dismissal"] is None
    assert _audit_actions(db, world.oos_id) == ["exception.dismiss", "exception.reopen"]
    assert _events(db, world.oos_id)[-1] is ExceptionEventType.REOPENED


def test_reopen_rejected_when_a_newer_occurrence_is_active(world: World, db: Session) -> None:
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oos_id}"
    manager.post(
        f"{url}/dismiss",
        json={"dismissal_reason": "FALSE_POSITIVE", "note": "Count missing from export."},
        headers=csrf,
    )
    old = db.get(OperationalException, world.oos_id)
    assert old is not None
    # Simulate R8: the condition cleared and came back as a new occurrence.
    old.condition_cleared_at = T0 + H / 2
    db.commit()
    evaluate(db, world.tenant, T0 + H)
    newer = db.scalars(
        select(OperationalException).where(
            OperationalException.previous_occurrence_id == world.oos_id
        )
    ).one()

    detail = manager.get(url).json()
    assert "reopen" not in detail["available_actions"]
    response = manager.post(f"{url}/reopen", json={"reason": "Still an issue"}, headers=csrf)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "EXCEPTION_NEWER_OCCURRENCE_EXISTS"
    assert error["details"] == [{"exception_id": str(newer.id), "reference": newer.reference}]


# --- notes ----------------------------------------------------------------------------------------


def test_notes_are_appended_and_listed(world: World, db: Session) -> None:
    staff, csrf = world.client(world.staff)
    url = f"{world.base()}/exceptions/{world.oversold_id}/notes"

    created = staff.post(url, json={"body": "  Asked Ironleaf to ship early.  "}, headers=csrf)

    assert created.status_code == 201, created.text
    note = created.json()
    assert note["body"] == "Asked Ironleaf to ship early."
    assert note["source"] == "USER"
    assert note["author"]["id"] == str(world.staff.id)
    assert staff.post(url, json={"body": "   "}, headers=csrf).status_code == 422
    assert staff.post(url, json={"body": "x" * 4001}, headers=csrf).status_code == 422
    listed = staff.get(url).json()
    assert [n["body"] for n in listed["items"]] == ["Asked Ironleaf to ship early."]
    assert _events(db, world.oversold_id)[-1] is ExceptionEventType.NOTE_ADDED
    assert _audit_actions(db, world.oversold_id) == ["exception.note"]
    exc = db.get(OperationalException, world.oversold_id)
    assert exc is not None
    assert exc.version == 2  # NOTE_ADDED is an event, so the version moves


# --- assign ---------------------------------------------------------------------------------------


def test_manager_assigns_reassigns_and_unassigns(world: World, db: Session) -> None:
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oversold_id}/assign"

    first = manager.post(url, json={"assignee_id": str(world.staff.id)}, headers=csrf)
    assert first.status_code == 200
    assert first.json()["assignee"]["id"] == str(world.staff.id)
    second = manager.post(url, json={"assignee_id": str(world.staff2.id)}, headers=csrf)
    assert second.json()["assignee"]["id"] == str(world.staff2.id)
    same = manager.post(url, json={"assignee_id": str(world.staff2.id)}, headers=csrf)
    assert same.json()["version"] == second.json()["version"]  # no-op
    cleared = manager.post(url, json={"assignee_id": None}, headers=csrf)
    assert cleared.json()["assignee"] is None

    rows = db.scalars(
        select(ExceptionAssignment)
        .where(ExceptionAssignment.exception_id == world.oversold_id)
        .order_by(ExceptionAssignment.assigned_at, ExceptionAssignment.assignee_id)
    ).all()
    assert {r.assignee_id for r in rows} == {world.staff.id, world.staff2.id}
    assert all(r.unassigned_at is not None for r in rows)
    assert _events(db, world.oversold_id)[-3:] == [
        ExceptionEventType.ASSIGNED,
        ExceptionEventType.ASSIGNED,
        ExceptionEventType.UNASSIGNED,
    ]
    assert _audit_actions(db, world.oversold_id).count("exception.assign") == 3


def test_assignee_must_be_able_to_work_exceptions(world: World, db: Session) -> None:
    manager, csrf = world.client(world.manager)
    outsider = create_user(db, world.other, Role.STAFF, email="staff@zenith.example")
    url = f"{world.base()}/exceptions/{world.oversold_id}/assign"
    for candidate in (world.viewer.id, world.analyst.id, outsider.id, uuid.uuid4()):
        response = manager.post(url, json={"assignee_id": str(candidate)}, headers=csrf)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ASSIGNEE"


def test_staff_can_claim_only_unassigned_exceptions_for_themselves(world: World) -> None:
    staff, csrf = world.client(world.staff)
    staff2, csrf2 = world.client(world.staff2)
    url = f"{world.base()}/exceptions/{world.oversold_id}/assign"

    other_person = staff.post(url, json={"assignee_id": str(world.staff2.id)}, headers=csrf)
    assert other_person.status_code == 403
    claimed = staff.post(url, json={"assignee_id": str(world.staff.id)}, headers=csrf)
    assert claimed.status_code == 200
    taken = staff2.post(url, json={"assignee_id": str(world.staff2.id)}, headers=csrf2)
    assert taken.status_code == 403
    assert taken.json()["error"]["code"] == "ASSIGNED_TO_ANOTHER_USER"
    release = staff.post(url, json={"assignee_id": None}, headers=csrf)
    assert release.status_code == 403  # releasing needs exceptions.assign (O-27)


# --- due date -------------------------------------------------------------------------------------


def test_due_date_override_is_audited_and_requires_assign_permission(
    world: World, db: Session
) -> None:
    staff, staff_csrf = world.client(world.staff)
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oos_id}/due-date"
    due = "2026-11-12T18:00:00-05:00"

    assert staff.patch(url, json={"due_at": due}, headers=staff_csrf).status_code == 403
    naive = manager.patch(url, json={"due_at": "2026-11-12T18:00:00"}, headers=csrf)
    assert naive.status_code == 422

    response = manager.patch(
        url, json={"due_at": due, "note": "Supplier confirmed Thursday."}, headers=csrf
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["due_at"] == "2026-11-12T23:00:00Z"
    assert body["due_at_overridden"] is True
    assert body["priority_breakdown"]["due"]["basis"] == "OVERRIDE"
    assert _events(db, world.oos_id)[-2:] == [
        ExceptionEventType.DUE_DATE_CHANGED,
        ExceptionEventType.NOTE_ADDED,
    ]
    assert _audit_actions(db, world.oos_id) == ["exception.due_date"]


def test_resolved_exception_rejects_assignment_and_due_date(world: World) -> None:
    manager, csrf = world.client(world.manager)
    url = f"{world.base()}/exceptions/{world.oos_id}"
    manager.post(
        f"{url}/resolve",
        json={"resolution_code": "STOCK_REPLENISHED", "resolution_note": "Stock counted again."},
        headers=csrf,
    )
    assign = manager.post(f"{url}/assign", json={"assignee_id": str(world.staff.id)}, headers=csrf)
    assert assign.status_code == 409
    assert assign.json()["error"]["code"] == "EXCEPTION_NOT_ACTIVE"
    due = manager.patch(f"{url}/due-date", json={"due_at": "2026-11-12T18:00:00Z"}, headers=csrf)
    assert due.status_code == 409


def test_detail_shows_supersede_and_occurrence_links(world: World, db: Session) -> None:
    """BR-401 in the API: the superseded exception points to its successor, offers no reopen,
    and the successor lists what it superseded."""
    knife = make_product(db, world.tenant, "KHK-CHF-20", reorder_point=8)
    set_stock(db, world.tenant, knife, 5, T0)
    evaluate(db, world.tenant, T0 + H / 2)
    make_order(
        db,
        world.tenant,
        OrderSpec(
            "KHK-2001",
            OrderStatus.PAID,
            [LineSpec(knife, 5)],
            placed_at=T0 + H / 2,
            paid_at=T0 + H / 2,
        ),
    )
    evaluate(db, world.tenant, T0 + H)
    below, oos = (
        db.scalars(
            select(OperationalException).where(
                OperationalException.primary_entity_id == knife.id,
                OperationalException.exception_type == exception_type,
            )
        ).one()
        for exception_type in (
            ExceptionType.INVENTORY_BELOW_REORDER_POINT,
            ExceptionType.INVENTORY_OUT_OF_STOCK,
        )
    )
    manager, csrf = world.client(world.manager)

    old = manager.get(f"{world.base()}/exceptions/{below.id}").json()
    new = manager.get(f"{world.base()}/exceptions/{oos.id}").json()

    assert old["status"] == "RESOLVED"
    assert old["resolution"]["resolution_code"] == "SUPERSEDED"
    assert old["resolution"]["resolution_actor"] == "SYSTEM"
    assert old["superseded_by"] == {
        "id": str(oos.id),
        "reference": oos.reference,
        "exception_type": "INVENTORY_OUT_OF_STOCK",
        "status": "OPEN",
        "title": oos.title,
    }
    assert "reopen" not in old["available_actions"]
    assert [ref["id"] for ref in new["supersedes"]] == [str(below.id)]
    reopen = manager.post(
        f"{world.base()}/exceptions/{below.id}/reopen", json={"reason": "Try again"}, headers=csrf
    )
    assert reopen.status_code == 409
    assert reopen.json()["error"]["code"] == "EXCEPTION_TRANSITION_NOT_ALLOWED"
