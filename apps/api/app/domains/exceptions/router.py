"""HTTP endpoints for the exceptions module (exception inbox, lifecycle, evaluation runs).

Store-scoped: every route takes ``store_id`` and resolves the caller's role through
``require_permission`` (another tenant's store or exception → 404).
"""

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.core.errors import BusinessRuleViolationError
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.exceptions import service
from app.domains.exceptions.models import (
    EvaluationStatus,
    EvaluationTrigger,
    ExceptionCategory,
    ExceptionStatus,
    ExceptionType,
    PriorityBand,
    ResolutionCode,
    Severity,
)
from app.domains.exceptions.schemas import (
    AssignRequest,
    DismissRequest,
    DueDateRequest,
    EvaluationCreate,
    EvaluationRunOut,
    ExceptionDetail,
    ExceptionEventOut,
    ExceptionListItem,
    ExceptionNoteOut,
    NoteCreate,
    ReopenRequest,
    ResolveRequest,
    VersionedRequest,
)
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext

router = APIRouter(prefix="/stores/{store_id}", tags=["exceptions"])

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_READ = require_permission(Permission.EXCEPTIONS_READ)
_WORK = require_permission(Permission.EXCEPTIONS_WORK)
_ASSIGN = require_permission(Permission.EXCEPTIONS_ASSIGN)
_MANAGE = require_permission(Permission.EXCEPTIONS_MANAGE)
_RUN = require_permission(Permission.EVALUATIONS_RUN)


def _version(body: VersionedRequest | None) -> int | None:
    return body.expected_version if body is not None else None


# --- exceptions ---------------------------------------------------------------------------------


