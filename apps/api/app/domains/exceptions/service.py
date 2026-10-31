"""Exceptions service: queries, lifecycle actions and evaluation runs (STATE_MACHINES.md §3).

Every lifecycle action follows the same unit of work: lock the exception row (``SELECT … FOR
UPDATE``), compare ``expected_version``, validate the action with ``lifecycle.check_action``,
apply the change, write the exception event(s), assignment history and an audit row, and commit.
``version`` is incremented by the ORM whenever an action writes an event.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, case, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolationError, ConflictError, NotFoundError
from app.domains.audit import service as audit
from app.domains.audit.models import AuditLog
from app.domains.exceptions import engine, repository
from app.domains.exceptions.lifecycle import (
    Actor,
    ExceptionAction,
    ExceptionState,
    StaleVersionError,
    available_actions,
    check_action,
    validate_closing_note,
    validate_resolution_code,
)
from app.domains.exceptions.models import (
    ACTIVE_STATUSES,
    ActorType,
    DismissalReason,
    EntityType,
    EvaluationRun,
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionAssignment,
    ExceptionCategory,
    ExceptionEntityLink,
    ExceptionEvent,
    ExceptionEventType,
    ExceptionNote,
    ExceptionStatus,
    ExceptionType,
    LinkRole,
    NoteSource,
    OperationalException,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.exceptions.priority import (
    PriorityInputs,
    PriorityWeights,
    compute_due_at,
    compute_priority,
)
from app.domains.exceptions.rules.base import jsonable
from app.domains.exceptions.schemas import (
    BlockedActionOut,
    DismissalOut,
    EntityLinkOut,
    EntityRefOut,
    EvaluationRunOut,
    ExceptionDetail,
    ExceptionEventOut,
    ExceptionListItem,
    ExceptionNoteOut,
    ExceptionRef,
    ResolutionOut,
    UserRef,
)
from app.domains.exceptions.snapshot import load_settings
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

E = OperationalException

# --- listing -------------------------------------------------------------------------------------

SORT_FIELDS: dict[str, Any] = {
    "priority_score": E.priority_score,
    "due_at": E.due_at,
    "first_detected_at": E.first_detected_at,
    "last_detected_at": E.last_detected_at,
}
DEFAULT_SORT = "-priority_score"
RUN_SORT_FIELDS: dict[str, Any] = {
    "started_at": EvaluationRun.started_at,
    "as_of": EvaluationRun.as_of,
}


@dataclass(frozen=True)
class ExceptionFilters:
    statuses: Sequence[ExceptionStatus] | None = None  # None → active statuses
    severities: Sequence[Severity] | None = None
    exception_types: Sequence[ExceptionType] | None = None
    categories: Sequence[ExceptionCategory] | None = None
    priority_bands: Sequence[PriorityBand] | None = None
    assignee: str | None = None  # "me" | "unassigned" | user UUID
    product_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    q: str | None = None
    due_to: datetime | None = None  # due_at <= due_to (overdue or due soon)


def _order_by(sort: str, fields: dict[str, Any]) -> tuple[str, Any]:
    descending = sort.startswith("-")
    name = sort[1:] if descending else sort
    column = fields.get(name)
    if column is None:
        raise BusinessRuleViolationError(
            "Unsupported sort field.",
            code="INVALID_SORT",
            details=[{"sort": sort, "allowed": sorted(fields) + [f"-{f}" for f in sorted(fields)]}],
        )
    return name, column.desc() if descending else column.asc()


def _linked(entity_type: EntityType, entity_id: uuid.UUID, store_id: uuid.UUID) -> Any:
    return exists().where(
        ExceptionEntityLink.exception_id == E.id,
        ExceptionEntityLink.store_id == store_id,
        ExceptionEntityLink.entity_type == entity_type,
        ExceptionEntityLink.entity_id == entity_id,
    )


def _filter_conditions(
    store_id: uuid.UUID, user_id: uuid.UUID, filters: ExceptionFilters
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [E.store_id == store_id]
    statuses = list(filters.statuses) if filters.statuses else list(ACTIVE_STATUSES)
    conditions.append(E.status.in_(statuses))
    if filters.severities:
        conditions.append(E.severity.in_(list(filters.severities)))
    if filters.exception_types:
        conditions.append(E.exception_type.in_(list(filters.exception_types)))
    if filters.categories:
        conditions.append(E.category.in_(list(filters.categories)))
    if filters.priority_bands:
        conditions.append(E.priority_band.in_(list(filters.priority_bands)))
    if filters.assignee:
        value = filters.assignee.strip().lower()
        if value == "me":
            conditions.append(E.assignee_id == user_id)
        elif value == "unassigned":
            conditions.append(E.assignee_id.is_(None))
        else:
            try:
                conditions.append(E.assignee_id == uuid.UUID(value))
            except ValueError as exc:
                raise BusinessRuleViolationError(
                    "assignee must be 'me', 'unassigned' or a user id.",
                    code="VALIDATION_FAILED",
                    details=[{"loc": ["query", "assignee"], "message": "invalid assignee filter"}],
                ) from exc
    if filters.product_id:
        conditions.append(_linked(EntityType.PRODUCT, filters.product_id, store_id))
    if filters.order_id:
        conditions.append(_linked(EntityType.ORDER, filters.order_id, store_id))
    if filters.due_to is not None:
        if filters.due_to.tzinfo is None:
            raise BusinessRuleViolationError(
                "due_to must include a time zone offset.",
                code="VALIDATION_FAILED",
                details=[{"loc": ["query", "due_to"], "message": "naive datetime"}],
            )
        conditions.append(E.due_at <= filters.due_to)
    if filters.q and filters.q.strip():
        term = filters.q.strip()
        conditions.append(
            or_(
                E.reference.icontains(term, autoescape=True),
                E.title.icontains(term, autoescape=True),
            )
        )
    return conditions


def list_exceptions(
    db: Session,
    store_id: uuid.UUID,
    *,
    current_user_id: uuid.UUID,
    filters: ExceptionFilters,
    sort: str = DEFAULT_SORT,
    offset: int = 0,
    limit: int = 25,
    now: datetime,
) -> tuple[list[ExceptionListItem], int]:
    """Exceptions of one store with filters and an allowlisted sort."""
    conditions = _filter_conditions(store_id, current_user_id, filters)
    name, primary = _order_by(sort, SORT_FIELDS)
    tie_breakers: list[Any] = (
        [E.due_at.asc(), E.first_detected_at.asc(), E.reference.asc()]
        if name == "priority_score"
        else [E.priority_score.desc(), E.reference.asc()]
    )
    total = db.scalar(select(func.count()).select_from(E).where(*conditions)) or 0
    rows = db.scalars(
        select(E)
        .where(*conditions)
        .order_by(primary, *tie_breakers, E.id)
        .offset(offset)
        .limit(limit)
    ).all()
    labels = _Labels.load(db, store_id, rows)
    return [_list_item(exc, labels, now) for exc in rows], total


# --- labels and DTO assembly ---------------------------------------------------------------------


@dataclass
class _Labels:
    users: dict[uuid.UUID, str] = field(default_factory=dict)
    products: dict[uuid.UUID, tuple[str, str]] = field(default_factory=dict)
    orders: dict[uuid.UUID, str] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        db: Session,
        store_id: uuid.UUID,
        exceptions: Iterable[OperationalException],
        *,
        links: Iterable[ExceptionEntityLink] = (),
        extra_users: Iterable[uuid.UUID | None] = (),
    ) -> "_Labels":
        excs = list(exceptions)
        entities = [(e.primary_entity_type, e.primary_entity_id) for e in excs]
        entities += [(link.entity_type, link.entity_id) for link in links]
        product_ids = [eid for etype, eid in entities if etype is EntityType.PRODUCT]
        order_ids = [eid for etype, eid in entities if etype is EntityType.ORDER]
        user_ids: list[uuid.UUID | None] = [e.assignee_id for e in excs]
        user_ids += [e.resolved_by for e in excs]
        user_ids += list(extra_users)
        return cls(
            users=repository.user_names(db, user_ids),
            products=repository.product_labels(db, store_id, product_ids),
            orders=repository.order_labels(db, store_id, order_ids),
        )

    def user(self, user_id: uuid.UUID | None) -> UserRef | None:
        if user_id is None:
            return None
        return UserRef(id=user_id, full_name=self.users.get(user_id, "Former user"))

    def entity(self, entity_type: EntityType, entity_id: uuid.UUID) -> tuple[str, str | None]:
        if entity_type is EntityType.PRODUCT:
            sku, name = self.products.get(entity_id, ("(unknown product)", ""))
            return sku, name or None
        return self.orders.get(entity_id, "(unknown order)"), None


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _list_item(exc: OperationalException, labels: _Labels, now: datetime) -> ExceptionListItem:
    label, name = labels.entity(exc.primary_entity_type, exc.primary_entity_id)
    return ExceptionListItem(
        id=exc.id,
        reference=exc.reference,
        exception_type=exc.exception_type,
        category=exc.category,
        status=exc.status,
        severity=exc.severity,
        priority_score=exc.priority_score,
        priority_band=exc.priority_band,
        title=exc.title,
        primary_entity=EntityRefOut(
            type=exc.primary_entity_type, id=exc.primary_entity_id, label=label, name=name
        ),
        assignee=labels.user(exc.assignee_id),
        exposure_amount=exc.exposure_amount,
        affected_order_count=exc.affected_order_count,
        deadline_at=exc.deadline_at,
        due_at=exc.due_at,
        due_at_overridden=exc.due_at_overridden,
        is_past_due=exc.status in ACTIVE_STATUSES and exc.due_at < now,
        first_detected_at=exc.first_detected_at,
        last_detected_at=exc.last_detected_at,
        detection_count=exc.detection_count,
        age_hours=max(int((now - exc.first_detected_at).total_seconds() // 3600), 0),
        reopen_count=exc.reopen_count,
        version=exc.version,
    )


def _ref(exc: OperationalException | None) -> ExceptionRef | None:
    if exc is None:
        return None
    return ExceptionRef(
        id=exc.id,
        reference=exc.reference,
        exception_type=exc.exception_type,
        status=exc.status,
        title=exc.title,
    )


def _actor(ctx: StoreContext) -> Actor:
    return Actor(user_id=ctx.user.id, permissions=ctx.permissions)


def _state(db: Session, exc: OperationalException) -> ExceptionState:
    other = None
    if exc.status not in ACTIVE_STATUSES:
        other = repository.other_active_occurrence(db, exc.store_id, exc.dedup_key, exc.id)
    return ExceptionState(
        status=exc.status,
        assignee_id=exc.assignee_id,
        resolution_code=exc.resolution_code,
        active_occurrence_id=other.id if other else None,
        active_occurrence_reference=other.reference if other else None,
    )


def get_exception_detail(
    db: Session, ctx: StoreContext, exception_id: uuid.UUID, *, now: datetime
) -> ExceptionDetail:
    exc = repository.get_exception(db, ctx.store_id, exception_id)
    links = db.scalars(
        select(ExceptionEntityLink)
        .where(
            ExceptionEntityLink.store_id == ctx.store_id,
            ExceptionEntityLink.exception_id == exc.id,
        )
        .order_by(
            case((ExceptionEntityLink.role == LinkRole.PRIMARY, 0), else_=1),
            ExceptionEntityLink.entity_type,
            ExceptionEntityLink.entity_id,
        )
    ).all()
    related_ids = [i for i in (exc.superseded_by_id, exc.previous_occurrence_id) if i is not None]
    related = {
        r.id: r
        for r in db.scalars(
            select(E).where(E.store_id == ctx.store_id, E.id.in_(related_ids))
        ).all()
    }
    supersedes = db.scalars(
        select(E)
        .where(E.store_id == ctx.store_id, E.superseded_by_id == exc.id)
        .order_by(E.first_detected_at)
    ).all()
    dismissal_event = None
    if exc.status is ExceptionStatus.DISMISSED:
        dismissal_event = db.scalar(
            select(ExceptionEvent)
            .where(
                ExceptionEvent.store_id == ctx.store_id,
                ExceptionEvent.exception_id == exc.id,
                ExceptionEvent.to_status == ExceptionStatus.DISMISSED,
            )
            .order_by(ExceptionEvent.occurred_at.desc())
            .limit(1)
        )
    labels = _Labels.load(
        db,
        ctx.store_id,
        [exc],
        links=links,
        extra_users=[dismissal_event.actor_id if dismissal_event else None],
    )
    base = _list_item(exc, labels, now)
    allowed, blocked = available_actions(_state(db, exc), _actor(ctx))

    resolution = None
    if exc.status is ExceptionStatus.RESOLVED:
        resolution = ResolutionOut(
            resolved_at=exc.resolved_at,
            resolved_by=labels.user(exc.resolved_by),
            resolution_actor=exc.resolution_actor,
            resolution_code=exc.resolution_code,
            resolution_note=exc.resolution_note,
            verified_at=exc.verified_at,
        )
    dismissal = None
    if exc.status is ExceptionStatus.DISMISSED:
        dismissal = DismissalOut(
            dismissed_reason=exc.dismissed_reason,
            note=exc.resolution_note,
            dismissed_at=dismissal_event.occurred_at if dismissal_event else None,
            dismissed_by=labels.user(dismissal_event.actor_id if dismissal_event else None),
            condition_cleared_at=exc.condition_cleared_at,
        )
    link_out = []
    for link in links:
        label, name = labels.entity(link.entity_type, link.entity_id)
        link_out.append(
            EntityLinkOut(
                entity_type=link.entity_type,
                entity_id=link.entity_id,
                role=link.role,
                label=label,
                name=name,
            )
        )
    return ExceptionDetail(
        **base.model_dump(),
        rule_id=exc.rule_id,
        dedup_key=exc.dedup_key,
        priority_breakdown=exc.priority_breakdown,
        evidence=exc.evidence,
        calculation=exc.calculation,
        recommended_action=exc.recommended_action,
        links=link_out,
        resolution=resolution,
        dismissal=dismissal,
        superseded_by=_ref(related.get(exc.superseded_by_id) if exc.superseded_by_id else None),
        supersedes=[r for r in (_ref(s) for s in supersedes) if r is not None],
        previous_occurrence=_ref(
            related.get(exc.previous_occurrence_id) if exc.previous_occurrence_id else None
        ),
        available_actions=allowed,
        blocked_actions=[
            BlockedActionOut(action=b.action, code=b.code, reason=b.reason) for b in blocked
        ],
        created_at=exc.created_at,
        updated_at=exc.updated_at,
    )


# Events that share a timestamp are listed in causal order.
_EVENT_ORDER = {
    ExceptionEventType.DETECTED: 0,
    ExceptionEventType.REOPENED: 1,
    ExceptionEventType.ASSIGNED: 2,
    ExceptionEventType.UNASSIGNED: 3,
    ExceptionEventType.STATUS_CHANGED: 4,
    ExceptionEventType.AUTO_RESOLVED: 5,
    ExceptionEventType.SUPERSEDED: 6,
    ExceptionEventType.VERIFIED: 7,
    ExceptionEventType.SEVERITY_CHANGED: 8,
    ExceptionEventType.EVIDENCE_UPDATED: 9,
    ExceptionEventType.DUE_DATE_CHANGED: 10,
    ExceptionEventType.NOTE_ADDED: 11,
}


def list_events(
    db: Session, ctx: StoreContext, exception_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[ExceptionEventOut], int]:
    exc = repository.get_exception(db, ctx.store_id, exception_id)
    where = (ExceptionEvent.store_id == ctx.store_id, ExceptionEvent.exception_id == exc.id)
    total = db.scalar(select(func.count()).select_from(ExceptionEvent).where(*where)) or 0
    ordinal = case(
        *[(ExceptionEvent.event_type == t, n) for t, n in _EVENT_ORDER.items()], else_=99
    )
    events = db.scalars(
        select(ExceptionEvent)
        .where(*where)
        .order_by(ExceptionEvent.occurred_at, ordinal, ExceptionEvent.id)
        .offset(offset)
        .limit(limit)
    ).all()
    names = repository.user_names(db, [e.actor_id for e in events])
    return [
        ExceptionEventOut(
            id=e.id,
            event_type=e.event_type,
            actor_type=e.actor_type,
            actor=(
                UserRef(id=e.actor_id, full_name=names.get(e.actor_id, "Former user"))
                if e.actor_id
                else None
            ),
            evaluation_run_id=e.evaluation_run_id,
            from_status=e.from_status,
            to_status=e.to_status,
            payload=e.payload,
            occurred_at=e.occurred_at,
        )
        for e in events
    ], total


def _note_out(note: ExceptionNote, names: dict[uuid.UUID, str]) -> ExceptionNoteOut:
    author = None
    if note.author_id is not None:
        author = UserRef(id=note.author_id, full_name=names.get(note.author_id, "Former user"))
    return ExceptionNoteOut(
        id=note.id, body=note.body, source=note.source, author=author, created_at=note.created_at
    )


def list_notes(
    db: Session, ctx: StoreContext, exception_id: uuid.UUID, *, offset: int, limit: int
) -> tuple[list[ExceptionNoteOut], int]:
    exc = repository.get_exception(db, ctx.store_id, exception_id)
    where = (ExceptionNote.store_id == ctx.store_id, ExceptionNote.exception_id == exc.id)
    total = db.scalar(select(func.count()).select_from(ExceptionNote).where(*where)) or 0
    notes = db.scalars(
        select(ExceptionNote)
        .where(*where)
        .order_by(ExceptionNote.created_at, ExceptionNote.id)
        .offset(offset)
        .limit(limit)
    ).all()
    names = repository.user_names(db, [n.author_id for n in notes])
    return [_note_out(n, names) for n in notes], total


# --- lifecycle actions ---------------------------------------------------------------------------


def _lock(
    db: Session, ctx: StoreContext, exception_id: uuid.UUID, expected_version: int | None
) -> OperationalException:
    """Lock the row, then compare the client's version (409 STALE_VERSION on mismatch)."""
    exc = repository.get_exception(db, ctx.store_id, exception_id, for_update=True)
    if expected_version is not None and expected_version != exc.version:
        raise StaleVersionError(
            "This exception changed since you loaded it. Reload to see the latest.",
            details=[{"current_version": exc.version, "expected_version": expected_version}],
        )
    return exc


