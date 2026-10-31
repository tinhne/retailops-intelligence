"""Row validation primitives shared by every import type.

A validator turns each parsed row into a ``RowPlan`` (CREATE / UPDATE / UNCHANGED / SKIP) and
records ``Issue`` objects. Validation only reads the database; the same plans drive the apply step
after re-validation (STATE_MACHINES.md §4).
"""

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from app.domains.imports.models import IssueSeverity
from app.domains.imports.parsing import FileIssue, ParsedRow

PREVIEW_LIMIT = 50
_MAX_INT = 2_147_483_647  # PostgreSQL INTEGER
_MAX_MONEY = Decimal("9999999999.99")  # NUMERIC(12,2)
_CENT = Decimal("0.01")
_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
_RAW_VALUE_LIMIT = 500


class RowAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    UNCHANGED = "UNCHANGED"
    SKIP = "SKIP"  # the row has at least one ERROR and is never applied


@dataclass(frozen=True)
class Issue:
    row_number: int | None
    column: str | None
    code: str
    severity: IssueSeverity
    message: str
    raw_value: str | None = None

    @classmethod
    def from_file_issue(cls, issue: FileIssue) -> "Issue":
        return cls(None, issue.column, issue.code, issue.severity, issue.message, issue.raw_value)


@dataclass(frozen=True)
class ValidationContext:
    """Store facts the validators need (BR-004 currency, BR-502 time zone, BR-201 SLA)."""

    store_id: uuid.UUID
    currency: str
    timezone: str
    fulfillment_sla_hours: int

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class RowPlan[P]:
    row_number: int
    key: str
    action: RowAction
    changed_fields: tuple[str, ...] = ()
    payload: P | None = None  # validated data for CREATE / UPDATE rows


class IssueCollector:
    """Collects issues for one file and aggregates repetitive warnings.

    ``TIMEZONE_ASSUMED`` is reported once per column with a count (BR-502) instead of once per
    cell, so a file exported without offsets does not bury the real problems.
    """

    def __init__(self, zone_name: str) -> None:
        self.zone_name = zone_name
        self.issues: list[Issue] = []
        self._timezone_assumed: dict[str, list[tuple[int, str]]] = {}

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    def timezone_assumed(self, row_number: int, column: str, raw: str) -> None:
        self._timezone_assumed.setdefault(column, []).append((row_number, raw))

    def finalize(self) -> list[Issue]:
        aggregated = [
            Issue(
                row_number=None,
                column=column,
                code="TIMEZONE_ASSUMED",
                severity=IssueSeverity.WARNING,
                message=(
                    f"{len(cells)} value(s) in {column} have no UTC offset and were interpreted "
                    f"in the store time zone {self.zone_name} (first at row {cells[0][0]})."
                ),
                raw_value=_clip(cells[0][1]),
            )
            for column, cells in self._timezone_assumed.items()
        ]
        return aggregated + self.issues