@router.get("/exceptions", response_model=Page[ExceptionListItem])
def list_exceptions(
    status_: list[ExceptionStatus] | None = Query(
        None, alias="status", description="Repeatable. Defaults to the active statuses."
    ),
    severity: list[Severity] | None = Query(None),
    exception_type: list[ExceptionType] | None = Query(None),
    category: list[ExceptionCategory] | None = Query(None),
    priority_band: list[PriorityBand] | None = Query(None),
    assignee: str | None = Query(
        None, max_length=40, description="'me', 'unassigned' or a user id"
    ),
    product_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    q: str | None = Query(None, max_length=100, description="Reference or title contains"),
    due_to: datetime | None = Query(
        None, description="Only exceptions due at or before this instant (with a time zone)"
    ),
    sort: str = Query(
        service.DEFAULT_SORT,
        description="priority_score, due_at, first_detected_at, last_detected_at; '-' = desc",
    ),
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> Page[ExceptionListItem]:
    items, total = service.list_exceptions(
        db,
        ctx.store_id,
        current_user_id=ctx.user.id,
        filters=service.ExceptionFilters(
            statuses=status_,
            severities=severity,
            exception_types=exception_type,
            categories=category,
            priority_bands=priority_band,
            assignee=assignee,
            product_id=product_id,
            order_id=order_id,
            q=q,
            due_to=due_to,
        ),
        sort=sort,
        offset=paging.offset,
        limit=paging.page_size,
        now=utcnow(),
    )
    return Page[ExceptionListItem](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


@router.get("/exceptions/{exception_id}", response_model=ExceptionDetail)
def get_exception(
    exception_id: uuid.UUID,
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.get_exception_detail(db, ctx, exception_id, now=utcnow())


@router.get("/exceptions/{exception_id}/events", response_model=Page[ExceptionEventOut])
def list_exception_events(
    exception_id: uuid.UUID,
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> Page[ExceptionEventOut]:
    items, total = service.list_events(
        db, ctx, exception_id, offset=paging.offset, limit=paging.page_size
    )
    return Page[ExceptionEventOut](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


@router.get("/exceptions/{exception_id}/notes", response_model=Page[ExceptionNoteOut])
def list_exception_notes(
    exception_id: uuid.UUID,
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> Page[ExceptionNoteOut]:
    items, total = service.list_notes(
        db, ctx, exception_id, offset=paging.offset, limit=paging.page_size
    )
    return Page[ExceptionNoteOut](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


@router.post("/exceptions/{exception_id}/acknowledge", response_model=ExceptionDetail)
def acknowledge_exception(
    exception_id: uuid.UUID,
    body: VersionedRequest | None = None,
    ctx: StoreContext = Depends(_WORK),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.acknowledge(db, ctx, exception_id, expected_version=_version(body), now=utcnow())


@router.post("/exceptions/{exception_id}/start", response_model=ExceptionDetail)
def start_exception(
    exception_id: uuid.UUID,
    body: VersionedRequest | None = None,
    ctx: StoreContext = Depends(_WORK),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.start(db, ctx, exception_id, expected_version=_version(body), now=utcnow())


@router.post("/exceptions/{exception_id}/resolve", response_model=ExceptionDetail)
def resolve_exception(
    exception_id: uuid.UUID,
    body: ResolveRequest,
    ctx: StoreContext = Depends(_WORK),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.resolve(
        db,
        ctx,
        exception_id,
        resolution_code=ResolutionCode(body.resolution_code.value),
        resolution_note=body.resolution_note,
        expected_version=body.expected_version,
        now=utcnow(),
    )


@router.post("/exceptions/{exception_id}/dismiss", response_model=ExceptionDetail)
def dismiss_exception(
    exception_id: uuid.UUID,
    body: DismissRequest,
    ctx: StoreContext = Depends(_MANAGE),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.dismiss(
        db,
        ctx,
        exception_id,
        dismissal_reason=body.dismissal_reason,
        note=body.note,
        expected_version=body.expected_version,
        now=utcnow(),
    )


@router.post("/exceptions/{exception_id}/reopen", response_model=ExceptionDetail)
def reopen_exception(
    exception_id: uuid.UUID,
    body: ReopenRequest,
    ctx: StoreContext = Depends(_MANAGE),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.reopen(
        db,
        ctx,
        exception_id,
        reason=body.reason,
        expected_version=body.expected_version,
        now=utcnow(),
    )


@router.post(
    "/exceptions/{exception_id}/notes",
    response_model=ExceptionNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def add_exception_note(
    exception_id: uuid.UUID,
    body: NoteCreate,
    ctx: StoreContext = Depends(_WORK),
    db: Session = Depends(get_db),
) -> ExceptionNoteOut:
    return service.add_note(
        db,
        ctx,
        exception_id,
        body=body.body,
        expected_version=body.expected_version,
        now=utcnow(),
        source=body.source,
    )


@router.post("/exceptions/{exception_id}/assign", response_model=ExceptionDetail)
def assign_exception(
    exception_id: uuid.UUID,
    body: AssignRequest,
    ctx: StoreContext = Depends(_WORK),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    """Assign, reassign or unassign (exceptions.assign). Users with only exceptions.work may
    claim an unassigned exception by passing their own id."""
    return service.assign(
        db,
        ctx,
        exception_id,
        assignee_id=body.assignee_id,
        expected_version=body.expected_version,
        now=utcnow(),
    )


@router.patch("/exceptions/{exception_id}/due-date", response_model=ExceptionDetail)
def set_exception_due_date(
    exception_id: uuid.UUID,
    body: DueDateRequest,
    ctx: StoreContext = Depends(_ASSIGN),
    db: Session = Depends(get_db),
) -> ExceptionDetail:
    return service.set_due_date(
        db,
        ctx,
        exception_id,
        due_at=body.due_at,
        note=body.note,
        expected_version=body.expected_version,
        now=utcnow(),
    )


# --- evaluation runs ----------------------------------------------------------------------------


@router.post(
    "/evaluations",
    response_model=EvaluationRunOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Idempotent replay, or SKIPPED because a run is in progress"}},
)
def trigger_evaluation(
    response: Response,
    body: EvaluationCreate | None = None,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ctx: StoreContext = Depends(_RUN),
    db: Session = Depends(get_db),
) -> EvaluationRunOut:
    """Manual "Run analysis". 201 with the new run; 200 with the SKIPPED run while another
    evaluation holds the store lock; 200 with the original run on an Idempotency-Key replay."""
    if idempotency_key is not None and not _IDEMPOTENCY_KEY.match(idempotency_key):
        raise BusinessRuleViolationError(
            "Idempotency-Key must be 1–128 characters of letters, digits, '.', '_', ':' or '-'.",
            code="VALIDATION_FAILED",
            details=[{"loc": ["header", "Idempotency-Key"], "message": "invalid format"}],
        )
    result = service.trigger_evaluation(
        db,
        ctx,
        rule_ids=body.rule_ids if body else None,
        idempotency_key=idempotency_key,
        now=utcnow(),
    )
    if result.replayed:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotent-Replayed"] = "true"
    elif result.run.status is EvaluationStatus.SKIPPED:
        response.status_code = status.HTTP_200_OK
    return result.run


@router.get("/evaluations", response_model=Page[EvaluationRunOut])
def list_evaluations(
    status_: list[EvaluationStatus] | None = Query(None, alias="status"),
    trigger: list[EvaluationTrigger] | None = Query(None),
    sort: str = Query("-started_at", description="started_at or as_of; '-' = descending"),
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> Page[EvaluationRunOut]:
    items, total = service.list_runs(
        db,
        ctx,
        statuses=status_,
        triggers=trigger,
        sort=sort,
        offset=paging.offset,
        limit=paging.page_size,
    )
    return Page[EvaluationRunOut](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


@router.get("/evaluations/{run_id}", response_model=EvaluationRunOut)
def get_evaluation(
    run_id: uuid.UUID,
    ctx: StoreContext = Depends(_READ),
    db: Session = Depends(get_db),
) -> EvaluationRunOut:
    return service.get_run(db, ctx, run_id)