def _check(
    db: Session, ctx: StoreContext, exc: OperationalException, action: ExceptionAction
) -> None:
    denial = check_action(action, _state(db, exc), _actor(ctx))
    if denial is not None:
        raise denial.to_error()


def _lock_and_check(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    action: ExceptionAction,
    expected_version: int | None,
) -> OperationalException:
    exc = _lock(db, ctx, exception_id, expected_version)
    _check(db, ctx, exc, action)
    return exc


def _user_event(
    db: Session,
    ctx: StoreContext,
    exc: OperationalException,
    event_type: ExceptionEventType,
    now: datetime,
    *,
    from_status: ExceptionStatus | None = None,
    to_status: ExceptionStatus | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        ExceptionEvent(
            exception_id=exc.id,
            store_id=ctx.store_id,
            event_type=event_type,
            actor_type=ActorType.USER,
            actor_id=ctx.user.id,
            evaluation_run_id=None,
            from_status=from_status,
            to_status=to_status,
            payload=jsonable(payload or {}),
            occurred_at=now,
        )
    )


def _audit(
    db: Session,
    ctx: StoreContext,
    exc: OperationalException,
    action: str,
    details: dict[str, Any],
) -> None:
    audit.record(
        db,
        action=action,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        store_id=ctx.store_id,
        target_type="exception",
        target_id=exc.id,
        details=jsonable({"reference": exc.reference, **details}),
    )


