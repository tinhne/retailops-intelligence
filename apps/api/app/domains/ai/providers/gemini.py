"""The ``gemini`` adapter: Google Gemini API (free tier, key from Google AI Studio) over HTTPS.

Uses the ``generateContent`` REST method with function calling. The key travels in the
``x-goog-api-key`` header, never in the URL, and is never logged. The default model is a
"Flash"-class model; ``LLM_MODEL`` overrides it when Google retires or renames free-tier models.
"""

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

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"  # Needs validation against Google's current free-tier list
_BLOCKED_FINISH = {
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "MALFORMED_FUNCTION_CALL",
    "OTHER",
}
_KEEP = ("description", "enum", "minItems", "maxItems", "required")


def gemini_schema(node: dict[str, Any]) -> dict[str, Any]:
    """Neutral JSON Schema → the OpenAPI subset Gemini function declarations accept."""
    out: dict[str, Any] = {k: node[k] for k in _KEEP if k in node}
    if "type" in node:
        out["type"] = str(node["type"]).upper()
    if node.get("format") == "date-time":
        out["format"] = "date-time"
    if "items" in node:
        out["items"] = gemini_schema(node["items"])
    if "properties" in node:
        out["properties"] = {k: gemini_schema(v) for k, v in node["properties"].items()}
    return out


def _declaration(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": definition["name"],
        "description": definition["description"],
        "parameters": gemini_schema(definition["parameters"]),
    }


def _contents(messages: list[Message]) -> list[dict[str, Any]]:
    """Neutral messages → Gemini ``contents``. The results of one round go in one user turn."""
    contents: list[dict[str, Any]] = []
    previous_was_result = False
    for message in messages:
        if isinstance(message, ToolResultMessage):
            key = "error" if message.is_error else "result"
            part = {"functionResponse": {"name": message.name, "response": {key: message.content}}}
            if previous_was_result:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": "user", "parts": [part]})
            previous_was_result = True
            continue
        previous_was_result = False
        if isinstance(message, UserMessage):
            contents.append({"role": "user", "parts": [{"text": message.text}]})
        elif message.raw is not None:
            contents.append({"role": "model", "parts": message.raw})
        else:
            parts: list[dict[str, Any]] = [{"text": message.text}] if message.text else []
            parts += [
                {"functionCall": {"name": c.name, "args": c.arguments or {}}}
                for c in message.tool_calls
            ]
            contents.append({"role": "model", "parts": parts})
    return contents


class GeminiProvider:
    name = "gemini"

    def __init__(self, client: httpx.Client, *, api_key: str, model: str | None) -> None:
        self._client = client
        self._api_key = api_key
        self.model = model or DEFAULT_MODEL

    def build_body(self, request: ProviderRequest) -> dict[str, Any]:
        declarations = [_declaration(d) for d in [*request.tools, request.output_tool]]
        return {
            "systemInstruction": {"parts": [{"text": request.system}]},
            "contents": _contents(request.messages),
            "tools": [{"functionDeclarations": declarations}],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"maxOutputTokens": request.max_output_tokens},
        }

    def next_step(self, request: ProviderRequest) -> ProviderStep:
        body = self.build_body(request)
        data = post_json(
            self._client,
            f"{API_BASE}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self._api_key},
            body=body,
            timeout_seconds=request.timeout_seconds,
        )
        return self.parse(data, request, body)

    def parse(
        self, data: dict[str, Any], request: ProviderRequest, body: dict[str, Any]
    ) -> ProviderStep:
        candidates = data.get("candidates") or []
        if not candidates:
            if (data.get("promptFeedback") or {}).get("blockReason"):
                raise ProviderFailure(FallbackReason.INVALID_OUTPUT, "prompt blocked")
            raise ProviderFailure(FallbackReason.PROVIDER_ERROR, "no candidates")
        candidate = candidates[0]
        finish = str(candidate.get("finishReason") or "")
        if finish == "MAX_TOKENS":
            raise ProviderFailure(FallbackReason.INVALID_OUTPUT, "output cut off by token limit")
        if finish in _BLOCKED_FINISH:
            raise ProviderFailure(FallbackReason.INVALID_OUTPUT, f"finish reason {finish}")
        parts: list[dict[str, Any]] = (candidate.get("content") or {}).get("parts") or []
        usage = self._usage(data, body, parts)
        calls = tuple(
            ToolRequest(
                id=str(p["functionCall"].get("id") or new_call_id()),
                name=str(p["functionCall"].get("name") or ""),
                arguments=p["functionCall"].get("args") or {},
            )
            for p in parts
            if isinstance(p.get("functionCall"), dict)
        )
        text = "".join(str(p["text"]) for p in parts if "text" in p and not p.get("thought"))
        message = AssistantMessage(text=text or None, tool_calls=calls, raw=parts)
        output_name = request.output_tool["name"]
        final = next((c for c in calls if c.name == output_name), None)
        if final is not None:
            return FinalStep(arguments=final.arguments, message=message, usage=usage)
        if calls:
            return ToolCallsStep(calls=calls, message=message, usage=usage)
        return TextStep(text=text, message=message, usage=usage)

    @staticmethod
    def _usage(data: dict[str, Any], body: dict[str, Any], parts: list[dict[str, Any]]) -> Usage:
        meta = data.get("usageMetadata") or {}
        if "promptTokenCount" in meta:
            return Usage(
                input_tokens=int(meta.get("promptTokenCount") or 0),
                output_tokens=int(meta.get("candidatesTokenCount") or 0),
            )
        return Usage(
            input_tokens=estimate_tokens(str(body)),
            output_tokens=estimate_tokens(str(parts)),
            estimated=True,
        )
