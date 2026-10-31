"""Copilot conversations, messages and tool-call execution metadata (docs/ai/AI_ARCHITECTURE.md)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, func
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


class ToolCallStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    FAILED = "FAILED"


class AIConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversation"
    __table_args__ = (Index("ix_ai_conversation_store_user", "store_id", "user_id"),)

    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    context_type: Mapped[ConversationContext] = mapped_column(
        str_enum(ConversationContext, length=16)
    )
    context_id: Mapped[uuid.UUID | None]


class AIMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_message"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversation.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole, length=16))
    # User messages: {"text": ...}. Assistant messages: the structured answer schema.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AIToolCall(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_tool_call"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_message.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[ToolCallStatus] = mapped_column(str_enum(ToolCallStatus, length=24))
    result_summary: Mapped[str | None] = mapped_column(String(500))
    row_count: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