def _change_status(
    db: Session,
    ctx: StoreContext,
    exc: OperationalException,
    target: ExceptionStatus,
    now: datetime,
    payload: dict[str, Any] | None = None,
) -> ExceptionStatus:
    from_status = exc.status
    exc.status = target
    _user_event(
        db,
        ctx,
        exc,
        ExceptionEventType.STATUS_CHANGED,
        now,
        from_status=from_status,
        to_status=target,
        payload=payload,
    )
    return from_status


def _assign(
    db: Session,
    ctx: StoreContext,
    exc: OperationalException,
    assignee_id: uuid.UUID | None,
    now: datetime,
    reason: str,
) -> None:
    """Change the assignee: close the open assignment row, open a new one, write the event."""
    previous = exc.assignee_id
    db.execute(
        update(ExceptionAssignment)
        .where(
            ExceptionAssignment.exception_id == exc.id,
            ExceptionAssignment.unassigned_at.is_(None),
        )
        .values(unassigned_at=now)
        .execution_options(synchronize_session=False)
    )
    exc.assignee_id = assignee_id
    if assignee_id is None:
        _user_event(
            db,
            ctx,
            exc,
            ExceptionEventType.UNASSIGNED,
            now,
            payload={"previous_assignee_id": previous, "reason": reason},
        )
        return
    db.add(
        ExceptionAssignment(
            exception_id=exc.id, assignee_id=assignee_id, assigned_by=ctx.user.id, assigned_at=now
        )
    )
    _user_event(
        db,
        ctx,
        exc,
        ExceptionEventType.ASSIGNED,
        now,
        payload={"assignee_id": assignee_id, "previous_assignee_id": previous, "reason": reason},
    )


