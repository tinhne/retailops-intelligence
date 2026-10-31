"""Aggregate and import tools: get_dashboard_summary, get_operational_trends, get_import_errors
(TOOL_CATALOG.md §2.1, §2.10, §2.11).

The dashboard and trends come from ``analytics.service``, the functions behind the analytics
endpoints. Import history is read with plain SELECTs: the imports service's list functions also do
lazy preview housekeeping (a write), which a read-only tool transaction must not attempt.
"""

import uuid
from typing import Any, Literal

from pydantic import AwareDatetime, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.ai.tools.base import (
    ToolArgs,
    ToolContext,
    ToolOutput,
    ToolSpec,
    check_since,
    not_found,
    ref,
)
from app.domains.ai.tools.sanitize import FILENAME_MAX, RAW_VALUE_MAX, TITLE_MAX, TextGuard
from app.domains.analytics import service as analytics
from app.domains.identity import store_service
from app.domains.identity.permissions import Permission
from app.domains.imports.models import DataImport, ImportRowIssue, ImportType, IssueSeverity
from app.domains.imports.schemas import ImportSummary

EXPOSURE_NOTE = (
    "exposure_by_category is the gross order-line value at risk (BR-404), not a measured "
    "financial impact; the sums are not additive across categories."
)
TREND_METRICS = Literal[
    "orders_placed",
    "units",
    "gmv",
    "exceptions_detected",
    "exceptions_resolved",
    "shipped_on_time",
    "shipped_late",
]
TREND_DEFINITIONS: dict[str, str] = {
    "orders_placed": "Orders with placed_at in the store-local day, any status.",
    "units": "Units on lines of orders placed in the day that count as sales (BR-150).",
    "gmv": "Σ total of paid orders placed in the day (gross; refunds not subtracted).",
    "exceptions_detected": "Exceptions first detected in the day.",
    "exceptions_resolved": "Exceptions resolved in the day, manual or automatic (not superseded).",
    "shipped_on_time": "Orders shipped in the day at or before their ship-by.",
    "shipped_late": "Orders shipped in the day after their ship-by.",
}
IMPORTS_CAP = 10


# --- get_dashboard_summary -----------------------------------------------------------------------


class DashboardArgs(ToolArgs):
    pass


def get_dashboard_summary(db: Session, ctx: ToolContext, _args: DashboardArgs) -> ToolOutput:
    settings = store_service.get_settings(db, ctx.store_id)
    store = ctx.store.store
    board = analytics.get_dashboard_summary(
        db,
        ctx.store_id,
        timezone=store.timezone,
        currency=store.currency,
        approaching_factor=settings.approaching_reorder_factor,
        as_of=ctx.as_of,
    )
    guard = TextGuard()
    active = board.active_exceptions
    freshness = board.data_freshness
    run = freshness.last_evaluation_run
    record: dict[str, Any] = {
        "ref": ctx.aggregate_ref("Dashboard summary"),
        "currency": board.currency,
        "active_exceptions": {
            "total": active.total,
            "by_severity": active.by_severity,
            "by_band": active.by_band,
            "by_category": active.by_category,
            "exposure_by_category": active.exposure_by_category,
            "unassigned": active.unassigned,
            "past_due": active.past_due,
            "reopened": active.reopened,
        },
        "attention": [
            {
                "ref": ref(
                    "exception", item.id, f"{item.reference} · {guard(item.title, TITLE_MAX)}"
                ),
                "severity": item.severity,
                "priority_band": item.priority_band,
                "priority_score": item.priority_score,
                "due_at": item.due_at,
                "is_past_due": item.is_past_due,
                "assignee": item.assignee_name,
            }
            for item in board.attention
        ],
        "orders": {
            "overdue_now": board.orders.overdue_count,
            "overdue_value": board.orders.overdue_value,
            "awaiting_shipment": board.orders.awaiting_shipment,
            "placed_today": board.sales_today.orders_placed,
        },
        "inventory": {
            "active_products": board.inventory.active_products,
            "oversold": board.inventory.oversold,
            "out_of_stock": board.inventory.out_of_stock,
            "below_reorder_point": board.inventory.below_reorder_point,
            "approaching_reorder_point": board.inventory.approaching_reorder_point,
        },
        "data_freshness": {
            "imports": [
                {
                    "ref": ref("import", item.import_id, f"{item.import_type.value} import"),
                    "import_type": item.import_type,
                    "applied_at": item.applied_at,
                }
                for item in freshness.imports
                if item.import_id is not None
            ],
            "last_evaluation_run": (
                {
                    "ref": ref("evaluation_run", run.id, f"Evaluation run ({run.trigger.value})"),
                    "trigger": run.trigger,
                    "status": run.status,
                    "as_of": run.as_of,
                    "finished_at": run.finished_at,
                }
                if run is not None
                else None
            ),
        },
    }
    notes = [EXPOSURE_NOTE, "past_due counts active exceptions with due_at before as_of."]
    if run is None:
        notes.append("No evaluation has run yet, so exception counts may be empty for that reason.")
    return ToolOutput(
        records=[guard.mark(record)],
        notes=notes,
        untrusted_fields=["records[].attention[].ref.label"],
    )


