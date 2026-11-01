"""Public demo visitors cannot change shared data (T-094, ADR-0011).

The checks run against the real demo build (dataset, evaluations and team history) and walk every
mutating operation in the OpenAPI document, so a route added later is covered automatically.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.demo.build import build_demo
from app.domains.exceptions.models import ACTIVE_STATUSES, OperationalException
from app.domains.identity.models import Membership
from app.domains.imports.models import DataImport
from tests.factories import pre_session_csrf

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)
MUTATING = ("post", "put", "patch", "delete")

# Anyone may call these: they create or end the caller's own session, never shared data.
SIGN_IN = {("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/demo")}
OWN_SESSION = {("POST", "/api/v1/auth/logout")}
# Mutating routes a demo visitor may legitimately call because they only write the visitor's own,
# session-scoped data (for example copilot conversations, ADR-0011). Every entry needs a reason.
VISITOR_PRIVATE: set[tuple[str, str]] = {
    # Starts a copilot conversation private to the visitor's session (ai_conversation.session_id).
    ("POST", "/api/v1/stores/{store_id}/copilot/conversations"),
    # Asks a question in that conversation; the copilot reads through read-only tools and writes
    # only the visitor's own ai_message and ai_tool_call rows.
    ("POST", "/api/v1/stores/{store_id}/copilot/conversations/{conversation_id}/messages"),
    # Investigation summary: read-only tools, stored in the visitor's own exception conversation.
    ("POST", "/api/v1/stores/{store_id}/copilot/exception-summaries"),
}

# Session and audit rows are written by signing in and are not shared business data.
UNSHARED_TABLES = {"user_session", "audit_log"}


def _mutating_operations(app: FastAPI) -> list[tuple[str, str]]:
    paths: dict[str, dict[str, Any]] = app.openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if method in MUTATING
    )


def _fingerprint(db: Session) -> dict[str, object]:
    """Row counts of every shared table plus the mutable state of exceptions and imports."""
    counts = {
        table.name: db.scalar(select(func.count()).select_from(table))
        for table in Base.metadata.sorted_tables
        if table.name not in UNSHARED_TABLES
    }
    exceptions = db.execute(
        select(
            OperationalException.id,
            OperationalException.status,
            OperationalException.version,
            OperationalException.assignee_id,
            OperationalException.due_at,
        ).order_by(OperationalException.id)
    ).all()
    imports = db.execute(select(DataImport.id, DataImport.status).order_by(DataImport.id)).all()
    settings = db.execute(text("SELECT * FROM store_settings ORDER BY store_id")).all()
    return {"counts": counts, "exceptions": exceptions, "imports": imports, "settings": settings}


def _url(path: str, ids: dict[str, uuid.UUID]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        assert name in ids, f"Add a demo id for path parameter {name!r} to this test."
        return str(ids[name])

    return re.sub(r"\{(\w+)\}", replace, path)


@pytest.fixture
def demo(db: Session) -> dict[str, uuid.UUID]:
    """The real demo organization, and ids of an active and a closed exception and an import."""
    build = build_demo(db, now=NOW)
    store_id = build.summary.store_id
    active = db.scalars(
        select(OperationalException.id).where(
            OperationalException.store_id == store_id,
            OperationalException.status.in_(ACTIVE_STATUSES),
        )
    ).first()
    closed = db.scalars(
        select(OperationalException.id).where(
            OperationalException.store_id == store_id,
            OperationalException.status.not_in(ACTIVE_STATUSES),
        )
    ).first()
    import_id = db.scalars(select(DataImport.id).where(DataImport.store_id == store_id)).first()
    organization_id = build.summary.organization_id
    membership_id = db.scalars(
        select(Membership.id).where(Membership.organization_id == organization_id)
    ).first()
    assert active is not None
    assert closed is not None
    assert import_id is not None
    assert membership_id is not None
    return {
        "store_id": store_id,
        "active": active,
        "closed": closed,
        "import_id": import_id,
        "organization_id": organization_id,
        "membership_id": membership_id,
        # Copilot conversation routes are visitor-private; anonymous calls stop at 401 first.
        "conversation_id": uuid.uuid4(),
    }


def test_demo_visitors_cannot_change_shared_data_through_any_route(
    app: FastAPI, client: TestClient, db: Session, demo: dict[str, uuid.UUID]
) -> None:
    """One demo build, three phases: anonymous, the sign-in itself, the signed-in visitor."""
    before = _fingerprint(db)

    # 1. Anonymous: every mutating route answers 401; sign-in without the token answers 403.
    for method, path in _mutating_operations(app):
        expected = 403 if (method, path) in SIGN_IN else 401
        ids = {**demo, "exception_id": demo["active"]}
        response = client.request(method, _url(path, ids), json={})
        assert response.status_code == expected, (method, path, response.status_code)

    # 2. "Explore the demo" only ever grants the read-only viewer of the demo store.
    signed_in = client.post("/api/v1/auth/demo", headers=pre_session_csrf(client))
    assert signed_in.status_code == 200
    (membership,) = signed_in.json()["memberships"]
    assert membership["role"] == "VIEWER"
    assert membership["is_demo"] is True
    assert [store["id"] for store in membership["stores"]] == [str(demo["store_id"])]
    write_verbs = {"work", "assign", "manage", "run"}
    assert not [p for p in membership["permissions"] if p.split(".")[-1] in write_verbs]
    csrf = {"X-CSRF-Token": signed_in.json()["csrf_token"]}

    # 3. Signed in with a valid CSRF token, every command is refused by permission, both for an
    #    active and a closed exception, and for the import and store settings of the demo.
    checked: list[tuple[str, str]] = []
    for method, path in _mutating_operations(app):
        if (method, path) in SIGN_IN | OWN_SESSION | VISITOR_PRIVATE:
            continue
        for exception_id in (demo["active"], demo["closed"]):
            ids = {**demo, "exception_id": exception_id}
            response = client.request(method, _url(path, ids), json={}, headers=csrf)
            assert response.status_code == 403, (method, path, response.status_code, response.text)
            assert response.json()["error"]["code"] == "PERMISSION_DENIED", (method, path)
            if "{exception_id}" not in path:
                break
        checked.append((method, path))

    db.expire_all()
    assert _fingerprint(db) == before
    assert len(checked) >= 13  # every store-scoped command known today, plus new ones
    # The visitor's session is still usable for reading.
    overview = client.get(f"/api/v1/stores/{demo['store_id']}/exceptions")
    assert overview.status_code == 200
