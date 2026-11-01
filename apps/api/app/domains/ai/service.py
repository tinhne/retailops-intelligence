"""CopilotService: conversations, chat turns, investigation summaries and note drafts (§2, §4).

Each turn captures ``as_of`` once, runs through ``engine.run_turn`` and is persisted in one
transaction at the end: the user message, the assistant message (with provider, prompt version,
fallback reason, validation flags and token counts), every tool call, and an ``ai.tool_denied``
audit row for each permission-denied tool call. The copilot writes only its own tables: a note
draft is returned to the user and never saved here.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import ConflictError, PermissionDeniedError
from app.core.pagination import Page, PageParams
from app.domains.ai import cache, prompts, repository
from app.domains.ai.answer import NoteDraft, StructuredAnswer
from app.domains.ai.engine import StoreInfo, TurnInput, TurnResult, notice_for, run_turn
from app.domains.ai.models import (
    AIConversation,
    AIMessage,
    AIToolCall,
    ConversationContext,
    MessageKind,
    MessageRole,
)
from app.domains.ai.repository import Owner
from app.domains.ai.runtime import CopilotRuntime
from app.domains.ai.schemas import (
    AnswerMeta,
    CacheOut,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    CopilotTurnOut,
    ExceptionSummaryOut,
    ExceptionSummaryRequest,
    FallbackOut,
    MessageOut,
    NoteDraftOut,
    NoteDraftRequest,
    ProviderName,
    ToolCallOut,
    ValidationOut,
)
from app.domains.ai.tools.sanitize import clean
from app.domains.analytics import service as analytics
from app.domains.audit import service as audit
from app.domains.exceptions import repository as exceptions_repository
from app.domains.exceptions.models import OperationalException
from app.domains.identity.models import User
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext, normalize_email

logger = logging.getLogger("app.ai")

NEW_CONVERSATION_TITLE = "New conversation"
TITLE_MAX = 80


def owner_for(user: User, session_id: uuid.UUID, demo_user_email: str) -> Owner:
    """Conversations of the shared public demo viewer are private to the browser session
    (ADR-0011); everyone else's are private to the user."""
    is_demo_viewer = user.email == normalize_email(demo_user_email)
    return Owner(user.id, session_id if is_demo_viewer else None)


def store_info(db: Session, ctx: StoreContext) -> StoreInfo:
    freshness = analytics.data_freshness(db, ctx.store_id)
    applied = [i for i in freshness.imports if i.applied_at is not None]
    latest = max(applied, key=lambda i: i.applied_at or ctx.store.created_at, default=None)
    run = freshness.last_evaluation_run
    return StoreInfo(
        name=ctx.store.name,
        currency=ctx.store.currency,
        timezone=ctx.store.timezone,
        role=ctx.role.value,
        last_import_at=latest.applied_at if latest else None,
        last_import_type=latest.import_type.value if latest else None,
        last_run_as_of=run.as_of if run else None,
        last_run_trigger=run.trigger.value if run else None,
        last_run_status=run.status.value if run else None,
    )


# --- read models ---------------------------------------------------------------------------------