class RowReader:
    """Typed access to one row's cells. Every problem becomes an ``Issue`` on the collector."""

    def __init__(
        self,
        row: ParsedRow,
        ctx: ValidationContext,
        collector: IssueCollector,
    ) -> None:
        self.row = row
        self.ctx = ctx
        self.collector = collector
        self.error_count = 0
        self.datetime_failed = False
        if row.extra_values:
            self.error(
                None,
                "EXTRA_FIELDS",
                f"The row has {len(row.extra_values)} more value(s) than the header has columns; "
                "check for an unquoted comma.",
                ", ".join(row.extra_values),
            )

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def raw(self, column: str) -> str:
        return self.row.values.get(column, "")

    def error(self, column: str | None, code: str, message: str, raw: str | None = None) -> None:
        self.error_count += 1
        self.collector.add(
            Issue(self.row.row_number, column, code, IssueSeverity.ERROR, message, _clip(raw))
        )

    def warning(self, column: str | None, code: str, message: str, raw: str | None = None) -> None:
        self.collector.add(
            Issue(self.row.row_number, column, code, IssueSeverity.WARNING, message, _clip(raw))
        )

    def _missing(self, column: str, required: bool) -> None:
        if required:
            self.error(column, "REQUIRED", f"{column} is required.")

    def text(self, column: str, *, max_length: int, required: bool = False) -> str | None:
        value = self.raw(column)
        if not value:
            self._missing(column, required)
            return None
        if len(value) > max_length:
            self.error(
                column,
                "VALUE_TOO_LONG",
                f"{column} is {len(value)} characters; the maximum is {max_length}.",
                value,
            )
            return None
        return value

    def enum[E: StrEnum](
        self,
        column: str,
        enum_cls: type[E],
        *,
        required: bool = False,
        allowed: tuple[E, ...] | None = None,
    ) -> E | None:
        value = self.raw(column)
        if not value:
            self._missing(column, required)
            return None
        choices = allowed or tuple(enum_cls)
        normalized = value.upper()
        for member in choices:
            if member.value == normalized:
                return member
        self.error(
            column,
            "INVALID_ENUM",
            f"{column} must be one of {', '.join(m.value for m in choices)}.",
            value,
        )
        return None

    def integer(
        self,
        column: str,
        *,
        required: bool = False,
        minimum: int | None = 0,
        maximum: int = _MAX_INT,
    ) -> int | None:
        value = self.raw(column)
        if not value:
            self._missing(column, required)
            return None
        if not _INTEGER.match(value) or abs(int(value)) > _MAX_INT:
            self.error(column, "INVALID_INTEGER", f"{column} must be a whole number.", value)
            return None
        number = int(value)
        if minimum is not None and number < minimum:
            if number < 0 <= minimum:
                self.error(column, "NEGATIVE_VALUE", f"{column} must not be negative.", value)
            else:
                self.error(
                    column, "INVALID_INTEGER", f"{column} must be at least {minimum}.", value
                )
            return None
        if number > maximum:
            self.error(column, "INVALID_INTEGER", f"{column} must be at most {maximum}.", value)
            return None
        return number

    def money(self, column: str, *, required: bool = False) -> Decimal | None:
        """A non-negative decimal with at most two decimal places (BR-503)."""
        value = self.raw(column)
        if not value:
            self._missing(column, required)
            return None
        try:
            number = Decimal(value) if _DECIMAL.match(value) else None
        except InvalidOperation:  # pragma: no cover - the pattern already guards this
            number = None
        if number is None:
            self.error(column, "INVALID_NUMBER", f"{column} must be a decimal number.", value)
            return None
        if number < 0:
            self.error(column, "NEGATIVE_VALUE", f"{column} must not be negative.", value)
            return None
        if number != number.quantize(_CENT) or number > _MAX_MONEY:
            self.error(
                column,
                "INVALID_NUMBER",
                f"{column} must have at most 2 decimal places and be below 10,000,000,000.",
                value,
            )
            return None
        return number.quantize(_CENT)

    def timestamp(self, column: str, *, required: bool = False) -> datetime | None:
        """ISO-8601. Without an offset the value is read in the store time zone (BR-502)."""
        value = self.raw(column)
        if not value:
            self._missing(column, required)
            return None
        try:
            parsed = datetime.fromisoformat(value)
            assumed = parsed.tzinfo is None
            if assumed:
                parsed = parsed.replace(tzinfo=self.ctx.zone)
            parsed = parsed.astimezone(UTC)
        except (ValueError, OverflowError):
            self.datetime_failed = True
            self.error(
                column,
                "INVALID_DATETIME",
                f"{column} must be an ISO-8601 date-time such as 2026-10-28T14:05:00-04:00.",
                value,
            )
            return None
        if assumed:
            self.collector.timezone_assumed(self.row.row_number, column, value)
        return parsed


@dataclass
class ValidationResult[P]:
    plans: list[RowPlan[P]]
    issues: list[Issue]
    file_warnings: list[Issue] = field(default_factory=list)

    @property
    def all_issues(self) -> list[Issue]:
        return self.file_warnings + self.issues

    @property
    def error_rows(self) -> set[int]:
        return {plan.row_number for plan in self.plans if plan.action is RowAction.SKIP}

    def count(self, action: RowAction) -> int:
        return sum(1 for plan in self.plans if plan.action is action)

    def summary(self) -> dict[str, Any]:
        warning_rows = {
            issue.row_number
            for issue in self.issues
            if issue.severity is IssueSeverity.WARNING and issue.row_number is not None
        }
        error_rows = self.error_rows
        preview = [
            {
                "row_number": plan.row_number,
                "key": plan.key,
                "action": plan.action.value,
                "changed_fields": list(plan.changed_fields),
            }
            for plan in self.plans
            if plan.action is not RowAction.UNCHANGED
        ][:PREVIEW_LIMIT]
        return {
            "rows_total": len(self.plans),
            "rows_valid": len(self.plans) - len(error_rows),
            "rows_with_errors": len(error_rows),
            "rows_with_warnings": len(warning_rows),
            "creates": self.count(RowAction.CREATE),
            "updates": self.count(RowAction.UPDATE),
            "unchanged": self.count(RowAction.UNCHANGED),
            "issue_counts_by_code": dict(
                sorted(Counter(issue.code for issue in self.all_issues).items())
            ),
            "preview": preview,
        }


def classify(
    row: RowReader, existing: object | None, changed: list[str]
) -> tuple[RowAction, tuple[str, ...]]:
    """Map a validated row to its action; rows with errors are always SKIP."""
    if row.has_errors:
        return RowAction.SKIP, ()
    if existing is None:
        return RowAction.CREATE, ()
    return (RowAction.UPDATE if changed else RowAction.UNCHANGED), tuple(changed)


def duplicate_check(
    row: RowReader, seen: dict[str, int], key: str | None, column: str, label: str
) -> None:
    """BR-604: every occurrence of a key after the first is a row error."""
    if key is None:
        return
    first = seen.get(key)
    if first is None:
        seen[key] = row.row.row_number
        return
    row.error(
        column,
        "DUPLICATE_KEY_IN_FILE",
        f"{label} {key} already appears in row {first}; each key may appear once per file.",
        key,
    )


def _clip(raw: str | None) -> str | None:
    if raw is None:
        return None
    return raw[:_RAW_VALUE_LIMIT]