# --- get_operational_trends ----------------------------------------------------------------------


class TrendsArgs(ToolArgs):
    window_days: int = Field(default=14, ge=1, le=60)
    metrics: list[TREND_METRICS] | None = Field(default=None, max_length=7)


def get_operational_trends(db: Session, ctx: ToolContext, args: TrendsArgs) -> ToolOutput:
    store = ctx.store.store
    trends = analytics.get_trends(
        db,
        ctx.store_id,
        timezone=store.timezone,
        currency=store.currency,
        days=args.window_days,
        as_of=ctx.as_of,
    )
    names = list(dict.fromkeys(args.metrics or TREND_DEFINITIONS))
    record = {
        "ref": ctx.aggregate_ref(f"Operational trends, {args.window_days} days"),
        "timezone": trends.window.timezone,
        "currency": trends.currency,
        "days": [day.date.isoformat() for day in trends.days],
        "partial_last_day": True,
        "series": {name: [getattr(day, name) for day in trends.days] for name in names},
        "totals": {name: getattr(trends.totals, name) for name in names},
        "definitions": {name: TREND_DEFINITIONS[name] for name in names},
    }
    return ToolOutput(
        records=[record],
        data_window_from=trends.window.start,
        notes=["Counts only; no projection. The last day is partial (today so far)."],
    )


# --- get_import_errors ---------------------------------------------------------------------------


class ImportErrorsArgs(ToolArgs):
    import_id: uuid.UUID | None = None
    import_type: ImportType | None = None
    since: AwareDatetime | None = None
    severity: IssueSeverity | None = None
    codes: list[str] | None = Field(default=None, max_length=20)
    limit: int = Field(default=25, ge=1, le=50)


def _code_counts(db: Session, import_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ImportRowIssue.code, ImportRowIssue.severity, func.count())
        .where(ImportRowIssue.import_id == import_id)
        .group_by(ImportRowIssue.code, ImportRowIssue.severity)
        .order_by(func.count().desc(), ImportRowIssue.code)
    ).all()
    return [{"code": code, "severity": severity, "count": int(n)} for code, severity, n in rows]


