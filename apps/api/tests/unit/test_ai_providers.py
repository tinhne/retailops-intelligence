"""Live provider adapters over mocked HTTP, the LLM budget, the circuit breaker and provider
selection (AI_ARCHITECTURE.md §4.2, §8). No test reaches a real LLM API."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.domains.ai import prompts
from app.domains.ai.budget import CircuitBreaker, LLMBudget
from app.domains.ai.models import FallbackReason
from app.domains.ai.providers.base import (
    AssistantMessage,
    FinalStep,
    ProviderFailure,
    ProviderRequest,
    TextStep,
    ToolCallsStep,
    ToolRequest,
    ToolResultMessage,
    UserMessage,
)
from app.domains.ai.providers.gemini import GeminiProvider, gemini_schema
from app.domains.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.domains.ai.runtime import CopilotRuntime, configured_provider
from app.domains.ai.tools.registry import TOOLS
from tests.conftest import make_settings

KEY = "test-key-never-real"
Handler = Callable[[httpx.Request], httpx.Response]


def client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def request(**overrides: Any) -> ProviderRequest:
    base: dict[str, Any] = {
        "system": prompts.SYSTEM.text,
        "messages": [
            UserMessage("<question>What needs attention?</question>"),
            AssistantMessage(tool_calls=(ToolRequest("p0", "get_dashboard_summary", {}),)),
            ToolResultMessage("p0", "get_dashboard_summary", "TOOL DATA ...{}"),
        ],
        "tools": prompts.tool_definitions(list(TOOLS.values())),
        "output_tool": prompts.output_definition(prompts.SUBMIT_ANSWER),
        "max_output_tokens": 512,
        "timeout_seconds": 5.0,
    }
    base.update(overrides)
    return ProviderRequest(**base)


def gemini_reply(parts: list[dict[str, Any]], finish: str = "STOP") -> dict[str, Any]:
    return {
        "candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": finish}],
        "usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 80},
    }


# --- gemini -------------------------------------------------------------------------------------


def test_gemini_sends_the_key_in_a_header_and_maps_tool_calls() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(
            200,
            json=gemini_reply(
                [{"functionCall": {"name": "list_exceptions", "args": {"limit": 5}}}]
            ),
        )

    step = GeminiProvider(client(handler), api_key=KEY, model=None).next_step(request())

    sent = seen[0]
    assert KEY not in str(sent.url)
    assert sent.headers["x-goog-api-key"] == KEY
    assert sent.url.path.endswith("/models/gemini-2.5-flash:generateContent")
    body = json.loads(sent.content)
    assert body["systemInstruction"]["parts"][0]["text"] == prompts.SYSTEM.text
    roles = [c["role"] for c in body["contents"]]
    assert roles == ["user", "model", "user"]
    assert "functionResponse" in body["contents"][2]["parts"][0]
    names = [d["name"] for d in body["tools"][0]["functionDeclarations"]]
    assert names[-1] == "submit_answer"
    assert "list_exceptions" in names
    assert isinstance(step, ToolCallsStep)
    assert step.calls[0].name == "list_exceptions"
    assert step.calls[0].arguments == {"limit": 5}
    assert (step.usage.input_tokens, step.usage.output_tokens) == (1200, 80)


def test_gemini_final_answer_and_plain_text() -> None:
    answer = {"summary": "ok"}
    final = GeminiProvider(
        client(
            lambda r: httpx.Response(
                200,
                json=gemini_reply([{"functionCall": {"name": "submit_answer", "args": answer}}]),
            )
        ),
        api_key=KEY,
        model="gemini-x",
    ).next_step(request())
    plain = GeminiProvider(
        client(lambda r: httpx.Response(200, json=gemini_reply([{"text": "Here you go"}]))),
        api_key=KEY,
        model="gemini-x",
    ).next_step(request())

    assert isinstance(final, FinalStep)
    assert final.arguments == answer
    assert isinstance(plain, TextStep)
    assert plain.text == "Here you go"


def test_gemini_schema_uses_the_openapi_subset() -> None:
    schema = gemini_schema(prompts.tool_definitions([TOOLS["list_exceptions"]])[0]["parameters"])
    assert schema["type"] == "OBJECT"
    assert schema["properties"]["limit"]["type"] == "INTEGER"
    assert "additionalProperties" not in json.dumps(schema)


@pytest.mark.parametrize(
    ("response", "reason", "retry_after"),
    [
        (httpx.Response(429, headers={"Retry-After": "30"}, json={}), "PROVIDER_RATE_LIMITED", 30),
        (
            httpx.Response(
                429,
                json={
                    "error": {
                        "status": "RESOURCE_EXHAUSTED",
                        "details": [
                            {
                                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                                "retryDelay": "17s",
                            }
                        ],
                    }
                },
            ),
            "PROVIDER_RATE_LIMITED",
            17,
        ),
        (httpx.Response(400, json={"error": {"message": "bad tool"}}), "PROVIDER_ERROR", None),
        (httpx.Response(200, json=gemini_reply([], "MAX_TOKENS")), "INVALID_OUTPUT", None),
        (httpx.Response(200, json=gemini_reply([], "SAFETY")), "INVALID_OUTPUT", None),
        (httpx.Response(200, text="<html>"), "PROVIDER_ERROR", None),
    ],
)
def test_gemini_failures_map_to_fallback_reasons(
    response: httpx.Response, reason: str, retry_after: float | None
) -> None:
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return response

    with pytest.raises(ProviderFailure) as failure:
        GeminiProvider(client(handler), api_key=KEY, model="m").next_step(request())

    assert failure.value.reason.value == reason
    assert failure.value.retry_after == retry_after
    assert KEY not in failure.value.detail
    assert len(calls) == 1  # 429 and 4xx are never retried


def test_server_errors_are_retried_once_then_fail() -> None:
    calls: list[int] = []

    def flaky(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=gemini_reply([{"text": "recovered"}]))

    def down(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    assert isinstance(
        GeminiProvider(client(flaky), api_key=KEY, model="m").next_step(request()), TextStep
    )
    calls.clear()
    with pytest.raises(ProviderFailure) as failure:
        GeminiProvider(client(down), api_key=KEY, model="m").next_step(request())
    assert failure.value.reason is FallbackReason.PROVIDER_ERROR
    assert len(calls) == 2


def test_timeouts_map_to_provider_timeout() -> None:
    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=req)

    with pytest.raises(ProviderFailure) as failure:
        GeminiProvider(client(slow), api_key=KEY, model="m").next_step(request())
    assert failure.value.reason is FallbackReason.PROVIDER_TIMEOUT


# --- openai_compatible ---------------------------------------------------------------------------


def test_openai_compatible_maps_messages_tools_and_calls() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "submit_answer",
                                        "arguments": json.dumps({"summary": "done"}),
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 900, "completion_tokens": 40},
            },
        )

    provider = OpenAICompatibleProvider(
        client(handler), base_url="https://api.example.test/openai/v1/", api_key=KEY, model="free-m"
    )
    step = provider.next_step(request())

    sent = seen[0]
    assert str(sent.url) == "https://api.example.test/openai/v1/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "tool"]
    assert body["messages"][3]["tool_call_id"] == "p0"
    assert body["tools"][-1]["function"]["name"] == "submit_answer"
    assert isinstance(step, FinalStep)
    assert step.arguments == {"summary": "done"}
    assert step.usage.input_tokens == 900


def test_openai_compatible_length_cutoff_is_invalid_output() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": "…"}}]}
        )

    provider = OpenAICompatibleProvider(
        client(handler), base_url="https://x.test/v1", api_key=KEY, model="m"
    )
    with pytest.raises(ProviderFailure) as failure:
        provider.next_step(request())
    assert failure.value.reason is FallbackReason.INVALID_OUTPUT


# --- budget, circuit, selection ------------------------------------------------------------------


def test_budget_caps_requests_per_minute_day_and_tokens() -> None:
    now = [1_000_000.0]
    budget = LLMBudget(
        requests_per_minute=2, requests_per_day=3, tokens_per_day=500, clock=lambda: now[0]
    )
    assert budget.try_acquire()
    assert budget.try_acquire()
    assert not budget.try_acquire()  # minute window full
    now[0] += 61
    assert budget.try_acquire()
    now[0] += 61
    assert not budget.try_acquire()  # day cap of 3 requests
    now[0] += 86_400  # next UTC day
    assert budget.try_acquire()
    budget.record_tokens(600)
    now[0] += 61
    assert not budget.try_acquire()  # token cap


def test_circuit_opens_on_repeated_failures_and_after_quota_errors() -> None:
    now = [0.0]
    breaker = CircuitBreaker(failure_threshold=3, open_seconds=60, clock=lambda: now[0])
    for _ in range(2):
        breaker.record_failure(FallbackReason.PROVIDER_ERROR)
    assert breaker.allow()
    breaker.record_failure(FallbackReason.PROVIDER_TIMEOUT)
    assert not breaker.allow()
    now[0] += 61
    assert breaker.allow()

    breaker.record_failure(FallbackReason.PROVIDER_RATE_LIMITED, retry_after=10)
    assert not breaker.allow()
    now[0] += 11
    assert breaker.allow()
    breaker.record_failure(FallbackReason.PROVIDER_RATE_LIMITED)  # 2nd in a row: 120 s
    now[0] += 100
    assert not breaker.allow()
    now[0] += 21
    assert breaker.allow()


def test_provider_selection_follows_the_settings() -> None:
    assert configured_provider(make_settings()) == "deterministic"
    assert configured_provider(make_settings(gemini_api_key=SecretStr(KEY))) == "gemini"
    assert configured_provider(make_settings(llm_provider="", gemini_api_key="")) == (
        "deterministic"
    )
    explicit = make_settings(llm_provider="deterministic", gemini_api_key=SecretStr(KEY))
    assert configured_provider(explicit) == "deterministic"

    missing = CopilotRuntime(make_settings(llm_provider="openai_compatible"))
    assert missing.live_provider() == (None, FallbackReason.PROVIDER_NOT_CONFIGURED)
    configured = CopilotRuntime(
        make_settings(
            llm_provider="openai_compatible",
            llm_base_url="https://x.test/v1",
            llm_api_key=SecretStr(KEY),
            llm_model="free-model",
        )
    )
    provider, reason = configured.live_provider()
    assert reason is None
    assert provider is not None
    assert provider.name == "openai_compatible"
    assert CopilotRuntime(make_settings()).live_provider() == (None, None)
    assert KEY not in repr(make_settings(gemini_api_key=SecretStr(KEY)))