def _finish(
    db: Session, ctx: StoreContext, exc: OperationalException, now: datetime
) -> ExceptionDetail:
    db.commit()
    return get_exception_detail(db, ctx, exc.id, now=now)


def acknowledge(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.ACKNOWLEDGE, expected_version)
    from_status = _change_status(db, ctx, exc, ExceptionStatus.ACKNOWLEDGED, now)
    _audit(db, ctx, exc, "exception.acknowledge", {"from_status": from_status})
    return _finish(db, ctx, exc, now)


def start(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    """``* → IN_PROGRESS``. An unassigned exception is assigned to the actor; an exception
    assigned to someone else keeps its assignee (only users who may reassign get this far)."""
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.START, expected_version)
    auto_assigned = exc.assignee_id is None
    if auto_assigned:
        _assign(db, ctx, exc, ctx.user.id, now, reason="AUTO_ON_START")
    from_status = _change_status(db, ctx, exc, ExceptionStatus.IN_PROGRESS, now)
    _audit(
        db,
        ctx,
        exc,
        "exception.start",
        {
            "from_status": from_status,
            "assignee_id": exc.assignee_id,
            "auto_assigned": auto_assigned,
        },
    )
    return _finish(db, ctx, exc, now)


def resolve(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    resolution_code: ResolutionCode,
    resolution_note: str,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    code = validate_resolution_code(resolution_code)
    note = validate_closing_note(resolution_note, "resolution_note")
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.RESOLVE, expected_version)
    exc.resolved_at = now
    exc.resolved_by = ctx.user.id
    exc.resolution_actor = ActorType.USER
    exc.resolution_code = code
    exc.resolution_note = note
    exc.verified_at = None
    from_status = _change_status(
        db,
        ctx,
        exc,
        ExceptionStatus.RESOLVED,
        now,
        payload={"resolution_code": code, "resolution_note": note},
    )
    _audit(
        db,
        ctx,
        exc,
        "exception.resolve",
        {"from_status": from_status, "resolution_code": code},
    )
    return _finish(db, ctx, exc, now)


