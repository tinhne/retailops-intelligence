"""HTTP endpoints for the imports module. See docs/architecture/API_CONVENTIONS.md."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.clock import utcnow
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_db
from app.domains.exceptions import engine
from app.domains.exceptions.models import EvaluationTrigger
from app.domains.identity.permissions import Permission
from app.domains.identity.service import StoreContext
from app.domains.imports import parsing, service
from app.domains.imports.models import ImportStatus, ImportType, IssueSeverity
from app.domains.imports.schemas import (
    ApplyImportRequest,
    ImportDetailOut,
    ImportIssueOut,
    ImportOut,
    ImportSort,
    IssueSort,
)

router = APIRouter(prefix="/stores/{store_id}/imports", tags=["imports"])

_CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


def _evaluate_after_import(
    db: Session,
    *,
    store_id: uuid.UUID,
    import_id: uuid.UUID,
    as_of: datetime,
    triggered_by: uuid.UUID | None,
) -> uuid.UUID:
    """Binds ``service.ImportAppliedHandler`` to the exception engine (IMPORT trigger)."""
    run = engine.run_evaluation(
        db,
        store_id,
        trigger=EvaluationTrigger.IMPORT,
        as_of=as_of,
        triggered_by=triggered_by,
        import_id=import_id,
    )
    return run.id


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=_CSV_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("", response_model=ImportDetailOut, status_code=status.HTTP_201_CREATED)
def create_import(
    import_type: ImportType = Form(...),
    file: UploadFile = File(...),
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_RUN)),
    db: Session = Depends(get_db),
) -> ImportDetailOut:
    """Upload a CSV and validate it. A file-level failure is still 201, with status REJECTED."""
    upload = parsing.read_upload(file.file, file.filename)
    return service.create_import(db, ctx, import_type=import_type, upload=upload, now=utcnow())


@router.get("", response_model=Page[ImportOut])
def list_imports(
    import_type: ImportType | None = None,
    import_status: ImportStatus | None = Query(None, alias="status"),
    sort: ImportSort = "-created_at",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_READ)),
    db: Session = Depends(get_db),
) -> Page[ImportOut]:
    items, total = service.list_imports(
        db,
        ctx,
        import_type=import_type,
        status=import_status,
        sort=sort,
        offset=paging.offset,
        limit=paging.page_size,
        now=utcnow(),
    )
    return Page[ImportOut](items=items, page=paging.page, page_size=paging.page_size, total=total)


# Declared before "/{import_id}" so "templates" is never parsed as an import id.
@router.get(
    "/templates/{import_type}",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV template"}},
)
def download_template(
    import_type: ImportType,
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_READ)),
) -> Response:
    return _csv_response(service.template_csv(import_type), f"{import_type.value}_template.csv")


@router.get("/{import_id}", response_model=ImportDetailOut)
def get_import(
    import_id: uuid.UUID,
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_READ)),
    db: Session = Depends(get_db),
) -> ImportDetailOut:
    return service.get_import(db, ctx, import_id, now=utcnow())


@router.get(
    "/{import_id}/issues.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "Issues as CSV"}},
)
def download_issues(
    import_id: uuid.UUID,
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_READ)),
    db: Session = Depends(get_db),
) -> Response:
    content = service.export_issues_csv(db, ctx, import_id)
    return _csv_response(content, f"import-{import_id}-issues.csv")


@router.get("/{import_id}/issues", response_model=Page[ImportIssueOut])
def list_issues(
    import_id: uuid.UUID,
    severity: IssueSeverity | None = None,
    code: str | None = Query(None, max_length=64),
    sort: IssueSort = "row_number",
    paging: PageParams = Depends(page_params),
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_READ)),
    db: Session = Depends(get_db),
) -> Page[ImportIssueOut]:
    items, total = service.list_issues(
        db,
        ctx,
        import_id,
        severity=severity,
        code=code,
        sort=sort,
        offset=paging.offset,
        limit=paging.page_size,
    )
    return Page[ImportIssueOut](
        items=items, page=paging.page, page_size=paging.page_size, total=total
    )


@router.post("/{import_id}/apply", response_model=ImportDetailOut)
def apply_import(
    import_id: uuid.UUID,
    body: ApplyImportRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=200),
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_RUN)),
    db: Session = Depends(get_db),
) -> ImportDetailOut:
    """Apply atomically (BR-606), then run the IMPORT-triggered exception evaluation."""
    return service.apply_import(
        db,
        ctx,
        import_id,
        mode=body.mode,
        confirm_skipped_rows=body.confirm_skipped_rows,
        idempotency_key=idempotency_key,
        now=utcnow(),
        on_applied=_evaluate_after_import,
    )


@router.post("/{import_id}/discard", response_model=ImportDetailOut)
def discard_import(
    import_id: uuid.UUID,
    ctx: StoreContext = Depends(require_permission(Permission.IMPORTS_RUN)),
    db: Session = Depends(get_db),
) -> ImportDetailOut:
    return service.discard_import(db, ctx, import_id, now=utcnow())
