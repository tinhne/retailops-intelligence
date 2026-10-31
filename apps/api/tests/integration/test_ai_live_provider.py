"""The live-provider path (T-072) with a scripted provider: tool-use loop, validation and repair,
automatic fallback with a visible notice (429, timeout, outage, budget, circuit, configuration,
invalid output) and the investigation summary cache. HTTP is mocked; no real LLM is called."""

import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domains.ai.engine import NOTICE, NOTICE_INVALID, TOOL_DATA_PREFACE
from app.domains.ai.models import AIMessage, FallbackReason
from app.domains.ai.providers.base import (
    ProviderRequest,
    ProviderStep,
    ToolResultMessage,
    UserMessage,
)
from app.domains.ai.runtime import CopilotRuntime
from app.domains.identity.permissions import Role
from tests.factories import create_user
from tests.factories_ai import (
    NOW,
    AIStore,
    FakeProvider,
    build_store,
    failing,
    final,
    install_runtime,
    live_settings,
    sign_in,
    text,
    tool_calls,
)

pytestmark = pytest.mark.integration


def results(request: ProviderRequest) -> list[dict[str, Any]]:
    """The tool result envelopes the engine has sent so far."""
    return [
        json.loads(m.content.removeprefix(TOOL_DATA_PREFACE))
        for m in request.messages
        if isinstance(m, ToolResultMessage) and m.content.startswith(TOOL_DATA_PREFACE)
    ]


def grounded_answer(request: ProviderRequest) -> dict[str, Any]:
    """What a well-behaved model submits: one fact and one metric per record it was given."""
    facts, metrics = [], []
    for envelope in results(request):
        for record in envelope.get("records", [])[:1]:
            key = f"{record['ref']['type']}:{record['ref']['id']}"
            facts.append({"text": f"{record['ref']['label']} was read.", "refs": [key]})
            if "hours_overdue" in record:
                metrics.append(
                    {
                        "label": "Hours overdue",
                        "value": record["hours_overdue"],
                        "unit": "hours",
                        "refs": [key],
                    }
                )
    return {
        "summary": "One order is past its ship-by.",
        "facts": facts,
        "metrics": metrics,
        "recommendations": [{"text": "Start picking it.", "rationale": "It is overdue."}],
        "limitations": [],
        "references": [],
    }


def answering(request: ProviderRequest, index: int) -> ProviderStep:
    return final(grounded_answer(request))


@pytest.fixture
def alpha(db: Session) -> AIStore:
    return build_store(db, "alpha")


