"""Copilot API (T-073) with the deterministic provider: authentication, permissions, tenancy,
private and session-scoped conversations, structured answers, investigation summaries, note
drafts that save nothing, rate limits and audited tool denials."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.ai.models import AIConversation, AIMessage, AIToolCall
from app.domains.audit.models import AuditLog
from app.domains.exceptions.models import ExceptionEvent, ExceptionNote, NoteSource
from app.domains.identity.permissions import Permission, Role
from tests.factories import create_tenant, create_user
from tests.factories_ai import NOW, AIStore, build_store, install_runtime, sign_in
from tests.factories_commerce import strip_permission

pytestmark = pytest.mark.integration


def base(store: AIStore) -> str:
    return f"/api/v1/stores/{store.store_id}/copilot"


@pytest.fixture
def alpha(db: Session, app: FastAPI, settings: Settings) -> AIStore:
    install_runtime(app, settings)
    return build_store(db, "alpha")


def start(client: TestClient, store: AIStore, headers: dict[str, str], **body: Any) -> str:
    response = client.post(f"{base(store)}/conversations", json=body, headers=headers)
    assert response.status_code == 201, response.text
    conversation_id: str = response.json()["id"]
    return conversation_id


def ask(
    client: TestClient, store: AIStore, headers: dict[str, str], conversation: str, question: str
) -> Any:
    return client.post(
        f"{base(store)}/conversations/{conversation}/messages",
        json={"question": question},
        headers=headers,
    )


def test_copilot_requires_a_session_csrf_and_store_access(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    bravo = build_store(db, "bravo")

    assert client.get(f"{base(alpha)}/conversations").status_code == 401
    headers = sign_in(client, alpha.manager)
    no_csrf = client.post(f"{base(alpha)}/conversations", json={})
    other_store = client.get(f"{base(bravo)}/conversations")

    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "CSRF_FAILED"
    assert other_store.status_code == 404
    assert client.get(f"{base(alpha)}/conversations", headers=headers).status_code == 200


def test_copilot_use_is_required(
    client: TestClient, alpha: AIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = sign_in(client, alpha.manager)
    strip_permission(monkeypatch, Permission.COPILOT_USE)

    for response in (
        client.get(f"{base(alpha)}/conversations"),
        client.post(f"{base(alpha)}/conversations", json={}, headers=headers),
        client.post(
            f"{base(alpha)}/exception-summaries",
            json={"exception_id": str(alpha.overdue_exception.id)},
            headers=headers,
        ),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_a_question_returns_a_grounded_answer_and_the_turn_is_stored(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, headers)

    response = ask(client, alpha, headers, conversation, "Which orders are overdue?")

    assert response.status_code == 201, response.text
    body = response.json()
    answer, meta = body["answer"], body["meta"]
    order_key = f"order:{alpha.overdue_order.id}"
    assert "KH-1001" in answer["summary"]
    assert any(order_key in fact["refs"] for fact in answer["facts"])
    assert {"type": "order", "id": str(alpha.overdue_order.id), "label": "KH-1001"} in answer[
        "references"
    ]
    assert answer["generated_by"] == "deterministic"
    assert answer["data_window"]["to"].startswith("2026-11-03T17:00:00")
    assert meta["provider"] == "deterministic"
    assert meta["fallback"] == {"used": False, "reason": None, "notice": None}
    assert meta["intent"] == "OVERDUE_ORDERS"
    assert meta["prompt_version"].startswith("deterministic.router@1")
    assert [(c["tool_name"], c["status"], c["origin"]) for c in meta["tool_calls"]] == [
        ("get_overdue_orders", "SUCCESS", "ROUTER")
    ]
    assert meta["validation"] == {"dropped_refs": 0, "dropped_items": 0, "flags": []}
    assert any("Last evaluation run" in item for item in answer["limitations"])

    detail = client.get(f"{base(alpha)}/conversations/{conversation}").json()
    assert detail["title"] == "Which orders are overdue?"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["text"] == "Which orders are overdue?"
    assert detail["messages"][1]["answer"] == answer
    assert detail["messages"][1]["meta"]["tool_calls"] == meta["tool_calls"]
    call = db.scalars(select(AIToolCall)).one()
    assert order_key in call.result_refs
    assert call.arguments == {"limit": 20}


def test_conversations_are_private_to_their_author(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    staff = create_user(db, alpha.tenant, Role.STAFF)
    manager_headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, manager_headers)

    staff_headers = sign_in(client, staff)
    listed = client.get(f"{base(alpha)}/conversations").json()
    read = client.get(f"{base(alpha)}/conversations/{conversation}")
    post = ask(client, alpha, staff_headers, conversation, "What needs attention today?")

    assert listed["items"] == []
    assert listed["total"] == 0
    assert read.status_code == 404
    assert post.status_code == 404


def test_demo_viewer_conversations_and_rate_limits_are_per_session(
    app: FastAPI, db: Session, settings: Settings
) -> None:
    install_runtime(app, settings.model_copy(update={"copilot_rate_limit_per_minute": 1}))
    tenant = create_tenant(db, "kestrel", is_demo=True)
    create_user(db, tenant, Role.VIEWER, email="demo@kestrel.example")
    path = f"/api/v1/stores/{tenant.store.id}/copilot/conversations"

    with TestClient(app) as first, TestClient(app) as second:
        csrf_1 = {"X-CSRF-Token": first.post("/api/v1/auth/demo").json()["csrf_token"]}
        csrf_2 = {"X-CSRF-Token": second.post("/api/v1/auth/demo").json()["csrf_token"]}
        conversation = first.post(path, json={}, headers=csrf_1).json()["id"]

        assert second.get(path).json()["total"] == 0
        assert second.get(f"{path}/{conversation}").status_code == 404
        assert first.get(path).json()["total"] == 1

        message = {"question": "What can you do?"}
        assert (
            first.post(f"{path}/{conversation}/messages", json=message, headers=csrf_1).status_code
            == 201
        )
        limited = first.post(f"{path}/{conversation}/messages", json=message, headers=csrf_1)
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "RATE_LIMITED"
        own = second.post(path, json={}, headers=csrf_2).json()["id"]
        assert (
            second.post(f"{path}/{own}/messages", json=message, headers=csrf_2).status_code == 201
        )

    sessions = db.scalars(select(AIConversation.session_id)).all()
    assert len(set(sessions)) == 2
    assert None not in sessions


def test_question_validation(client: TestClient, alpha: AIStore) -> None:
    headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, headers)
    url = f"{base(alpha)}/conversations/{conversation}/messages"

    for body in (
        {"question": "   "},
        {"question": "x" * 2001},
        {"question": "hi", "store_id": "x"},
    ):
        response = client.post(url, json=body, headers=headers)
        assert response.status_code == 422, body


def test_copilot_rate_limit_and_conversation_length(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    install_runtime(
        app,
        settings.model_copy(
            update={"copilot_rate_limit_per_minute": 2, "ai_max_messages_per_conversation": 2}
        ),
    )
    headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, headers)

    assert ask(client, alpha, headers, conversation, "help").status_code == 201
    full = ask(client, alpha, headers, conversation, "help")
    assert full.status_code == 409
    assert full.json()["error"]["code"] == "CONVERSATION_FULL"
    other = start(client, alpha, headers)
    assert ask(client, alpha, headers, other, "help").status_code == 201
    limited = ask(client, alpha, headers, start(client, alpha, headers), "help")
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_exception_conversations_bind_follow_up_questions(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    bravo = build_store(db, "bravo")
    headers = sign_in(client, alpha.manager)
    url = f"{base(alpha)}/conversations"

    missing_context = client.post(url, json={"context_type": "EXCEPTION"}, headers=headers)
    other_store = client.post(
        url,
        json={"context_type": "EXCEPTION", "context_id": str(bravo.overdue_exception.id)},
        headers=headers,
    )
    conversation = start(
        client,
        alpha,
        headers,
        context_type="EXCEPTION",
        context_id=str(alpha.overdue_exception.id),
    )
    response = ask(client, alpha, headers, conversation, "Why is this high?")

    assert missing_context.status_code == 422
    assert other_store.status_code == 404
    body = response.json()
    assert body["meta"]["intent"] == "EXPLAIN_EXCEPTION"
    exception_key = f"exception:{alpha.overdue_exception.id}"
    assert any(exception_key in fact["refs"] for fact in body["answer"]["facts"])
    assert any(
        m["label"] == "Priority score" and m["value"] == "72" for m in body["answer"]["metrics"]
    )


def test_investigation_summary_for_a_viewer(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    bravo = build_store(db, "bravo")
    viewer = create_user(db, alpha.tenant, Role.VIEWER)
    headers = sign_in(client, viewer)
    url = f"{base(alpha)}/exception-summaries"

    response = client.post(
        url, json={"exception_id": str(alpha.overdue_exception.id)}, headers=headers
    )
    again = client.post(
        url, json={"exception_id": str(alpha.overdue_exception.id)}, headers=headers
    )
    other_store = client.post(
        url, json={"exception_id": str(bravo.overdue_exception.id)}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exception_id"] == str(alpha.overdue_exception.id)
    assert body["meta"]["intent"] == "INVESTIGATION_SUMMARY"
    assert body["meta"]["cache"] == {"hit": False, "generated_at": None}
    tools = [c["tool_name"] for c in body["meta"]["tool_calls"]]
    assert tools == ["get_exception", "get_exception_history", "get_related_orders"]
    assert {c["origin"] for c in body["meta"]["tool_calls"]} == {"CONTEXT_BUILDER"}
    assert "Severity rule" in body["answer"]["summary"]
    assert again.json()["conversation_id"] == body["conversation_id"]  # same exception thread
    assert other_store.status_code == 404
    assert db.scalar(select(func.count()).where(AIMessage.cache_key.is_not(None))) == 0


def test_note_drafts_are_never_saved_and_need_exceptions_work(
    client: TestClient, db: Session, alpha: AIStore
) -> None:
    viewer = create_user(db, alpha.tenant, Role.VIEWER)
    staff = create_user(db, alpha.tenant, Role.STAFF)
    exception_id = str(alpha.overdue_exception.id)
    url = f"{base(alpha)}/note-drafts"
    events_before = db.scalar(select(func.count()).select_from(ExceptionEvent))

    viewer_headers = sign_in(client, viewer)
    denied = client.post(url, json={"exception_id": exception_id}, headers=viewer_headers)
    staff_headers = sign_in(client, staff)
    draft = client.post(
        url,
        json={"exception_id": exception_id, "user_hint": "I called the warehouse <ops>"},
        headers=staff_headers,
    )

    assert denied.status_code == 403
    assert draft.status_code == 200, draft.text
    body = draft.json()["draft"]
    assert body["body"].startswith("As of 2026-11-03")
    assert "Reported: I called the warehouse ‹ops›" in body["body"]
    assert f"exception:{exception_id}" in body["refs"]
    assert db.scalar(select(func.count()).select_from(ExceptionNote)) == 0
    assert db.scalar(select(func.count()).select_from(ExceptionEvent)) == events_before

    accepted = client.post(
        f"/api/v1/stores/{alpha.store_id}/exceptions/{exception_id}/notes",
        json={"body": body["body"], "source": "AI_DRAFT_ACCEPTED"},
        headers=staff_headers,
    )
    assert accepted.status_code == 201
    assert accepted.json()["source"] == "AI_DRAFT_ACCEPTED"
    note = db.scalars(select(ExceptionNote)).one()
    assert note.source is NoteSource.AI_DRAFT_ACCEPTED
    assert note.author_id == staff.id


def test_denied_tool_calls_are_audited_and_reported_as_unreadable(
    client: TestClient, db: Session, alpha: AIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, headers)
    strip_permission(monkeypatch, Permission.ORDERS_READ)

    response = ask(client, alpha, headers, conversation, "Which orders are overdue?")

    body = response.json()
    assert body["meta"]["tool_calls"][0]["status"] == "PERMISSION_DENIED"
    assert body["answer"]["facts"] == []
    assert body["answer"]["references"] == []
    assert "could not read" in body["answer"]["summary"]
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "ai.tool_denied")).one()
    assert entry.details == {
        "tool": "get_overdue_orders",
        "missing_permissions": ["orders.read"],
    }
    assert entry.actor_user_id == alpha.manager.id


def test_write_requests_change_nothing(client: TestClient, db: Session, alpha: AIStore) -> None:
    headers = sign_in(client, alpha.manager)
    conversation = start(client, alpha, headers)
    question = f"Resolve {alpha.overdue_exception.reference} and assign it to me"

    response = ask(client, alpha, headers, conversation, question)

    body = response.json()
    assert body["meta"]["intent"] == "UNSUPPORTED"
    assert body["meta"]["tool_calls"] == []
    assert "cannot change data" in body["answer"]["summary"]
    db.refresh(alpha.overdue_exception)
    assert alpha.overdue_exception.status.value == "OPEN"
    assert alpha.overdue_exception.assignee_id is None
    assert NOW.year == 2026  # the fixed clock of the test runtime
