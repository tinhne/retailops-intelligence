"""CSV import pipeline: upload and validate, preview, apply, discard and issue export.

Lifecycle (STATE_MACHINES.md §4)::

    upload -> VALIDATED | REJECTED            (one transaction, read-only against business data)
    apply  -> APPLYING (T1) -> COMPLETED | COMPLETED_WITH_ERRORS (T2) | FAILED (T3 after rollback)
    then an IMPORT-triggered evaluation in its own unit of work; its failure never undoes T2

Every business change goes through the owning module's service (catalog, orders, inventory) inside
the single T2 transaction this module owns (BR-606). Entry points commit; helpers never do.
"""

import csv
import io
import logging
import uuid
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import Integer, cast, delete, func, insert, literal, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import AppError, BusinessRuleViolationError, ConflictError, NotFoundError
from app.domains.audit import service as audit
from app.domains.catalog import service as catalog
from app.domains.identity.service import StoreContext
from app.domains.imports import (
    parsing,
    templates,
    validate_inventory_adjustments,
    validate_order_items,
    validate_orders,
    validate_products,
)
from app.domains.imports.models import (
    DataImport,
    ImportMode,
    ImportRowIssue,
    ImportStatus,
    ImportType,
    IssueSeverity,
)
from app.domains.imports.schemas import (
    AppliedCounts,
    ImportDetailOut,
    ImportIssueOut,
    ImportOut,
    ImportSort,
    ImportSummary,
    IssueSort,
)
from app.domains.imports.validation import (
    Issue,
    RowAction,
    RowPlan,
    ValidationContext,
    ValidationResult,
)
from app.domains.inventory import service as inventory
from app.domains.inventory.models import MovementSource
from app.domains.orders import service as orders
from app.domains.orders.models import ChangeSource, Order

logger = logging.getLogger("app.imports")

PREVIEW_TTL = timedelta(hours=24)
APPLYING_STALE_AFTER = timedelta(minutes=15)
DEFAULT_FULFILLMENT_SLA_HOURS = 48
FILE_ISSUE_LIMIT = 50
_IMPORT_APPLY_LOCK = 0x494D5054  # advisory lock namespace "IMPT" (two-int form)
_IDEMPOTENCY_FIELD = "apply_idempotency_key"
_APPLIED = frozenset({ImportStatus.COMPLETED, ImportStatus.COMPLETED_WITH_ERRORS})
_CHANGES = frozenset({RowAction.CREATE, RowAction.UPDATE})
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

Validator = Callable[[Session, ValidationContext, parsing.ParsedFile], ValidationResult[Any]]
_VALIDATORS: dict[ImportType, Validator] = {
    ImportType.PRODUCTS: validate_products.validate,
    ImportType.ORDERS: validate_orders.validate,
    ImportType.ORDER_ITEMS: validate_order_items.validate,
    ImportType.INVENTORY_ADJUSTMENTS: validate_inventory_adjustments.validate,
}


class ImportAppliedHandler(Protocol):
    """Runs the IMPORT-triggered evaluation after a successful apply; returns the run id.

    Declared here and bound by the entry point (the router) so ``imports`` does not depend on
    ``exceptions`` (SYSTEM_ARCHITECTURE §5, the one inverted edge). The handler must not commit.
    """

    def __call__(
        self,
        db: Session,
        *,
        store_id: uuid.UUID,
        import_id: uuid.UUID,
        as_of: datetime,
        triggered_by: uuid.UUID | None,
    ) -> uuid.UUID: ...


@dataclass(frozen=True)
class ApplyContext:
    store_id: uuid.UUID
    import_id: uuid.UUID
    user_id: uuid.UUID
    fulfillment_sla_hours: int


# --- Upload and validation -----------------------------------------------------------------