def _conversation_out(conversation: AIConversation, count: int) -> ConversationOut:
    return ConversationOut(
        id=conversation.id,
        title=conversation.title,
        context_type=conversation.context_type,
        context_id=conversation.context_id,
        message_count=count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _tool_out(call: AIToolCall) -> ToolCallOut:
    return ToolCallOut(
        tool_name=call.tool_name,
        status=call.status,
        origin=call.origin,
        row_count=call.row_count,
        duration_ms=call.duration_ms,
    )


def _meta(message: AIMessage, calls: list[ToolCallOut]) -> AnswerMeta:
    validation = message.validation or {}
    return AnswerMeta(
        provider=cast(ProviderName, message.provider or "deterministic"),
        model=message.model,
        fallback=FallbackOut(
            used=message.fallback_reason is not None,
            reason=message.fallback_reason,
            notice=notice_for(message.fallback_reason),
        ),
        cache=CacheOut(
            hit=message.cache_generated_at is not None, generated_at=message.cache_generated_at
        ),
        prompt_version=message.prompt_version or "",
        intent=validation.get("intent"),
        tool_calls=calls,
        validation=ValidationOut(
            dropped_refs=int(validation.get("dropped_refs") or 0),
            dropped_items=int(validation.get("dropped_items") or 0),
            flags=list(validation.get("flags") or []),
        ),
        as_of=message.as_of or message.created_at,
        latency_ms=message.latency_ms,
        input_tokens=message.input_tokens or 0,
        output_tokens=message.output_tokens or 0,
    )


def _message_out(message: AIMessage, calls: list[ToolCallOut]) -> MessageOut:
    if message.role is MessageRole.USER:
        return MessageOut(
            id=message.id,
            role=message.role,
            kind=message.kind,
            created_at=message.created_at,
            text=str(message.content.get("text") or ""),
            answer=None,
            draft=None,
            meta=None,
        )
    is_draft = message.kind is MessageKind.NOTE_DRAFT
    return MessageOut(
        id=message.id,
        role=message.role,
        kind=message.kind,
        created_at=message.created_at,
        text=None,
        answer=None if is_draft else StructuredAnswer.model_validate(message.content),
        draft=NoteDraft.model_validate(message.content) if is_draft else None,
        meta=_meta(message, calls),
    )


# --- conversations -------------------------------------------------------------------------------


def _exception(db: Session, ctx: StoreContext, exception_id: uuid.UUID) -> OperationalException:
    if not ctx.can(Permission.EXCEPTIONS_READ):
        raise PermissionDeniedError(
            "Your role does not allow this action.",
            details=[{"missing_permission": Permission.EXCEPTIONS_READ.value}],
        )
    return exceptions_repository.get_exception(db, ctx.store_id, exception_id)


def _exception_title(exc: OperationalException) -> str:
    return clean(f"{exc.reference} · {exc.title}", TITLE_MAX)


def start_conversation(
    db: Session, ctx: StoreContext, owner: Owner, body: ConversationCreate
) -> ConversationOut:
    title = NEW_CONVERSATION_TITLE
    if body.context_type is ConversationContext.EXCEPTION:
        assert body.context_id is not None  # schema-validated
        title = _exception_title(_exception(db, ctx, body.context_id))
    conversation = repository.create_conversation(
        db,
        store_id=ctx.store_id,
        owner=owner,
        context_type=body.context_type,
        context_id=body.context_id,
        title=title,
    )
    db.commit()
    return _conversation_out(conversation, 0)


def list_conversations(
    db: Session, ctx: StoreContext, owner: Owner, paging: PageParams
) -> Page[ConversationOut]:
    rows, total = repository.list_conversations(
        db, ctx.store_id, owner, offset=paging.offset, limit=paging.page_size
    )
    return Page[ConversationOut](
        items=[_conversation_out(c, n) for c, n in rows],
        page=paging.page,
        page_size=paging.page_size,
        total=total,
    )


def get_conversation(
    db: Session, ctx: StoreContext, owner: Owner, conversation_id: uuid.UUID, *, max_messages: int
) -> ConversationDetail:
    conversation = repository.get_conversation(db, ctx.store_id, owner, conversation_id)
    rows = repository.messages(db, conversation.id)
    calls = repository.tool_calls(db, [m.id for m in rows if m.role is MessageRole.ASSISTANT])
    return ConversationDetail(
        **_conversation_out(conversation, len(rows)).model_dump(),
        messages=[_message_out(m, [_tool_out(c) for c in calls.get(m.id, [])]) for m in rows],
        max_messages=max_messages,
    )


# --- turns ---------------------------------------------------------------------------------------


def _persist(
    db: Session,
    ctx: StoreContext,
    conversation: AIConversation,
    *,
    kind: MessageKind,
    user_content: dict[str, Any],
    assistant: AIMessage,
    result: TurnResult | None,
) -> tuple[AIMessage, list[ToolCallOut]]:
    """Write the turn in the caller's transaction: two messages, the tool calls, denials."""
    now = utcnow()
    user = AIMessage(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.USER,
        kind=kind,
        content=user_content,
        validation={},
        created_at=now,
    )
    assistant.id = uuid.uuid4()
    assistant.conversation_id = conversation.id
    assistant.role = MessageRole.ASSISTANT
    assistant.kind = kind
    assistant.created_at = now + timedelta(milliseconds=1)
    db.add_all([user, assistant])
    db.flush()
    calls: list[ToolCallOut] = []
    for record in result.tools.calls if result else []:
        row = AIToolCall(
            id=record.id,
            message_id=assistant.id,
            sequence=record.sequence,
            tool_name=record.tool_name,
            origin=record.origin,
            arguments=record.arguments,
            status=record.status,
            result_summary=record.summary(),
            result_refs=record.result_refs,
            row_count=record.row_count,
            duration_ms=record.duration_ms,
            error=record.error,
        )
        db.add(row)
        calls.append(_tool_out(row))
    for denial in result.tools.denied if result else []:
        audit.record(
            db,
            action="ai.tool_denied",
            organization_id=ctx.organization_id,
            actor_user_id=ctx.user.id,
            store_id=ctx.store_id,
            target_type="ai_tool",
            target_id=denial.tool_name,
            details={"tool": denial.tool_name, "missing_permissions": list(denial.missing)},
        )
    conversation.updated_at = now
    return user, calls


def _assistant_message(
    result: TurnResult, *, as_of: datetime, latency_ms: int, cache_key: str | None
) -> AIMessage:
    return AIMessage(
        content=result.content,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        as_of=as_of,
        fallback_reason=result.fallback_reason,
        cache_key=cache_key,
        validation={
            **result.report.as_json(),
            "intent": result.intent,
            "llm_requests": result.llm_requests,
        },
        latency_ms=latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


def _run(
    db: Session,
    ctx: StoreContext,
    runtime: CopilotRuntime,
    request: TurnInput,
    as_of: datetime,
) -> tuple[TurnResult, int]:
    started = time.perf_counter()
    result = run_turn(db, ctx, request, as_of=as_of, info=store_info(db, ctx), runtime=runtime)
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "copilot_turn",
        extra={
            "kind": request.kind.value,
            "provider": result.provider,
            "fallback_reason": result.fallback_reason.value if result.fallback_reason else None,
            "tool_calls": len(result.tools.calls),
            "latency_ms": latency_ms,
            "store_id": str(ctx.store_id),
        },
    )
    return result, latency_ms


def _check_length(db: Session, conversation: AIConversation, max_messages: int) -> None:
    if repository.message_count(db, conversation.id) >= max_messages:
        raise ConflictError(
            "This conversation is full. Start a new conversation.",
            code="CONVERSATION_FULL",
            details=[{"max_messages": max_messages}],
        )


def ask(
    db: Session,
    ctx: StoreContext,
    owner: Owner,
    conversation_id: uuid.UUID,
    question: str,
    runtime: CopilotRuntime,
) -> CopilotTurnOut:
    settings = runtime.settings
    conversation = repository.get_conversation(db, ctx.store_id, owner, conversation_id)
    _check_length(db, conversation, settings.ai_max_messages_per_conversation)
    runtime.limiter.hit(owner.rate_limit_key)
    history = repository.history(db, conversation.id, settings.ai_history_turns)
    as_of = runtime.clock()
    context_id = (
        conversation.context_id
        if conversation.context_type is ConversationContext.EXCEPTION
        else None
    )
    request = TurnInput(
        kind=MessageKind.CHAT, question=question, exception_id=context_id, history=tuple(history)
    )
    result, latency_ms = _run(db, ctx, runtime, request, as_of)
    assistant = _assistant_message(result, as_of=as_of, latency_ms=latency_ms, cache_key=None)
    user, calls = _persist(
        db,
        ctx,
        conversation,
        kind=MessageKind.CHAT,
        user_content={"text": question},
        assistant=assistant,
        result=result,
    )
    if conversation.title == NEW_CONVERSATION_TITLE:
        conversation.title = clean(question, TITLE_MAX)
    db.commit()
    return CopilotTurnOut(
        conversation_id=conversation.id,
        user_message_id=user.id,
        message_id=assistant.id,
        answer=StructuredAnswer.model_validate(result.content),
        meta=_meta(assistant, calls),
    )


def _exception_conversation(
    db: Session, ctx: StoreContext, owner: Owner, exc: OperationalException, max_messages: int
) -> AIConversation:
    """The caller's latest conversation about this exception, or a new one when there is none
    or it is full. Summaries and drafts live there, next to follow-up questions."""
    conversation = repository.latest_exception_conversation(db, ctx.store_id, owner, exc.id)
    if conversation is None or repository.message_count(db, conversation.id) >= max_messages:
        conversation = repository.create_conversation(
            db,
            store_id=ctx.store_id,
            owner=owner,
            context_type=ConversationContext.EXCEPTION,
            context_id=exc.id,
            title=_exception_title(exc),
        )
    return conversation


def exception_summary(
    db: Session,
    ctx: StoreContext,
    owner: Owner,
    body: ExceptionSummaryRequest,
    runtime: CopilotRuntime,
) -> ExceptionSummaryOut:
    settings = runtime.settings
    exc = _exception(db, ctx, body.exception_id)
    runtime.limiter.hit(owner.rate_limit_key)
    as_of = runtime.clock()
    user_content = {"text": "Investigation summary", "exception_id": str(exc.id)}

    key: str | None = None
    live = runtime.configured_live()
    if live is not None:
        key = cache.cache_key(
            store_id=ctx.store_id,
            exc=exc,
            last_event=cache.last_event_id(db, ctx.store_id, exc.id),
            permissions=[p.value for p in ctx.permissions],
            prompt_version=prompts.version_string(prompts.SYSTEM, prompts.INVESTIGATION_SUMMARY),
            provider=live.name,
            model=live.model,
        )
        hit = None
        if not body.refresh:
            hit = cache.find(
                db,
                store_id=ctx.store_id,
                key=key,
                now=utcnow(),
                ttl_hours=settings.ai_summary_cache_ttl_hours,
            )
        if hit is not None:
            logger.info("copilot_summary_cache_hit", extra={"exception_id": str(exc.id)})
            conversation = _exception_conversation(
                db, ctx, owner, exc, settings.ai_max_messages_per_conversation
            )
            assistant = AIMessage(
                content=hit.content,
                provider=hit.provider,
                model=hit.model,
                prompt_version=hit.prompt_version,
                as_of=hit.as_of,
                cache_generated_at=hit.created_at,
                validation=hit.validation,
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
            )
            _persist(
                db,
                ctx,
                conversation,
                kind=MessageKind.INVESTIGATION_SUMMARY,
                user_content=user_content,
                assistant=assistant,
                result=None,
            )
            db.commit()
            return ExceptionSummaryOut(
                conversation_id=conversation.id,
                message_id=assistant.id,
                exception_id=exc.id,
                answer=StructuredAnswer.model_validate(hit.content),
                meta=_meta(assistant, []),
            )

    request = TurnInput(kind=MessageKind.INVESTIGATION_SUMMARY, exception_id=exc.id)
    result, latency_ms = _run(db, ctx, runtime, request, as_of)
    conversation = _exception_conversation(
        db, ctx, owner, exc, settings.ai_max_messages_per_conversation
    )
    assistant = _assistant_message(
        result, as_of=as_of, latency_ms=latency_ms, cache_key=key if result.cacheable else None
    )
    _, calls = _persist(
        db,
        ctx,
        conversation,
        kind=MessageKind.INVESTIGATION_SUMMARY,
        user_content=user_content,
        assistant=assistant,
        result=result,
    )
    db.commit()
    return ExceptionSummaryOut(
        conversation_id=conversation.id,
        message_id=assistant.id,
        exception_id=exc.id,
        answer=StructuredAnswer.model_validate(result.content),
        meta=_meta(assistant, calls),
    )


def note_draft(
    db: Session,
    ctx: StoreContext,
    owner: Owner,
    body: NoteDraftRequest,
    runtime: CopilotRuntime,
) -> NoteDraftOut:
    """Draft a note. Nothing is saved to the exception: the person reviews, edits and saves it
    through the exception notes endpoint (``source = AI_DRAFT_ACCEPTED``)."""
    exc = _exception(db, ctx, body.exception_id)
    runtime.limiter.hit(owner.rate_limit_key)
    hint = clean(body.user_hint, 500).strip() if body.user_hint else None
    as_of = runtime.clock()
    request = TurnInput(kind=MessageKind.NOTE_DRAFT, exception_id=exc.id, user_hint=hint or None)
    result, latency_ms = _run(db, ctx, runtime, request, as_of)
    conversation = _exception_conversation(
        db, ctx, owner, exc, runtime.settings.ai_max_messages_per_conversation
    )
    assistant = _assistant_message(result, as_of=as_of, latency_ms=latency_ms, cache_key=None)
    user_content: dict[str, Any] = {"text": "Draft a note", "exception_id": str(exc.id)}
    if hint:
        user_content["user_hint"] = hint
    _, calls = _persist(
        db,
        ctx,
        conversation,
        kind=MessageKind.NOTE_DRAFT,
        user_content=user_content,
        assistant=assistant,
        result=result,
    )
    db.commit()
    return NoteDraftOut(
        conversation_id=conversation.id,
        message_id=assistant.id,
        exception_id=exc.id,
        draft=NoteDraft.model_validate(result.content),
        meta=_meta(assistant, calls),
    )