def _import_record(db: Session, record: DataImport, guard: TextGuard) -> dict[str, Any]:
    summary = ImportSummary.model_validate(record.summary or {})
    label = f"{record.import_type.value} import"
    if record.applied_at is not None:
        label += f", {record.applied_at.date().isoformat()}"
    return {
        "ref": ref("import", record.id, label),
        "import_type": record.import_type,
        "status": record.status,
        "mode": record.mode,
        "original_filename": guard(record.original_filename, FILENAME_MAX),
        "row_count": record.row_count,
        "summary": {
            "rows_valid": summary.rows_valid,
            "rows_with_errors": summary.rows_with_errors,
            "rows_with_warnings": summary.rows_with_warnings,
            "new": summary.creates,
            "updated": summary.updates,
            "unchanged": summary.unchanged,
        },
        "created_at": record.created_at,
        "validated_at": record.validated_at,
        "applied_at": record.applied_at,
        "expires_at": record.expires_at,
        "failure_reason": guard(record.failure_reason, TITLE_MAX),
        "code_counts": _code_counts(db, record.id),
    }


def get_import_errors(db: Session, ctx: ToolContext, args: ImportErrorsArgs) -> ToolOutput:
    check_since(args.since, ctx, "since")
    codes = [c.strip().upper() for c in args.codes or [] if c.strip()]
    stmt = select(DataImport).where(DataImport.store_id == ctx.store_id)
    if args.import_id is not None:
        stmt = stmt.where(DataImport.id == args.import_id)
    if args.import_type is not None:
        stmt = stmt.where(DataImport.import_type == args.import_type)
    if args.since is not None:
        stmt = stmt.where(DataImport.created_at >= args.since)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    imports = db.scalars(
        stmt.order_by(DataImport.created_at.desc(), DataImport.id).limit(IMPORTS_CAP)
    ).all()
    if args.import_id is not None and not imports:
        raise not_found("import")

    records = []
    issues_truncated = False
    for item in imports:
        guard = TextGuard()
        record = _import_record(db, item, guard)
        if args.import_id is not None:
            issue_stmt = select(ImportRowIssue).where(ImportRowIssue.import_id == item.id)
            if args.severity is not None:
                issue_stmt = issue_stmt.where(ImportRowIssue.severity == args.severity)
            if codes:
                issue_stmt = issue_stmt.where(ImportRowIssue.code.in_(codes))
            limit = min(args.limit, ctx.max_rows)
            issues = db.scalars(
                issue_stmt.order_by(
                    ImportRowIssue.row_number.asc().nulls_first(),
                    ImportRowIssue.code,
                    ImportRowIssue.id,
                ).limit(limit + 1)
            ).all()
            issues_truncated = len(issues) > limit
            record["issues"] = [
                {
                    "row_number": issue.row_number,
                    "column": issue.column,
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": guard(issue.message, TITLE_MAX),
                    "raw_value": guard(issue.raw_value, RAW_VALUE_MAX),
                }
                for issue in issues[:limit]
            ]
        records.append(guard.mark(record))
    notes = []
    if not records:
        notes.append("No imports match in this store.")
    return ToolOutput(
        records=records,
        total_available=total,
        truncated=issues_truncated,
        data_window_from=args.since,
        notes=notes,
        untrusted_fields=[
            "records[].original_filename",
            "records[].failure_reason",
            "records[].issues[].raw_value",
            "records[].issues[].message",
        ],
    )


SPECS = (
    ToolSpec(
        name="get_dashboard_summary",
        description="Overview: active exception counts, overdue orders, inventory health and "
        "data freshness.",
        args_model=DashboardArgs,
        permission=Permission.DASHBOARD_READ,
        row_cap=1,
        handler=get_dashboard_summary,
    ),
    ToolSpec(
        name="get_import_errors",
        description="Recent CSV imports with status and issue-code counts, or one import's row "
        "issues.",
        args_model=ImportErrorsArgs,
        permission=Permission.IMPORTS_READ,
        row_cap=IMPORTS_CAP,
        handler=get_import_errors,
    ),
    ToolSpec(
        name="get_operational_trends",
        description="Daily operational counts over the last N store-local days; counts only, no "
        "projections.",
        args_model=TrendsArgs,
        permission=Permission.ANALYTICS_READ,
        row_cap=1,
        handler=get_operational_trends,
    ),
)