def create_import(
    db: Session,
    ctx: StoreContext,
    *,
    import_type: ImportType,
    upload: parsing.Upload,
    now: datetime,
) -> ImportDetailOut:
    """Validate an upload and store it as VALIDATED (with a preview) or REJECTED (BR-602)."""
    _expire_previews(db, ctx.store_id, now)
    record = DataImport(
        id=uuid.uuid4(),
        store_id=ctx.store_id,
        import_type=import_type,
        status=ImportStatus.VALIDATING,
        original_filename=upload.filename or "upload",
        file_sha256=upload.sha256,
        size_bytes=upload.size_bytes,
        created_by=ctx.user.id,
        summary={},
    )
    db.add(record)
    db.flush()
    _validate_into(db, ctx, record, upload, now)
    db.commit()
    return _detail(db, record)


def revalidate_import(
    db: Session, ctx: StoreContext, import_id: uuid.UUID, *, now: datetime
) -> ImportDetailOut:
    """FAILED -> VALIDATING -> VALIDATED | REJECTED from the stored bytes (STATE_MACHINES §4).

    A failed apply keeps the file bytes until the preview's original expiry, so the same file
    can be validated again against current data (IMPORT_PIPELINE §9). Once they are purged, the
    only way forward is a new upload (``IMPORT_CONTENT_MISSING``).
    """
    record = _load(db, ctx.store_id, import_id, lock=True)
    _refresh_lifecycle(record, now)  # purges the bytes of an expired failure
    if record.status is not ImportStatus.FAILED:
        raise ConflictError(
            f"Only a FAILED import can be validated again; this one is {record.status.value}.",
            code="IMPORT_NOT_APPLICABLE",
        )
    if record.content is None:
        raise ConflictError(
            "The uploaded file is no longer stored. Upload the file again.",
            code="IMPORT_CONTENT_MISSING",
        )
    upload = parsing.Upload(
        filename=record.original_filename,
        size_bytes=record.size_bytes,
        sha256=record.file_sha256,
        content=record.content,
    )
    previous_failure = record.failure_reason
    record.status = ImportStatus.VALIDATING
    record.mode = None
    record.applied_by = None
    record.applied_at = None
    record.failure_reason = None
    record.evaluation_run_id = None
    db.execute(delete(ImportRowIssue).where(ImportRowIssue.import_id == record.id))
    db.flush()
    _validate_into(db, ctx, record, upload, now)
    audit.record(
        db,
        action="import.revalidated",
        organization_id=ctx.organization_id,
        store_id=ctx.store_id,
        actor_user_id=ctx.user.id,
        target_type="data_import",
        target_id=record.id,
        details={
            "import_type": record.import_type.value,
            "status": record.status.value,
            "previous_failure": previous_failure,
        },
    )
    db.commit()
    return _detail(db, record)


def _validate_into(
    db: Session, ctx: StoreContext, record: DataImport, upload: parsing.Upload, now: datetime
) -> None:
    """Parse and validate ``upload`` into ``record``: VALIDATED with a preview, or REJECTED."""
    import_type = record.import_type
    outcome = _parse(upload, templates.contract_for(import_type))
    if isinstance(outcome, parsing.FileIssue):
        record.status = ImportStatus.REJECTED
        record.content = None
        record.row_count = None
        record.expires_at = None
        record.summary = ImportSummary(issue_counts_by_code={outcome.code: 1}).model_dump(
            mode="json"
        )
        _store_issues(db, record.id, [Issue.from_file_issue(outcome)])
    else:
        result = _VALIDATORS[import_type](db, _validation_context(ctx), outcome)
        result.file_warnings = [Issue.from_file_issue(w) for w in outcome.warnings]
        if _is_duplicate_file(db, ctx.store_id, import_type, upload.sha256):
            result.file_warnings.append(
                Issue(
                    row_number=None,
                    column=None,
                    code="DUPLICATE_FILE",
                    severity=IssueSeverity.WARNING,
                    message=(
                        "An identical file was already imported for this store. Applying it "
                        "again is safe: rows are upserts and adjustment references are "
                        "idempotent (BR-607)."
                    ),
                )
            )
        record.status = ImportStatus.VALIDATED
        record.row_count = len(outcome.rows)
        record.summary = result.summary()
        record.validated_at = now
        record.expires_at = now + PREVIEW_TTL
        record.content = upload.content
        _store_issues(db, record.id, result.all_issues)


