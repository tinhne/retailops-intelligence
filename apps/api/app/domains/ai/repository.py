"""Conversation store: the ``ai_conversation``, ``ai_message`` and ``ai_tool_call`` tables (§9).

Every query is scoped by ``store_id`` and ``user_id``, and for the shared public demo viewer also
by ``session_id`` (ADR-0011), so another user's (or another visitor's) conversation is simply
"not found".
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.domains.ai.models import (
    AIConversation,
    AIMessage,
    AIToolCall,
    ConversationContext,
    MessageKind,
    MessageRole,
)


@dataclass(frozen=True)
class Owner:
    """Whose conversations these are: a user, narrowed to one session for the demo viewer."""

    user_id: uuid.UUID
    session_id: uuid.UUID | None

    @property
    def rate_limit_key(self) -> str:
        if self.session_id is not None:
            return f"copilot:session:{self.session_id}"
        return f"copilot:user:{self.user_id}"


def _scope(store_id: uuid.UUID, owner: Owner) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [
        AIConversation.store_id == store_id,
        AIConversation.user_id == owner.user_id,
    ]
    if owner.session_id is not None:
        conditions.append(AIConversation.session_id == owner.session_id)
    else:
        conditions.append(AIConversation.session_id.is_(None))
    return conditions


def create_conversation(
    db: Session,
    *,
    store_id: uuid.UUID,
    owner: Owner,
    context_type: ConversationContext,
    context_id: uuid.UUID | None,
    title: str,
) -> AIConversation:
    conversation = AIConversation(
        id=uuid.uuid4(),
        store_id=store_id,
        user_id=owner.user_id,
        session_id=owner.session_id,
        title=title[:200],
        context_type=context_type,
        context_id=context_id,
    )
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation(
    db: Session, store_id: uuid.UUID, owner: Owner, conversation_id: uuid.UUID
) -> AIConversation:
    conversation = db.scalar(
        select(AIConversation).where(AIConversation.id == conversation_id, *_scope(store_id, owner))
    )
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    return conversation


def list_conversations(
    db: Session, store_id: uuid.UUID, owner: Owner, *, offset: int, limit: int
) -> tuple[list[tuple[AIConversation, int]], int]:
    conditions = _scope(store_id, owner)
    total = db.scalar(select(func.count()).select_from(AIConversation).where(*conditions)) or 0
    counts = (
        select(AIMessage.conversation_id, func.count().label("n"))
        .group_by(AIMessage.conversation_id)
        .subquery()
    )
    rows = db.execute(
        select(AIConversation, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.conversation_id == AIConversation.id)
        .where(*conditions)
        .order_by(AIConversation.updated_at.desc(), AIConversation.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [(conversation, int(n)) for conversation, n in rows], int(total)


def latest_exception_conversation(
    db: Session, store_id: uuid.UUID, owner: Owner, exception_id: uuid.UUID
) -> AIConversation | None:
    return db.scalar(
        select(AIConversation)
        .where(
            *_scope(store_id, owner),
            AIConversation.context_type == ConversationContext.EXCEPTION,
            AIConversation.context_id == exception_id,
        )
        .order_by(AIConversation.updated_at.desc())
        .limit(1)
    )


def message_count(db: Session, conversation_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
        )
        or 0
    )


def messages(db: Session, conversation_id: uuid.UUID) -> list[AIMessage]:
    return list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.created_at, AIMessage.role.desc(), AIMessage.id)
        ).all()
    )


def tool_calls(db: Session, message_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[AIToolCall]]:
    if not message_ids:
        return {}
    rows = db.scalars(
        select(AIToolCall)
        .where(AIToolCall.message_id.in_(message_ids))
        .order_by(AIToolCall.message_id, AIToolCall.sequence)
    ).all()
    grouped: dict[uuid.UUID, list[AIToolCall]] = {}
    for row in rows:
        grouped.setdefault(row.message_id, []).append(row)
    return grouped


def history(db: Session, conversation_id: uuid.UUID, turns: int) -> list[tuple[str, str]]:
    """The last ``turns`` chat turns as (question, assistant summary), oldest first. Earlier tool
    results are never part of the history (AI_ARCHITECTURE.md §4.1)."""
    rows = list(
        db.scalars(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation_id, AIMessage.kind == MessageKind.CHAT)
            .order_by(AIMessage.created_at.desc(), AIMessage.role, AIMessage.id.desc())
            .limit(turns * 2)
        ).all()
    )
    rows.reverse()
    pairs: list[tuple[str, str]] = []
    question: str | None = None
    for row in rows:
        if row.role is MessageRole.USER:
            question = str(row.content.get("text") or "")
        elif question is not None:
            pairs.append((question, str(row.content.get("summary") or "")))
            question = None
    return pairs[-turns:]
