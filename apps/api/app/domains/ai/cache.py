"""Investigation summary cache (AI_ARCHITECTURE.md §8.3).

A validated live-model summary is reused while nothing about the exception changed, so several
people opening the same P1 exception cost one LLM request. The key covers everything the summary
depends on:

- ``evidence_hash``: SHA-256 of the canonical evidence, calculation, severity, status, assignee,
  priority score and band, and due date. Any evaluation that changes the snapshot changes it.
- ``last_event_id``: a new note, assignment, status change or reopen invalidates the entry.
- ``permission_set_hash``: entries are only shared between identical permission sets.
- prompt version, provider and model.

Storage is the original ``ai_message`` (``kind = INVESTIGATION_SUMMARY``) with its ``cache_key``;
there is no cache table and no external cache service. Deterministic summaries are never cached.
"""

import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.ai.models import AIConversation, AIMessage, MessageKind, MessageRole
from app.domains.exceptions.models import ExceptionEvent, OperationalException
from app.domains.exceptions.rules.base import jsonable


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(jsonable(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def evidence_hash(exc: OperationalException) -> str:
    return _sha(
        {
            "evidence": exc.evidence,
            "calculation": exc.calculation,
            "severity": exc.severity,
            "status": exc.status,
            "assignee_id": exc.assignee_id,
            "priority_score": exc.priority_score,
            "priority_band": exc.priority_band,
            "due_at": exc.due_at,
        }
    )


def last_event_id(db: Session, store_id: uuid.UUID, exception_id: uuid.UUID) -> str | None:
    event_id = db.scalar(
        select(ExceptionEvent.id)
        .where(ExceptionEvent.store_id == store_id, ExceptionEvent.exception_id == exception_id)
        .order_by(ExceptionEvent.occurred_at.desc(), ExceptionEvent.id.desc())
        .limit(1)
    )
    return str(event_id) if event_id else None


def permission_set_hash(permissions: Iterable[str]) -> str:
    return _sha(sorted(str(p) for p in permissions))


def cache_key(
    *,
    store_id: uuid.UUID,
    exc: OperationalException,
    last_event: str | None,
    permissions: Iterable[str],
    prompt_version: str,
    provider: str,
    model: str,
) -> str:
    return _sha(
        {
            "store_id": store_id,
            "exception_id": exc.id,
            "evidence_hash": evidence_hash(exc),
            "last_event_id": last_event,
            "permission_set_hash": permission_set_hash(permissions),
            "prompt_version": prompt_version,
            "provider": provider,
            "model": model,
        }
    )


def find(
    db: Session, *, store_id: uuid.UUID, key: str, now: datetime, ttl_hours: int
) -> AIMessage | None:
    """The newest cached summary with this key, scoped to the store, within the TTL."""
    return db.scalar(
        select(AIMessage)
        .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
        .where(
            AIConversation.store_id == store_id,
            AIMessage.cache_key == key,
            AIMessage.role == MessageRole.ASSISTANT,
            AIMessage.kind == MessageKind.INVESTIGATION_SUMMARY,
            AIMessage.created_at >= now - timedelta(hours=ttl_hours),
        )
        .order_by(AIMessage.created_at.desc())
        .limit(1)
    )