def _parse(
    upload: parsing.Upload, contract: templates.ImportContract
) -> parsing.ParsedFile | parsing.FileIssue:
    issue = parsing.check_upload(upload)
    if issue is not None:
        return issue
    text = parsing.decode(upload.content)
    if isinstance(text, parsing.FileIssue):
        return text
    return parsing.parse_csv(text, contract)


def _validation_context(ctx: StoreContext) -> ValidationContext:
    settings = ctx.store.settings
    return ValidationContext(
        store_id=ctx.store_id,
        currency=ctx.store.currency,
        timezone=ctx.store.timezone,
        fulfillment_sla_hours=(
            settings.fulfillment_sla_hours if settings else DEFAULT_FULFILLMENT_SLA_HOURS
        ),
    )


def _is_duplicate_file(
    db: Session, store_id: uuid.UUID, import_type: ImportType, sha256: str
) -> bool:
    """BR-607: an identical file already applied for this store and type."""
    return (
        db.scalar(
            select(DataImport.id)
            .where(
                DataImport.store_id == store_id,
                DataImport.import_type == import_type,
                DataImport.file_sha256 == sha256,
                DataImport.status.in_(_APPLIED),
            )
            .limit(1)
        )
        is not None
    )


def _store_issues(db: Session, import_id: uuid.UUID, issues: list[Issue]) -> None:
    if not issues:
        return
    db.execute(
        insert(ImportRowIssue),
        [
            {
                "id": uuid.uuid4(),
                "import_id": import_id,
                "row_number": issue.row_number,
                "column": issue.column[:64] if issue.column else None,
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message[:500],
                "raw_value": issue.raw_value,
            }
            for issue in issues
        ],
    )


# --- Reads ---------------------------------------------------------------------------------


def get_import(
    db: Session, ctx: StoreContext, import_id: uuid.UUID, *, now: datetime
) -> ImportDetailOut:
    record = _load(db, ctx.store_id, import_id)
    if _refresh_lifecycle(record, now):
        db.commit()
    return _detail(db, record)


_IMPORT_ORDER: dict[str, list[ColumnElement[Any]]] = {
    "created_at": [DataImport.created_at.asc()],
    "-created_at": [DataImport.created_at.desc()],
    "applied_at": [DataImport.applied_at.asc().nulls_last()],
    "-applied_at": [DataImport.applied_at.desc().nulls_last()],
    "status": [DataImport.status.asc()],
    "-status": [DataImport.status.desc()],
    "import_type": [DataImport.import_type.asc()],
    "-import_type": [DataImport.import_type.desc()],
}