def dismiss(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    dismissal_reason: DismissalReason,
    note: str,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    text = validate_closing_note(note, "note")
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.DISMISS, expected_version)
    exc.dismissed_reason = dismissal_reason
    exc.resolution_note = text  # the closing note of a dismissal
    exc.condition_cleared_at = None
    from_status = _change_status(
        db,
        ctx,
        exc,
        ExceptionStatus.DISMISSED,
        now,
        payload={"dismissal_reason": dismissal_reason, "note": text},
    )
    _audit(
        db,
        ctx,
        exc,
        "exception.dismiss",
        {"from_status": from_status, "dismissal_reason": dismissal_reason},
    )
    return _finish(db, ctx, exc, now)


def reopen(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    reason: str,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    """Manual ``RESOLVED/DISMISSED → REOPENED`` (exceptions.manage). A new response cycle starts:
    the due date is recalculated from now and any manual override is cleared."""
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.REOPEN, expected_version)
    from_status = exc.status
    previous_resolution = {
        "status": exc.status,
        "resolved_at": exc.resolved_at,
        "resolved_by": exc.resolved_by,
        "resolution_code": exc.resolution_code,
        "resolution_note": exc.resolution_note,
        "dismissed_reason": exc.dismissed_reason,
    }
    due_before = exc.due_at
    due = compute_due_at(exc.severity, now, exc.deadline_at)
    settings = load_settings(db, ctx.store_id)
    priority = compute_priority(
        PriorityInputs(
            severity=exc.severity,
            affected_order_count=exc.affected_order_count,
            exposure_amount=exc.exposure_amount,
            deadline_at=exc.deadline_at,
            first_detected_at=exc.first_detected_at,
        ),
        weights=PriorityWeights.from_settings(settings.priority_weights),
        exposure_cap=settings.exposure_cap,
        as_of=now,
    )
    exc.status = ExceptionStatus.REOPENED
    exc.reopen_count = exc.reopen_count + 1
    exc.resolved_at = None
    exc.resolved_by = None
    exc.resolution_actor = None
    exc.resolution_code = None
    exc.resolution_note = None
    exc.verified_at = None
    exc.dismissed_reason = None
    exc.condition_cleared_at = None
    exc.due_at = due.due_at
    exc.due_at_overridden = False
    exc.priority_score = priority.score
    exc.priority_band = priority.band
    exc.priority_breakdown = {**priority.breakdown, "due": due.as_json()}
    _user_event(
        db,
        ctx,
        exc,
        ExceptionEventType.REOPENED,
        now,
        from_status=from_status,
        to_status=ExceptionStatus.REOPENED,
        payload={
            "reason": "MANUAL",
            "note": reason,
            "previous_resolution": previous_resolution,
            "due_date_changed": {
                "from": due_before,
                "to": due.due_at,
                "basis": due.basis,
                "override_cleared": True,
            },
        },
    )
    _audit(db, ctx, exc, "exception.reopen", {"from_status": from_status, "reason": reason})
    try:
        db.flush()
    except IntegrityError as err:  # a newer occurrence became active concurrently
        db.rollback()
        raise ConflictError(
            "A newer occurrence of this condition is already active.",
            code="EXCEPTION_NEWER_OCCURRENCE_EXISTS",
        ) from err
    return _finish(db, ctx, exc, now)


