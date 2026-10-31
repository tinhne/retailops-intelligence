"""The provider-neutral LLM contract (AI_ARCHITECTURE.md §2, §8.4).

A live adapter turns a ``ProviderRequest`` into one HTTP request to its free-tier API and returns
either the tool calls the model asked for (``ToolCallsStep``) or the arguments of the output
function (``FinalStep``). Adapters never execute tools: ``CopilotService`` does, through the tool
registry, so permission checks and scoping live in one place whatever the provider.

Every failure is raised as ``ProviderFailure`` with a fallback reason; the turn then falls back to
the deterministic provider. Keys never appear in messages, logs or errors.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domains.ai.models import FallbackReason


@dataclass(frozen=True)
class ToolRequest:
    id: str
    name: str
    arguments: Any


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    text: str | None = None
    tool_calls: tuple[ToolRequest, ...] = ()
    # The provider's own encoding of this turn (for example Gemini parts with thought
    # signatures), replayed verbatim to the same adapter. None for synthetic prefetch turns.
    raw: Any = None


@dataclass(frozen=True)
class ToolResultMessage:
    call_id: str
    name: str
    content: str
    is_error: bool = False


Message = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    messages: list[Message]
    tools: list[dict[str, Any]]  # neutral definitions; empty when tools are disabled
    output_tool: dict[str, Any]  # submit_answer or submit_note_draft
    max_output_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated: bool = False


@dataclass(frozen=True)
class ToolCallsStep:
    calls: tuple[ToolRequest, ...]
    message: AssistantMessage
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class FinalStep:
    arguments: Any  # parameters of the output function, validated by the server
    message: AssistantMessage
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class TextStep:
    """The model answered in plain text instead of calling the output function (invalid)."""

    text: str
    message: AssistantMessage
    usage: Usage = field(default_factory=Usage)


ProviderStep = ToolCallsStep | FinalStep | TextStep


class ProviderFailure(Exception):  # noqa: N818 - a domain outcome, not a programming error
    def __init__(self, reason: FallbackReason, detail: str, *, retry_after: float | None = None):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.retry_after = retry_after


class LLMProvider(Protocol):
    name: str  # "gemini" or "openai_compatible"
    model: str

    def next_step(self, request: ProviderRequest) -> ProviderStep: ...


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:16]}"


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) when an endpoint reports no usage."""
    return max(len(text) // 4, 1)
