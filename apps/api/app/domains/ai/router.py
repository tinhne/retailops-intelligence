"""HTTP endpoints of the copilot (API_CONVENTIONS.md §12.8, AI_ARCHITECTURE.md §2.1).

Every route needs ``copilot.use``; investigation summaries also need ``exceptions.read`` and note
drafts ``exceptions.work`` (a draft the caller could not save would be a fake control). The store
comes from the path and is checked against the caller's membership (another store → 404).
Conversations are private: another user's conversation id returns 404, and the shared demo
viewer's conversations are private to the browser session. Chat, summaries and drafts count
against the per-principal copilot rate limit (``COPILOT_RATE_LIMIT_PER_MINUTE``, 429).
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, require_permission
from app.core.config import Settings, get_settings
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.ai import service
from app.domains.ai.repository import Owner
from app.domains.ai.runtime import CopilotRuntime, runtime_for
from app.domains.ai.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    CopilotTurnOut,
    ExceptionSummaryOut,
    ExceptionSummaryRequest,
    NoteDraftOut,
    NoteDraftRequest,
    QuestionCreate,
)
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

router = APIRouter(prefix="/stores/{store_id}/copilot", tags=["copilot"])

_USE = require_permission(Permission.COPILOT_USE)
_SUMMARY = require_permission(Permission.COPILOT_USE, Permission.EXCEPTIONS_READ)
_DRAFT = require_permission(Permission.COPILOT_USE, Permission.EXCEPTIONS_WORK)


def copilot_runtime(request: Request, settings: Settings = Depends(get_settings)) -> CopilotRuntime:
    return runtime_for(request.app.state, settings)


def owner(
    principal: Principal = Depends(get_principal), settings: Settings = Depends(get_settings)
) -> Owner:
    return service.owner_for(principal.user, principal.session.id, settings.demo_user_email)


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(_USE),
    who: Owner = Depends(owner),
    db: Session = Depends(get_db),
) -> Page[ConversationOut]:
    """The caller's own conversations in this store, most recently active first."""
    return service.list_conversations(db, ctx, who, paging)


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def start_conversation(
    body: ConversationCreate,
    ctx: StoreContext = Depends(_USE),
    who: Owner = Depends(owner),
    db: Session = Depends(get_db),
) -> ConversationOut:
    """Start a conversation. ``EXCEPTION`` conversations (``context_id`` = exception id) also need
    ``exceptions.read``; questions that name no other record bind to that exception."""
    return service.start_conversation(db, ctx, who, body)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    ctx: StoreContext = Depends(_USE),
    who: Owner = Depends(owner),
    runtime: CopilotRuntime = Depends(copilot_runtime),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """One of the caller's conversations with its messages (404 for anyone else's)."""
    return service.get_conversation(
        db,
        ctx,
        who,
        conversation_id,
        max_messages=runtime.settings.ai_max_messages_per_conversation,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=CopilotTurnOut,
    status_code=status.HTTP_201_CREATED,
)
def ask(
    conversation_id: uuid.UUID,
    body: QuestionCreate,
    ctx: StoreContext = Depends(_USE),
    who: Owner = Depends(owner),
    runtime: CopilotRuntime = Depends(copilot_runtime),
    db: Session = Depends(get_db),
) -> CopilotTurnOut:
    """Ask a question (one turn). Returns the structured answer and its provenance. When the live
    provider is unavailable the rule-based assistant answers and ``meta.fallback`` says why.
    409 ``CONVERSATION_FULL`` after ``max_messages``; 429 when the copilot rate limit is hit."""
    return service.ask(db, ctx, who, conversation_id, body.question, runtime)


@router.post("/exception-summaries", response_model=ExceptionSummaryOut)
def exception_summary(
    body: ExceptionSummaryRequest,
    ctx: StoreContext = Depends(_SUMMARY),
    who: Owner = Depends(owner),
    runtime: CopilotRuntime = Depends(copilot_runtime),
    db: Session = Depends(get_db),
) -> ExceptionSummaryOut:
    """Investigation summary of one exception. A validated live-model summary is reused while the
    exception's evidence and history are unchanged (``meta.cache``); ``refresh`` bypasses it."""
    return service.exception_summary(db, ctx, who, body, runtime)


@router.post("/note-drafts", response_model=NoteDraftOut)
def note_draft(
    body: NoteDraftRequest,
    ctx: StoreContext = Depends(_DRAFT),
    who: Owner = Depends(owner),
    runtime: CopilotRuntime = Depends(copilot_runtime),
    db: Session = Depends(get_db),
) -> NoteDraftOut:
    """Draft a work note for an exception. Nothing is saved: to keep it, the person posts the
    (edited) body to ``POST /stores/{store_id}/exceptions/{exception_id}/notes`` with
    ``source = AI_DRAFT_ACCEPTED``."""
    return service.note_draft(db, ctx, who, body, runtime)
