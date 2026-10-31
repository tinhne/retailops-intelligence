"""Copilot conversations, messages and tool-call execution metadata (docs/ai/AI_ARCHITECTURE.md).

The ``ai`` module writes only these three tables. Business data is read through the allowlisted
tools (``ai/tools``) and never written.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ConversationContext(StrEnum):
    GENERAL = "GENERAL"
    EXCEPTION = "EXCEPTION"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageKind(StrEnum):
    CHAT = "CHAT"
    INVESTIGATION_SUMMARY = "INVESTIGATION_SUMMARY"
    NOTE_DRAFT = "NOTE_DRAFT"


class ToolCallStatus(StrEnum):
    """Outcome of one tool call (TOOL_CATALOG.md §1.2)."""

    SUCCESS = "SUCCESS"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    REJECTED_LIMIT = "REJECTED_LIMIT"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    ERROR = "ERROR"


class ToolCallOrigin(StrEnum):
    """Who asked for the call: the live model, the deterministic router plan, or the
    investigation ContextBuilder (AI_ARCHITECTURE.md §4.3)."""

    MODEL = "MODEL"
    ROUTER = "ROUTER"
    CONTEXT_BUILDER = "CONTEXT_BUILDER"


class FallbackReason(StrEnum):
    """Why a turn was answered by the deterministic provider instead of the live one (§8.2)."""

    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class AIConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A conversation is private to its author. For the shared public demo viewer it is also
    private to the browser session that started it (ADR-0011): ``session_id`` is set and every
    query filters by it."""

    __tablename__ = "ai_conversation"
    __table_args__ = (Index("ix_ai_conversation_store_user", "store_id", "user_id"),)

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_session.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    context_type: Mapped[ConversationContext] = mapped_column(
        str_enum(ConversationContext, length=16)
    )
    context_id: Mapped[uuid.UUID | None]


class AIMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_message"
    __table_args__ = (
        # Investigation summary cache lookups (AI_ARCHITECTURE.md §8.3).
        Index(
            "ix_ai_message_cache_key",
            "cache_key",
            "created_at",
            postgresql_where=text("cache_key IS NOT NULL"),
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversation.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole, length=16))
    kind: Mapped[MessageKind] = mapped_column(
        str_enum(MessageKind, length=32), server_default=MessageKind.CHAT.value
    )
    # User messages: {"text": ...}. Assistant messages: the structured answer, or a note draft.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(200))
    as_of: Mapped[datetime | None]
    fallback_reason: Mapped[FallbackReason | None] = mapped_column(
        str_enum(FallbackReason, length=32)
    )
    # Set on validated live-model investigation summaries only; see ai/cache.py.
    cache_key: Mapped[str | None] = mapped_column(String(64))
    # Set when this answer reuses a cached summary: when the original was generated.
    cache_generated_at: Mapped[datetime | None]
    # {"dropped_refs": n, "dropped_items": n, "flags": [...]} from the AnswerValidator.
    validation: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AIToolCall(UUIDPrimaryKeyMixin, Base):
    """One tool call, whatever its outcome. Full results are never stored: only the row count,
    the truncation flag and the reference keys the result contained."""

    __tablename__ = "ai_tool_call"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_message.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, server_default="0")
    tool_name: Mapped[str] = mapped_column(String(64))
    origin: Mapped[ToolCallOrigin] = mapped_column(
        str_enum(ToolCallOrigin, length=24), server_default=ToolCallOrigin.MODEL.value
    )
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[ToolCallStatus] = mapped_column(str_enum(ToolCallStatus, length=24))
    result_summary: Mapped[str | None] = mapped_column(String(500))
    result_refs: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    row_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
