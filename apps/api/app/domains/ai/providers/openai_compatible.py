"""The ``openai_compatible`` adapter: any OpenAI-compatible ``/chat/completions`` endpoint with a
free tier (for example Groq, or free models on OpenRouter), configured by ``LLM_BASE_URL``,
``LLM_API_KEY`` and ``LLM_MODEL``. The chosen model must support tool (function) calling.
"""

import json
from typing import Any

import httpx

from app.domains.ai.models import FallbackReason
from app.domains.ai.providers.base import (
    AssistantMessage,
    FinalStep,
    Message,
    ProviderFailure,
    ProviderRequest,
    ProviderStep,
    TextStep,
    ToolCallsStep,
    ToolRequest,
    ToolResultMessage,
    Usage,
    UserMessage,
    estimate_tokens,
    new_call_id,
)
from app.domains.ai.providers.http import post_json


def _tool(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": definition["name"],
            "description": definition["description"],
            "parameters": definition["parameters"],
        },
    }


def _messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for message in messages:
        if isinstance(message, UserMessage):
            out.append({"role": "user", "content": message.text})
        elif isinstance(message, ToolResultMessage):
            out.append(
                {"role": "tool", "tool_call_id": message.call_id, "content": message.content}
            )
        else:
            entry: dict[str, Any] = {"role": "assistant", "content": message.text}
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments or {}),
                        },
                    }
                    for call in message.tool_calls
                ]
            out.append(entry)
    return out


def _arguments(raw: Any) -> Any:
    """Arguments arrive as a JSON string; an unparsable string is passed on as-is and fails the
    server-side validation (INVALID_ARGUMENTS / schema) instead of crashing the turn."""
    if isinstance(raw, str):
        try:
            return json.loads(raw) if raw.strip() else {}
        except ValueError:
            return raw
    return raw


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, client: httpx.Client, *, base_url: str, api_key: str, model: str) -> None:
        self._client = client
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self.model = model

    def build_body(self, request: ProviderRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": _messages(request.system, request.messages),
            "tools": [_tool(d) for d in [*request.tools, request.output_tool]],
            "tool_choice": "auto",
            "max_tokens": request.max_output_tokens,
        }

    def next_step(self, request: ProviderRequest) -> ProviderStep:
        body = self.build_body(request)
        data = post_json(
            self._client,
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            body=body,
            timeout_seconds=request.timeout_seconds,
        )
        return self.parse(data, request, body)

    def parse(
        self, data: dict[str, Any], request: ProviderRequest, body: dict[str, Any]
    ) -> ProviderStep:
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise ProviderFailure(FallbackReason.PROVIDER_ERROR, "no choices")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise ProviderFailure(FallbackReason.INVALID_OUTPUT, "output cut off by token limit")
        if choice.get("finish_reason") == "content_filter":
            raise ProviderFailure(FallbackReason.INVALID_OUTPUT, "content filtered")
        message = choice.get("message") or {}
        calls = tuple(
            ToolRequest(
                id=str(c.get("id") or new_call_id()),
                name=str((c.get("function") or {}).get("name") or ""),
                arguments=_arguments((c.get("function") or {}).get("arguments")),
            )
            for c in message.get("tool_calls") or []
            if isinstance(c, dict)
        )
        text = message.get("content") if isinstance(message.get("content"), str) else None
        usage_data = data.get("usage") or {}
        if "prompt_tokens" in usage_data:
            usage = Usage(
                input_tokens=int(usage_data.get("prompt_tokens") or 0),
                output_tokens=int(usage_data.get("completion_tokens") or 0),
            )
        else:
            usage = Usage(
                input_tokens=estimate_tokens(json.dumps(body)),
                output_tokens=estimate_tokens(json.dumps(message)),
                estimated=True,
            )
        assistant = AssistantMessage(text=text, tool_calls=calls)
        output_name = request.output_tool["name"]
        final = next((c for c in calls if c.name == output_name), None)
        if final is not None:
            return FinalStep(arguments=final.arguments, message=assistant, usage=usage)
        if calls:
            return ToolCallsStep(calls=calls, message=assistant, usage=usage)
        return TextStep(text=text or "", message=assistant, usage=usage)