def add_note(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    body: str,
    expected_version: int | None,
    now: datetime,
    source: NoteSource = NoteSource.USER,
) -> ExceptionNoteOut:
    """Append a note (any status). ``source`` is AI_DRAFT_ACCEPTED only after a person accepts
    an AI draft."""
    text = body.strip()
    if not text:
        raise BusinessRuleViolationError(
            "The note must not be blank.",
            code="VALIDATION_FAILED",
            details=[{"loc": ["body", "body"], "message": "blank note"}],
        )
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.ADD_NOTE, expected_version)
    note = ExceptionNote(
        id=uuid.uuid4(),
        exception_id=exc.id,
        store_id=ctx.store_id,
        author_id=ctx.user.id,
        body=text,
        source=source,
        created_at=now,
    )
    db.add(note)
    exc.updated_at = now  # the NOTE_ADDED event moves the version
    _user_event(
        db,
        ctx,
        exc,
        ExceptionEventType.NOTE_ADDED,
        now,
        payload={"note_id": note.id, "source": source, "length": len(text)},
    )
    _audit(db, ctx, exc, "exception.note", {"note_id": note.id, "source": source})
    db.commit()
    return _note_out(note, {ctx.user.id: ctx.user.full_name})


def assign(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    assignee_id: uuid.UUID | None,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    """Assign, reassign or unassign (exceptions.assign), or claim an unassigned exception for
    oneself (exceptions.work)."""
    can_assign = ctx.can(Permission.EXCEPTIONS_ASSIGN)
    exc = _lock(db, ctx, exception_id, expected_version)
    unchanged = exc.assignee_id == assignee_id and exc.status in ACTIVE_STATUSES
    if unchanged and (can_assign or assignee_id == ctx.user.id):
        db.rollback()  # nothing to change; release the row lock
        return get_exception_detail(db, ctx, exc.id, now=now)
    claiming = not can_assign and assignee_id == ctx.user.id
    _check(db, ctx, exc, ExceptionAction.CLAIM if claiming else ExceptionAction.ASSIGN)
    if assignee_id is not None and assignee_id not in repository.eligible_assignee_ids(
        db, ctx.store_id, [assignee_id]
    ):
        raise BusinessRuleViolationError(
            "The assignee must be an active member of this organization whose role can work "
            "on exceptions.",
            code="INVALID_ASSIGNEE",
            details=[{"assignee_id": str(assignee_id)}],
        )
    previous = exc.assignee_id
    _assign(db, ctx, exc, assignee_id, now, reason="CLAIMED" if claiming else "ASSIGNED")
    _audit(
        db,
        ctx,
        exc,
        "exception.assign",
        {"from_assignee_id": previous, "to_assignee_id": assignee_id, "claimed": claiming},
    )
    return _finish(db, ctx, exc, now)


def set_due_date(
    db: Session,
    ctx: StoreContext,
    exception_id: uuid.UUID,
    *,
    due_at: datetime,
    note: str | None,
    expected_version: int | None,
    now: datetime,
) -> ExceptionDetail:
    """Manual due-date override (exceptions.assign). Automatic recalculation on a severity
    change never overwrites it; a reopen starts a new cycle and clears it."""
    if due_at.tzinfo is None:
        raise BusinessRuleViolationError(
            "due_at must include a time zone offset.", code="VALIDATION_FAILED"
        )
    new_due = _as_utc(due_at)
    exc = _lock_and_check(db, ctx, exception_id, ExceptionAction.SET_DUE_DATE, expected_version)
    previous = exc.due_at
    exc.due_at = new_due
    exc.due_at_overridden = True
    previous_due = (exc.priority_breakdown or {}).get("due") or {}
    exc.priority_breakdown = {
        **(exc.priority_breakdown or {}),
        "due": {
            "due_at": new_due.isoformat(),
            "basis": "OVERRIDE",
            "anchor_at": previous_due.get("anchor_at", exc.first_detected_at.isoformat()),
            "response_hours": previous_due.get("response_hours"),
            "explanation": f"Set manually by {ctx.user.full_name}.",
        },
    }
    _user_event(
        db,
        ctx,
        exc,
        ExceptionEventType.DUE_DATE_CHANGED,
        now,
        payload={"from": previous, "to": new_due, "note": note},
    )
    text = (note or "").strip()
    if text:
        note_row = ExceptionNote(
            id=uuid.uuid4(),
            exception_id=exc.id,
            store_id=ctx.store_id,
            author_id=ctx.user.id,
            body=text,
            source=NoteSource.USER,
            created_at=now,
        )
        db.add(note_row)
        _user_event(
            db,
            ctx,
            exc,
            ExceptionEventType.NOTE_ADDED,
            now,
            payload={"note_id": note_row.id, "source": NoteSource.USER, "length": len(text)},
        )
    _audit(db, ctx, exc, "exception.due_date", {"from": previous, "to": new_due})
    return _finish(db, ctx, exc, now)


# --- evaluation runs -----------------------------------------------------------------------------


def _run_out(run: EvaluationRun, names: dict[uuid.UUID, str]) -> EvaluationRunOut:
    triggered_by = None
    if run.triggered_by is not None:
        triggered_by = UserRef(
            id=run.triggered_by, full_name=names.get(run.triggered_by, "Former user")
        )
    return EvaluationRunOut(
        id=run.id,
        trigger=run.trigger,
        status=run.status,
        as_of=run.as_of,
        rules=list(run.rules or []),
        counts=dict(run.counts or {}),
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        triggered_by=triggered_by,
        import_id=run.import_id,
        error=run.error,
    )


def run_out(db: Session, run: EvaluationRun) -> EvaluationRunOut:
    return _run_out(run, repository.user_names(db, [run.triggered_by]))


@dataclass(frozen=True)
class TriggeredRun:
    run: EvaluationRunOut
    replayed: bool


def _replayed_run(db: Session, ctx: StoreContext, idempotency_key: str) -> EvaluationRun | None:
    """A previous manual run by the same user with the same Idempotency-Key.

    The key is kept in the ``evaluation.run`` audit entry (the schema has no column for it yet).
    """
    entry = db.scalar(
        select(AuditLog)
        .where(
            AuditLog.organization_id == ctx.organization_id,
            AuditLog.store_id == ctx.store_id,
            AuditLog.actor_user_id == ctx.user.id,
            AuditLog.action == "evaluation.run",
            AuditLog.details["idempotency_key"].astext == idempotency_key,
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    if entry is None:
        return None
    try:
        run_id = uuid.UUID(str(entry.details.get("evaluation_run_id")))
    except ValueError:
        return None
    return db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.store_id == ctx.store_id, EvaluationRun.id == run_id
        )
    )


def trigger_evaluation(
    db: Session,
    ctx: StoreContext,
    *,
    rule_ids: list[str] | None,
    idempotency_key: str | None,
    now: datetime,
) -> TriggeredRun:
    """Manual "Run analysis". A SKIPPED run (lock held) is recorded and returned as-is."""
    if idempotency_key:
        previous = _replayed_run(db, ctx, idempotency_key)
        if previous is not None:
            return TriggeredRun(run=run_out(db, previous), replayed=True)
    run = engine.run_evaluation(
        db,
        ctx.store_id,
        trigger=EvaluationTrigger.MANUAL,
        as_of=now,
        triggered_by=ctx.user.id,
        rule_ids=rule_ids,
    )
    details: dict[str, Any] = {
        "evaluation_run_id": str(run.id),
        "status": run.status.value,
        "counts": run.counts,
        "rules": run.rules,
    }
    if idempotency_key and run.status is not EvaluationStatus.SKIPPED:
        details["idempotency_key"] = idempotency_key
    audit.record(
        db,
        action="evaluation.run",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        store_id=ctx.store_id,
        target_type="evaluation_run",
        target_id=run.id,
        details=details,
    )
    db.commit()
    return TriggeredRun(run=run_out(db, run), replayed=False)


def list_runs(
    db: Session,
    ctx: StoreContext,
    *,
    statuses: Sequence[EvaluationStatus] | None,
    triggers: Sequence[EvaluationTrigger] | None,
    sort: str,
    offset: int,
    limit: int,
) -> tuple[list[EvaluationRunOut], int]:
    conditions: list[ColumnElement[bool]] = [EvaluationRun.store_id == ctx.store_id]
    if statuses:
        conditions.append(EvaluationRun.status.in_(list(statuses)))
    if triggers:
        conditions.append(EvaluationRun.trigger.in_(list(triggers)))
    _, order = _order_by(sort, RUN_SORT_FIELDS)
    total = db.scalar(select(func.count()).select_from(EvaluationRun).where(*conditions)) or 0
    runs = db.scalars(
        select(EvaluationRun)
        .where(*conditions)
        .order_by(order, EvaluationRun.id)
        .offset(offset)
        .limit(limit)
    ).all()
    names = repository.user_names(db, [r.triggered_by for r in runs])
    return [_run_out(r, names) for r in runs], total


def get_run(db: Session, ctx: StoreContext, run_id: uuid.UUID) -> EvaluationRunOut:
    run = db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.store_id == ctx.store_id, EvaluationRun.id == run_id
        )
    )
    if run is None:
        raise NotFoundError("Evaluation run not found.")
    return run_out(db, run)