def list_imports(
    db: Session,
    ctx: StoreContext,
    *,
    import_type: ImportType | None,
    statuses: Sequence[ImportStatus] | None,
    sort: ImportSort,
    offset: int,
    limit: int,
    now: datetime,
) -> tuple[list[ImportOut], int]:
    if _expire_previews(db, ctx.store_id, now):
        db.commit()
    stmt = select(DataImport).where(DataImport.store_id == ctx.store_id)
    if import_type is not None:
        stmt = stmt.where(DataImport.import_type == import_type)
    if statuses:
        stmt = stmt.where(DataImport.status.in_(list(statuses)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(*_IMPORT_ORDER[sort], DataImport.created_at.desc(), DataImport.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [_out(record) for record in rows], total


_ISSUE_ORDER: dict[str, list[ColumnElement[Any]]] = {
    "row_number": [ImportRowIssue.row_number.asc().nulls_first()],
    "-row_number": [ImportRowIssue.row_number.desc().nulls_last()],
    "code": [ImportRowIssue.code.asc()],
    "-code": [ImportRowIssue.code.desc()],
    "severity": [ImportRowIssue.severity.asc()],
    "-severity": [ImportRowIssue.severity.desc()],
}
_ISSUE_TIEBREAK = (
    ImportRowIssue.row_number.asc().nulls_first(),
    ImportRowIssue.severity.asc(),
    ImportRowIssue.code.asc(),
    ImportRowIssue.column.asc().nulls_first(),
    ImportRowIssue.id.asc(),
)


def list_issues(
    db: Session,
    ctx: StoreContext,
    import_id: uuid.UUID,
    *,
    severity: IssueSeverity | None,
    code: str | None,
    row_number: int | None = None,
    sort: IssueSort,
    offset: int,
    limit: int,
) -> tuple[list[ImportIssueOut], int]:
    _load(db, ctx.store_id, import_id)
    stmt = select(ImportRowIssue).where(ImportRowIssue.import_id == import_id)
    if severity is not None:
        stmt = stmt.where(ImportRowIssue.severity == severity)
    if code:
        stmt = stmt.where(ImportRowIssue.code == code.upper())
    if row_number is not None:
        stmt = stmt.where(ImportRowIssue.row_number == row_number)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(*_ISSUE_ORDER[sort], *_ISSUE_TIEBREAK).offset(offset).limit(limit)
    ).all()
    return [_issue_out(issue) for issue in rows], total


def filenames_by_id(
    db: Session, store_id: uuid.UUID, import_ids: Collection[uuid.UUID | None]
) -> dict[uuid.UUID, str]:
    """``original_filename`` of the given imports of one store, for read models linking them."""
    ids = {import_id for import_id in import_ids if import_id is not None}
    if not ids:
        return {}
    rows = db.execute(
        select(DataImport.id, DataImport.original_filename).where(
            DataImport.store_id == store_id, DataImport.id.in_(ids)
        )
    ).all()
    return {import_id: filename for import_id, filename in rows}


def export_issues_csv(db: Session, ctx: StoreContext, import_id: uuid.UUID) -> str:
    """All issues as CSV. Cells that a spreadsheet would run as a formula are neutralised."""
    _load(db, ctx.store_id, import_id)
    rows = db.scalars(
        select(ImportRowIssue)
        .where(ImportRowIssue.import_id == import_id)
        .order_by(*_ISSUE_TIEBREAK)
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["row_number", "column", "severity", "code", "message", "raw_value"])
    for issue in rows:
        writer.writerow(
            [
                escape_cell(value)
                for value in (
                    issue.row_number,
                    issue.column,
                    issue.severity.value,
                    issue.code,
                    issue.message,
                    issue.raw_value,
                )
            ]
        )
    return "﻿" + buffer.getvalue()  # BOM so spreadsheet tools detect UTF-8


def escape_cell(value: object) -> str:
    """Prefix an apostrophe to cells starting with = + - @ tab or CR (CSV formula injection)."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def template_csv(import_type: ImportType) -> str:
    return templates.render_template(import_type)


# --- Apply ---------------------------------------------------------------------------------


def apply_import(
    db: Session,
    ctx: StoreContext,
    import_id: uuid.UUID,
    *,
    mode: ImportMode,
    confirm_skipped_rows: int | None,
    idempotency_key: str | None,
    now: datetime,
    on_applied: ImportAppliedHandler | None = None,
) -> ImportDetailOut:
    """Apply a validated import atomically (BR-606, STATE_MACHINES.md §4)."""
    record = _load(db, ctx.store_id, import_id, lock=True)
    stored_key = record.summary.get(_IDEMPOTENCY_FIELD)
    if idempotency_key is not None and record.status in _APPLIED and stored_key == idempotency_key:
        if record.mode is not mode:
            raise ConflictError(
                "This Idempotency-Key was used for an apply with a different mode.",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        db.rollback()
        return _detail(db, record)  # replay: the stored result, not a second apply
    if record.status is ImportStatus.VALIDATED and _expired(record, now):
        _discard(record)
        db.commit()
        raise ConflictError(
            "This preview expired 24 hours after validation because data may have changed. "
            "Upload the file again.",
            code="IMPORT_EXPIRED",
        )
    if record.status is not ImportStatus.VALIDATED:
        raise ConflictError(
            f"Only a VALIDATED import can be applied; this one is {record.status.value}.",
            code="IMPORT_NOT_APPLICABLE",
        )
    error_rows = int(record.summary.get("rows_with_errors", 0))
    if mode is ImportMode.STRICT and error_rows:
        raise ConflictError(
            f"{error_rows} row(s) have errors. Fix the file and upload it again, or apply in "
            "VALID_ROWS_ONLY mode and confirm the skipped rows.",
            code="IMPORT_HAS_ERRORS",
            details=[{"rows_with_errors": error_rows}],
        )
    if mode is ImportMode.VALID_ROWS_ONLY and (confirm_skipped_rows or 0) != error_rows:
        raise BusinessRuleViolationError(
            f"Confirm that {error_rows} row(s) with errors will be skipped (confirm_skipped_rows).",
            code="SKIPPED_ROWS_NOT_CONFIRMED",
            details=[
                {"expected_confirm_skipped_rows": error_rows, "received": confirm_skipped_rows}
            ],
        )

    # T1: claim the import so a concurrent apply sees APPLYING and stops.
    record.status = ImportStatus.APPLYING
    record.mode = mode
    record.applied_by = ctx.user.id
    db.commit()

    try:
        _apply_in_transaction(db, ctx, record, mode=mode, idempotency_key=idempotency_key, now=now)
    except Exception as exc:
        db.rollback()  # T2 undone: no business data changed
        raise _record_failure(db, ctx, import_id, mode, exc) from exc

    _evaluate(db, ctx, record, now=now, on_applied=on_applied)
    return _detail(db, record)


def _apply_in_transaction(
    db: Session,
    ctx: StoreContext,
    record: DataImport,
    *,
    mode: ImportMode,
    idempotency_key: str | None,
    now: datetime,
) -> None:
    """T2: re-validate against current data, apply through the domain services, commit."""
    db.execute(
        select(
            func.pg_advisory_xact_lock(
                cast(literal(_IMPORT_APPLY_LOCK), Integer),
                cast(literal(_store_lock_key(ctx.store_id)), Integer),
            )
        )
    )
    if record.content is None:
        raise ConflictError("The uploaded file is no longer stored.", code="IMPORT_CONTENT_MISSING")
    upload = parsing.Upload(
        filename=record.original_filename,
        size_bytes=record.size_bytes,
        sha256=record.file_sha256,
        content=record.content,
    )
    outcome = _parse(upload, templates.contract_for(record.import_type))
    if isinstance(outcome, parsing.FileIssue):
        raise ConflictError(outcome.message, code=outcome.code)
    result = _VALIDATORS[record.import_type](db, _validation_context(ctx), outcome)

    previewed = set(
        db.scalars(
            select(ImportRowIssue.row_number)
            .where(
                ImportRowIssue.import_id == record.id,
                ImportRowIssue.severity == IssueSeverity.ERROR,
                ImportRowIssue.row_number.is_not(None),
            )
            .distinct()
        ).all()
    )
    if result.error_rows != previewed:
        raise ConflictError(
            "The data changed since this file was validated, so the rows to skip are no longer "
            "the ones shown in the preview. Nothing was applied; upload the file again.",
            code="IMPORT_DATA_CHANGED",
            details=_drift_details(result, previewed),
        )

    actx = ApplyContext(
        store_id=ctx.store_id,
        import_id=record.id,
        user_id=ctx.user.id,
        fulfillment_sla_hours=_validation_context(ctx).fulfillment_sla_hours,
    )
    touched_orders = _apply_rows(db, actx, record.import_type, result.plans)
    if touched_orders:
        inventory.sync_reservations(db, ctx.store_id, touched_orders, now=now)

    counts = AppliedCounts(
        mode=mode,
        creates=result.count(RowAction.CREATE),
        updates=result.count(RowAction.UPDATE),
        unchanged=result.count(RowAction.UNCHANGED),
        skipped=result.count(RowAction.SKIP),
    )
    record.status = ImportStatus.COMPLETED_WITH_ERRORS if counts.skipped else ImportStatus.COMPLETED
    record.applied_at = now
    record.content = None  # purge the file bytes (DOMAIN_MODEL: kept only until apply)
    summary = {**record.summary, "applied": counts.model_dump(mode="json")}
    if idempotency_key is not None:
        summary[_IDEMPOTENCY_FIELD] = idempotency_key
    record.summary = summary
    audit.record(
        db,
        action="import.applied",
        organization_id=ctx.organization_id,
        store_id=ctx.store_id,
        actor_user_id=ctx.user.id,
        target_type="data_import",
        target_id=record.id,
        details={"import_type": record.import_type.value, **counts.model_dump(mode="json")},
    )
    db.commit()


def _apply_rows(
    db: Session, actx: ApplyContext, import_type: ImportType, plans: list[RowPlan[Any]]
) -> set[uuid.UUID]:
    """Apply CREATE / UPDATE rows in file order. Returns the ids of orders whose lines changed."""
    changes = [plan for plan in plans if plan.action in _CHANGES and plan.payload is not None]
    match import_type:
        case ImportType.PRODUCTS:
            _apply_products(db, actx, changes)
            return set()
        case ImportType.ORDERS:
            return _apply_orders(db, actx, changes)
        case ImportType.ORDER_ITEMS:
            return _apply_order_items(db, actx, changes)
        case ImportType.INVENTORY_ADJUSTMENTS:
            _apply_adjustments(db, actx, changes)
            return set()


def _apply_products(
    db: Session, actx: ApplyContext, plans: list[RowPlan[validate_products.ProductRow]]
) -> None:
    for plan in plans:
        assert plan.payload is not None
        data = plan.payload.data
        supplier_id = None
        if data.supplier_name is not None:
            supplier = catalog.upsert_supplier(
                db,
                store_id=actx.store_id,
                name=data.supplier_name,
                lead_time_days=plan.payload.supplier_lead_time_days,
            )
            supplier_id = supplier.id
        catalog.upsert_product(db, store_id=actx.store_id, data=data, supplier_id=supplier_id)


def _apply_orders(
    db: Session, actx: ApplyContext, plans: list[RowPlan[orders.OrderSnapshot]]
) -> set[uuid.UUID]:
    touched: set[uuid.UUID] = set()
    for plan in plans:
        assert plan.payload is not None
        order, _ = orders.upsert_order(
            db,
            store_id=actx.store_id,
            snapshot=plan.payload,
            fulfillment_sla_hours=actx.fulfillment_sla_hours,
            source=ChangeSource.IMPORT,
            import_id=actx.import_id,
            actor_user_id=actx.user_id,
        )
        touched.add(order.id)
    return touched


def _apply_order_items(
    db: Session, actx: ApplyContext, plans: list[RowPlan[validate_order_items.OrderItemRow]]
) -> set[uuid.UUID]:
    touched: dict[uuid.UUID, Order] = {}
    for plan in plans:
        assert plan.payload is not None
        order = orders.find_by_number(db, actx.store_id, plan.payload.order_number)
        if order is None:  # re-validated in this transaction; defensive only
            raise ConflictError(
                f"Order {plan.payload.order_number} no longer exists.", code="UNKNOWN_ORDER"
            )
        orders.upsert_order_item(db, order=order, line=plan.payload.line)
        touched[order.id] = order
    for order in touched.values():
        # Validation loaded order.items; reload so the reservation sync sees the new lines.
        db.expire(order, ["items"])
    return set(touched)


def _apply_adjustments(
    db: Session,
    actx: ApplyContext,
    plans: list[RowPlan[validate_inventory_adjustments.AdjustmentRow]],
) -> None:
    for plan in plans:
        assert plan.payload is not None
        row = plan.payload
        inventory.record_movement(
            db,
            store_id=actx.store_id,
            product_id=row.product_id,
            movement_type=row.movement_type,
            quantity=row.quantity,
            occurred_at=row.occurred_at,
            source=MovementSource.IMPORT,
            reference=row.reference,
            expected_at=row.expected_at,
            import_id=actx.import_id,
            note=row.note,
            created_by=actx.user_id,
        )


def _drift_details(
    result: ValidationResult[Any], previewed: set[int | None]
) -> list[dict[str, Any]]:
    new_errors = [
        {"row_number": issue.row_number, "code": issue.code, "message": issue.message}
        for issue in result.issues
        if issue.severity is IssueSeverity.ERROR and issue.row_number not in previewed
    ]
    cleared = sorted(n for n in previewed if n is not None and n not in result.error_rows)
    details: list[dict[str, Any]] = new_errors[:FILE_ISSUE_LIMIT]
    if cleared:
        details.append({"rows_no_longer_failing": cleared[:FILE_ISSUE_LIMIT]})
    return details


def _record_failure(
    db: Session, ctx: StoreContext, import_id: uuid.UUID, mode: ImportMode, exc: Exception
) -> AppError:
    """T3: mark the import FAILED in a fresh transaction and return the error to raise."""
    if isinstance(exc, AppError) and exc.status_code in (409, 422):
        error: AppError = exc
    elif isinstance(exc, AppError):
        error = ConflictError(exc.message, code=exc.code, details=exc.details)
    else:
        logger.exception("import_apply_failed", extra={"import_id": str(import_id)})
        error = ConflictError(
            "The import could not be applied. No data was changed.", code="IMPORT_APPLY_FAILED"
        )
    record = _load(db, ctx.store_id, import_id)
    record.status = ImportStatus.FAILED
    record.mode = mode
    record.applied_by = ctx.user.id
    record.failure_reason = f"{error.code}: {error.message}"[:500]
    # The bytes stay until the preview's expiry so the file can be validated again (revalidate).
    audit.record(
        db,
        action="import.failed",
        organization_id=ctx.organization_id,
        store_id=ctx.store_id,
        actor_user_id=ctx.user.id,
        target_type="data_import",
        target_id=record.id,
        details={"import_type": record.import_type.value, "mode": mode.value, "code": error.code},
    )
    db.commit()
    return error


def _evaluate(
    db: Session,
    ctx: StoreContext,
    record: DataImport,
    *,
    now: datetime,
    on_applied: ImportAppliedHandler | None,
) -> None:
    """Run the IMPORT-triggered evaluation in its own unit of work (STATE_MACHINES.md §4).

    The import is already committed, so a failing evaluation is logged and surfaced in the
    summary; it never undoes the import or fails the request.
    """
    if on_applied is None:
        return
    try:
        record.evaluation_run_id = on_applied(
            db, store_id=ctx.store_id, import_id=record.id, as_of=now, triggered_by=ctx.user.id
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("import_evaluation_failed", extra={"import_id": str(record.id)})
        try:
            record.summary = {
                **record.summary,
                "evaluation_error": (
                    "The exception evaluation after this import did not complete. The next "
                    "scheduled evaluation will include the imported data."
                ),
            }
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("import_evaluation_note_failed", extra={"import_id": str(record.id)})


# --- Discard and housekeeping --------------------------------------------------------------


def discard_import(
    db: Session, ctx: StoreContext, import_id: uuid.UUID, *, now: datetime
) -> ImportDetailOut:
    """VALIDATED -> DISCARDED; the stored file bytes are purged. Discarding twice is a no-op."""
    record = _load(db, ctx.store_id, import_id, lock=True)
    if record.status is ImportStatus.DISCARDED:
        db.rollback()
        return _detail(db, record)
    if record.status is not ImportStatus.VALIDATED:
        raise ConflictError(
            f"Only a VALIDATED import can be discarded; this one is {record.status.value}.",
            code="IMPORT_NOT_DISCARDABLE",
        )
    _discard(record)
    audit.record(
        db,
        action="import.discarded",
        organization_id=ctx.organization_id,
        store_id=ctx.store_id,
        actor_user_id=ctx.user.id,
        target_type="data_import",
        target_id=record.id,
        details={"import_type": record.import_type.value, "expired": _expired(record, now)},
    )
    db.commit()
    return _detail(db, record)


def _discard(record: DataImport) -> None:
    record.status = ImportStatus.DISCARDED
    record.content = None


def _expired(record: DataImport, now: datetime) -> bool:
    return record.expires_at is not None and record.expires_at <= now


def _refresh_lifecycle(record: DataImport, now: datetime) -> bool:
    """Lazy housekeeping on read (SYSTEM_ARCHITECTURE §11). Returns True if the record changed."""
    if record.status is ImportStatus.VALIDATED and _expired(record, now):
        _discard(record)
        return True
    if record.status is ImportStatus.APPLYING and record.updated_at < now - APPLYING_STALE_AFTER:
        record.status = ImportStatus.FAILED
        record.failure_reason = "IMPORT_INTERRUPTED: the apply did not finish; no data was changed."
        return True
    failed = record.status is ImportStatus.FAILED
    if failed and record.content is not None and _expired(record, now):
        record.content = None  # a failed import keeps its bytes only until the preview expiry
        return True
    return False


def _expire_previews(db: Session, store_id: uuid.UUID, now: datetime) -> bool:
    """Bulk form of ``_refresh_lifecycle`` for the store. The caller commits."""
    expired = db.execute(
        update(DataImport)
        .where(
            DataImport.store_id == store_id,
            DataImport.status == ImportStatus.VALIDATED,
            DataImport.expires_at <= now,
        )
        .values(status=ImportStatus.DISCARDED, content=None)
        .execution_options(synchronize_session=False)
        .returning(DataImport.id)
    ).all()
    stuck = db.execute(
        update(DataImport)
        .where(
            DataImport.store_id == store_id,
            DataImport.status == ImportStatus.APPLYING,
            DataImport.updated_at < now - APPLYING_STALE_AFTER,
        )
        .values(
            status=ImportStatus.FAILED,
            failure_reason="IMPORT_INTERRUPTED: the apply did not finish; no data was changed.",
        )
        .execution_options(synchronize_session=False)
        .returning(DataImport.id)
    ).all()
    purged = db.execute(
        update(DataImport)
        .where(
            DataImport.store_id == store_id,
            DataImport.status == ImportStatus.FAILED,
            DataImport.content.is_not(None),
            DataImport.expires_at <= now,
        )
        .values(content=None)
        .execution_options(synchronize_session=False)
        .returning(DataImport.id)
    ).all()
    return bool(expired or stuck or purged)


# --- Helpers -------------------------------------------------------------------------------


def _load(
    db: Session, store_id: uuid.UUID, import_id: uuid.UUID, *, lock: bool = False
) -> DataImport:
    stmt = select(DataImport).where(DataImport.id == import_id, DataImport.store_id == store_id)
    if lock:
        stmt = stmt.with_for_update()
    record = db.scalar(stmt)
    if record is None:
        raise NotFoundError("Import not found.")
    return record


def _store_lock_key(store_id: uuid.UUID) -> int:
    return int.from_bytes(store_id.bytes[:4], "big", signed=True)


def _out(record: DataImport) -> ImportOut:
    return ImportOut(
        id=record.id,
        import_type=record.import_type,
        status=record.status,
        mode=record.mode,
        original_filename=record.original_filename,
        file_sha256=record.file_sha256,
        size_bytes=record.size_bytes,
        row_count=record.row_count,
        summary=ImportSummary.model_validate(record.summary or {}),
        created_at=record.created_at,
        updated_at=record.updated_at,
        validated_at=record.validated_at,
        applied_at=record.applied_at,
        expires_at=record.expires_at,
        created_by=record.created_by,
        applied_by=record.applied_by,
        evaluation_run_id=record.evaluation_run_id,
        failure_reason=record.failure_reason,
        can_revalidate=record.status is ImportStatus.FAILED and record.content is not None,
    )


def _detail(db: Session, record: DataImport) -> ImportDetailOut:
    file_issues = db.scalars(
        select(ImportRowIssue)
        .where(ImportRowIssue.import_id == record.id, ImportRowIssue.row_number.is_(None))
        .order_by(*_ISSUE_TIEBREAK)
        .limit(FILE_ISSUE_LIMIT)
    ).all()
    return ImportDetailOut(
        **_out(record).model_dump(), file_issues=[_issue_out(i) for i in file_issues]
    )


def _issue_out(issue: ImportRowIssue) -> ImportIssueOut:
    return ImportIssueOut(
        id=issue.id,
        row_number=issue.row_number,
        column=issue.column,
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        raw_value=issue.raw_value,
    )
