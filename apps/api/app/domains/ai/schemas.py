"""Request and response schemas of the copilot API (API_CONVENTIONS.md §12.8).

Answers are ``StructuredAnswer`` documents (labelled sections plus typed record references); the
``meta`` block carries what the UI needs to label provenance and that a model never writes:
provider, fallback notice, cache reuse, prompt version, tool calls, validation flags and ``as_of``.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.ai.answer import NoteDraft, StructuredAnswer
from app.domains.ai.models import (
    ConversationContext,
    FallbackReason,
    MessageKind,
    MessageRole,
    ToolCallOrigin,
    ToolCallStatus,
)

ProviderName = Literal["gemini", "openai_compatible", "deterministic"]
QUESTION_MAX = 2000
HINT_MAX = 500


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _not_blank(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    return text


# --- requests ------------------------------------------------------------------------------------


class ConversationCreate(_Request):
    context_type: ConversationContext = ConversationContext.GENERAL
    context_id: uuid.UUID | None = Field(
        default=None, description="Required for EXCEPTION: the exception the conversation is about."
    )

    @model_validator(mode="after")
    def _context(self) -> "ConversationCreate":
        if self.context_type is ConversationContext.EXCEPTION and self.context_id is None:
            raise ValueError("context_id is required when context_type is EXCEPTION")
        if self.context_type is ConversationContext.GENERAL and self.context_id is not None:
            raise ValueError("context_id must be null when context_type is GENERAL")
        return self


class QuestionCreate(_Request):
    question: str = Field(min_length=1, max_length=QUESTION_MAX)

    _strip = field_validator("question")(_not_blank)


class ExceptionSummaryRequest(_Request):
    exception_id: uuid.UUID
    refresh: bool = Field(
        default=False, description="Bypass a cached summary (counts against rate limit and budget)."
    )


class NoteDraftRequest(_Request):
    exception_id: uuid.UUID
    user_hint: str | None = Field(
        default=None,
        max_length=HINT_MAX,
        description="The user's own account of what they did; quoted in the draft as 'Reported:'.",
    )


# --- responses -----------------------------------------------------------------------------------


class FallbackOut(BaseModel):
    used: bool
    reason: FallbackReason | None
    notice: str | None = Field(description="Shown above the answer when the live AI fell back.")


class CacheOut(BaseModel):
    hit: bool
    generated_at: datetime | None = Field(description="When a reused summary was generated.")


class ToolCallOut(BaseModel):
    tool_name: str
    status: ToolCallStatus
    origin: ToolCallOrigin
    row_count: int | None
    duration_ms: int | None


class ValidationOut(BaseModel):
    dropped_refs: int
    dropped_items: int
    flags: list[str]


class AnswerMeta(BaseModel):
    provider: ProviderName
    model: str | None
    fallback: FallbackOut
    cache: CacheOut
    prompt_version: str
    intent: str | None = Field(description="Deterministic intent the question was routed to.")
    tool_calls: list[ToolCallOut]
    validation: ValidationOut
    as_of: datetime = Field(description="The instant every number in the answer describes.")
    latency_ms: int | None
    input_tokens: int
    output_tokens: int


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    context_type: ConversationContext
    context_id: uuid.UUID | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    kind: MessageKind
    created_at: datetime
    text: str | None = Field(description="User messages: the question or action requested.")
    answer: StructuredAnswer | None = Field(description="Assistant CHAT and summary messages.")
    draft: NoteDraft | None = Field(description="Assistant NOTE_DRAFT messages.")
    meta: AnswerMeta | None = Field(description="Assistant messages only.")


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(description="Oldest first.")
    max_messages: int = Field(description="The UI asks for a new conversation at this length.")


class CopilotTurnOut(BaseModel):
    conversation_id: uuid.UUID
    user_message_id: uuid.UUID
    message_id: uuid.UUID
    answer: StructuredAnswer
    meta: AnswerMeta


class ExceptionSummaryOut(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    exception_id: uuid.UUID
    answer: StructuredAnswer
    meta: AnswerMeta


class NoteDraftOut(BaseModel):
    """A draft only. Nothing was saved: to keep it, a person with ``exceptions.work`` posts the
    (edited) body to ``POST …/exceptions/{exception_id}/notes`` with
    ``source = AI_DRAFT_ACCEPTED``."""

    conversation_id: uuid.UUID
    message_id: uuid.UUID
    exception_id: uuid.UUID
    draft: NoteDraft
    meta: AnswerMeta