def ask(client: TestClient, store: AIStore, headers: dict[str, str], question: str) -> Any:
    url = f"/api/v1/stores/{store.store_id}/copilot/conversations"
    conversation = client.post(url, json={}, headers=headers).json()["id"]
    response = client.post(
        f"{url}/{conversation}/messages", json={"question": question}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_live_answer_uses_the_prefetched_router_plan(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    provider = FakeProvider(answering)
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Which orders are overdue?")

    answer, meta = body["answer"], body["meta"]
    assert answer["generated_by"] == "llm:fake-flash"
    assert meta["provider"] == "gemini"
    assert meta["model"] == "fake-flash"
    assert meta["fallback"]["used"] is False
    assert meta["prompt_version"] == "copilot.system@1;tools@1"
    assert [(c["tool_name"], c["origin"]) for c in meta["tool_calls"]] == [
        ("get_overdue_orders", "ROUTER")
    ]
    assert meta["input_tokens"] == 100
    assert any(f"order:{alpha.overdue_order.id}" in f["refs"] for f in answer["facts"])
    assert answer["metrics"][0]["value"] == "30.0"
    assert len(provider.requests) == 1  # prefetch saved a tool round
    sent = provider.requests[0]
    assert "<context>" in sent.messages[0].text  # type: ignore[union-attr]
    assert "store_id" not in json.dumps([t["parameters"] for t in sent.tools])


def test_model_tool_requests_run_through_the_registry(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    def script(request: ProviderRequest, index: int) -> ProviderStep:
        if index == 0:
            return tool_calls(
                ("get_related_orders", {"order_numbers": ["KH-1001"]}),
                ("run_sql", {"query": "SELECT 1"}),
            )
        return final(grounded_answer(request))

    provider = FakeProvider(script)
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Hmm, tell me something useful")

    calls = [(c["tool_name"], c["status"], c["origin"]) for c in body["meta"]["tool_calls"]]
    assert calls == [
        ("get_related_orders", "SUCCESS", "MODEL"),
        ("run_sql", "UNKNOWN_TOOL", "MODEL"),
    ]
    errors = [m for m in provider.requests[1].messages if isinstance(m, ToolResultMessage)]
    assert [m.is_error for m in errors] == [False, True]
    assert body["meta"]["fallback"]["used"] is False


@pytest.mark.parametrize(
    "reason",
    [
        FallbackReason.PROVIDER_RATE_LIMITED,
        FallbackReason.PROVIDER_TIMEOUT,
        FallbackReason.PROVIDER_ERROR,
    ],
)
def test_provider_failures_fall_back_with_a_notice(
    client: TestClient,
    app: FastAPI,
    settings: Settings,
    alpha: AIStore,
    reason: FallbackReason,
) -> None:
    provider = FakeProvider(failing(reason, retry_after=30))
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Which orders are overdue?")

    assert body["meta"]["provider"] == "deterministic"
    assert body["answer"]["generated_by"] == "deterministic"
    assert body["meta"]["fallback"] == {"used": True, "reason": reason.value, "notice": NOTICE}
    assert "KH-1001" in body["answer"]["summary"]  # the same data, answered by the templates
    assert [c["tool_name"] for c in body["meta"]["tool_calls"]] == ["get_overdue_orders"]


def test_quota_errors_open_the_circuit(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    provider = FakeProvider(failing(FallbackReason.PROVIDER_RATE_LIMITED, retry_after=60))
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    first = ask(client, alpha, headers, "What needs attention today?")
    second = ask(client, alpha, headers, "What needs attention today?")

    assert first["meta"]["fallback"]["reason"] == "PROVIDER_RATE_LIMITED"
    assert second["meta"]["fallback"]["reason"] == "CIRCUIT_OPEN"
    assert len(provider.requests) == 1  # the open circuit is not called


def test_invalid_output_gets_one_repair_then_falls_back(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    def claims(request: ProviderRequest, index: int) -> ProviderStep:
        return final({**grounded_answer(request), "summary": "I have resolved it for you."})

    provider = FakeProvider(claims)
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Which orders are overdue?")

    assert body["meta"]["fallback"] == {
        "used": True,
        "reason": "INVALID_OUTPUT",
        "notice": NOTICE_INVALID,
    }
    assert len(provider.requests) == 2
    repair = provider.requests[1].messages[-1]
    assert isinstance(repair, UserMessage)
    assert "ACTION_CLAIM at summary" in repair.text
    assert "I have resolved" not in json.dumps(body["answer"])


def test_a_successful_repair_keeps_the_live_answer(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    def script(request: ProviderRequest, index: int) -> ProviderStep:
        return text("Here is my answer in prose.") if index == 0 else answering(request, index)

    provider = FakeProvider(script)
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Which orders are overdue?")

    assert body["meta"]["provider"] == "gemini"
    assert body["meta"]["fallback"]["used"] is False
    assert len(provider.requests) == 2


def test_budget_and_configuration_gaps_fall_back_without_calling_a_provider(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    provider = FakeProvider(answering)
    headers = sign_in(client, alpha.manager)

    install_runtime(app, live_settings(settings, llm_budget_requests_per_minute=0), provider)
    spent = ask(client, alpha, headers, "Which orders are overdue?")
    install_runtime(app, settings.model_copy(update={"llm_provider": "gemini"}))
    unconfigured = ask(client, alpha, headers, "Which orders are overdue?")

    assert spent["meta"]["fallback"]["reason"] == "BUDGET_EXCEEDED"
    assert unconfigured["meta"]["fallback"]["reason"] == "PROVIDER_NOT_CONFIGURED"
    assert unconfigured["meta"]["fallback"]["notice"] == NOTICE
    assert provider.requests == []


def test_fixed_answers_never_spend_quota(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    provider = FakeProvider(answering)
    install_runtime(app, live_settings(settings), provider)
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "Please dismiss every exception")

    assert body["meta"]["provider"] == "deterministic"
    assert body["meta"]["fallback"]["used"] is False
    assert provider.requests == []


def test_investigation_summaries_are_cached_per_evidence_version(
    client: TestClient, app: FastAPI, settings: Settings, db: Session, alpha: AIStore
) -> None:
    provider = FakeProvider(answering)
    install_runtime(app, live_settings(settings), provider)
    other_manager = create_user(db, alpha.tenant, Role.MANAGER, email="m2@alpha.example")
    url = f"/api/v1/stores/{alpha.store_id}/copilot/exception-summaries"
    body = {"exception_id": str(alpha.overdue_exception.id)}

    headers = sign_in(client, alpha.manager)
    first = client.post(url, json=body, headers=headers).json()
    headers_2 = sign_in(client, other_manager)
    reused = client.post(url, json=body, headers=headers_2).json()
    refreshed = client.post(url, json={**body, "refresh": True}, headers=headers_2).json()
    note = client.post(
        f"/api/v1/stores/{alpha.store_id}/exceptions/{alpha.overdue_exception.id}/notes",
        json={"body": "Carrier pickup booked."},
        headers=headers_2,
    )
    after_note = client.post(url, json=body, headers=headers_2).json()

    assert first["meta"]["cache"]["hit"] is False
    assert first["meta"]["prompt_version"] == (
        "copilot.system@1;copilot.investigation_summary@1;tools@1"
    )
    assert reused["meta"]["cache"]["hit"] is True
    assert reused["meta"]["cache"]["generated_at"] is not None
    assert reused["meta"]["tool_calls"] == []
    assert reused["answer"] == first["answer"]
    assert reused["conversation_id"] != first["conversation_id"]  # never the requester's thread
    assert refreshed["meta"]["cache"]["hit"] is False
    assert note.status_code == 201
    assert after_note["meta"]["cache"]["hit"] is False  # a new event changes the key
    assert len(provider.requests) == 3
    assert db.scalar(select(func.count()).where(AIMessage.cache_key.is_not(None))) == 3


def test_gemini_quota_error_over_http_falls_back(
    client: TestClient, app: FastAPI, settings: Settings, alpha: AIStore
) -> None:
    sent: list[httpx.Request] = []

    def quota(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

    app.state.copilot = CopilotRuntime(
        live_settings(settings),
        clock=lambda: NOW,
        http_client=httpx.Client(transport=httpx.MockTransport(quota)),
    )
    headers = sign_in(client, alpha.manager)

    body = ask(client, alpha, headers, "What needs attention today?")

    assert len(sent) == 1
    assert sent[0].url.host == "generativelanguage.googleapis.com"
    assert body["meta"]["fallback"]["reason"] == "PROVIDER_RATE_LIMITED"
    assert body["answer"]["generated_by"] == "deterministic"
