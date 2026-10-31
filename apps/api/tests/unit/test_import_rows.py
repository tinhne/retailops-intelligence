"""Cell parsing, issue aggregation and summaries for import rows (BR-502, BR-503, BR-604)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domains.imports.models import IssueSeverity
from app.domains.imports.parsing import ParsedRow
from app.domains.imports.validation import (
    PREVIEW_LIMIT,
    Issue,
    IssueCollector,
    RowAction,
    RowPlan,
    RowReader,
    ValidationContext,
    ValidationResult,
    duplicate_check,
)
from app.domains.orders.models import OrderStatus

CTX = ValidationContext(
    store_id=uuid.uuid4(), currency="USD", timezone="America/New_York", fulfillment_sla_hours=48
)


def _reader(values: dict[str, str], row_number: int = 2) -> tuple[RowReader, IssueCollector]:
    collector = IssueCollector(CTX.timezone)
    row = ParsedRow(row_number=row_number, values=values)
    return RowReader(row, CTX, collector), collector


def _codes(collector: IssueCollector) -> list[str]:
    return [issue.code for issue in collector.finalize()]


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("-1.00", "NEGATIVE_VALUE"),
        ("1.005", "INVALID_NUMBER"),
        ("1,000.00", "INVALID_NUMBER"),
        ("1e3", "INVALID_NUMBER"),
        ("NaN", "INVALID_NUMBER"),
        ("abc", "INVALID_NUMBER"),
        ("10000000000.00", "INVALID_NUMBER"),
    ],
)
def test_br503_money_rejects_invalid_values(raw: str, code: str) -> None:
    reader, collector = _reader({"unit_price": raw})
    assert reader.money("unit_price") is None
    assert _codes(collector) == [code]


@pytest.mark.parametrize(("raw", "expected"), [("16", "16.00"), ("16.5", "16.50"), (".5", "0.50")])
def test_br503_money_is_decimal_with_two_places(raw: str, expected: str) -> None:
    reader, collector = _reader({"unit_price": raw})
    value = reader.money("unit_price")
    assert value == Decimal(expected)
    assert str(value) == expected
    assert collector.finalize() == []


@pytest.mark.parametrize(
    ("raw", "minimum", "code"),
    [
        ("-3", 0, "NEGATIVE_VALUE"),
        ("0", 1, "INVALID_INTEGER"),
        ("2.5", 0, "INVALID_INTEGER"),
        ("1_000", 0, "INVALID_INTEGER"),
        ("99999999999", 0, "INVALID_INTEGER"),
    ],
)
def test_integer_validation(raw: str, minimum: int, code: str) -> None:
    reader, collector = _reader({"quantity": raw})
    assert reader.integer("quantity", minimum=minimum) is None
    assert _codes(collector) == [code]


def test_required_empty_cell_is_reported() -> None:
    reader, collector = _reader({"sku": ""})
    assert reader.text("sku", max_length=64, required=True) is None
    assert _codes(collector) == ["REQUIRED"]
    assert reader.has_errors


def test_value_too_long() -> None:
    reader, collector = _reader({"sku": "X" * 65})
    assert reader.text("sku", max_length=64) is None
    assert _codes(collector) == ["VALUE_TOO_LONG"]


def test_enum_is_case_insensitive_and_reports_allowed_values() -> None:
    reader, collector = _reader({"status": "paid", "other": "LOST"})
    assert reader.enum("status", OrderStatus) is OrderStatus.PAID
    assert reader.enum("other", OrderStatus) is None
    [issue] = collector.finalize()
    assert issue.code == "INVALID_ENUM"
    assert "CREATED" in issue.message


def test_br502_timestamp_with_offset_is_converted_to_utc() -> None:
    reader, collector = _reader({"placed_at": "2026-10-28T14:05:00-04:00"})
    assert reader.timestamp("placed_at") == datetime(2026, 10, 28, 18, 5, tzinfo=UTC)
    assert collector.finalize() == []


def test_br502_naive_timestamps_use_store_zone_and_warn_once_per_column() -> None:
    collector = IssueCollector(CTX.timezone)
    for row_number, raw in ((2, "2026-10-28T14:05:00"), (3, "2026-11-02 09:00")):
        values = {"placed_at": raw}
        reader = RowReader(ParsedRow(row_number, values), CTX, collector)
        value = reader.timestamp("placed_at")
        assert value is not None
        assert value.tzinfo is not None
    issues = collector.finalize()

    assert len(issues) == 1
    [issue] = issues
    assert (issue.code, issue.severity, issue.row_number) == (
        "TIMEZONE_ASSUMED",
        IssueSeverity.WARNING,
        None,
    )
    assert issue.message.startswith("2 value(s) in placed_at")
    # EDT (−04:00) before the DST change on 2026-11-01, EST (−05:00) after it.
    values = {"a": "2026-10-28T14:05:00", "b": "2026-11-02T09:00:00"}
    reader = RowReader(ParsedRow(2, values), CTX, IssueCollector(CTX.timezone))
    assert reader.timestamp("a") == datetime(2026, 10, 28, 18, 5, tzinfo=UTC)
    assert reader.timestamp("b") == datetime(2026, 11, 2, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize("raw", ["2026-13-45T09:00:00", "30/10/2026 12:00", "yesterday"])
def test_invalid_datetime(raw: str) -> None:
    reader, collector = _reader({"placed_at": raw})
    assert reader.timestamp("placed_at") is None
    assert _codes(collector) == ["INVALID_DATETIME"]
    assert reader.datetime_failed


def test_extra_fields_are_a_row_error() -> None:
    collector = IssueCollector(CTX.timezone)
    reader = RowReader(ParsedRow(4, {}, ("oops",)), CTX, collector)
    assert reader.has_errors
    assert _codes(collector) == ["EXTRA_FIELDS"]


def test_br604_duplicates_are_errors_on_every_later_occurrence() -> None:
    collector = IssueCollector(CTX.timezone)
    seen: dict[str, int] = {}
    for row_number in (2, 3, 4):
        reader = RowReader(ParsedRow(row_number, {}), CTX, collector)
        duplicate_check(reader, seen, "KHK-1", "sku", "SKU")
    issues = collector.finalize()
    assert [(i.row_number, i.code) for i in issues] == [
        (3, "DUPLICATE_KEY_IN_FILE"),
        (4, "DUPLICATE_KEY_IN_FILE"),
    ]
    assert "row 2" in issues[0].message


def test_summary_counts_and_preview_limit() -> None:
    plans: list[RowPlan[None]] = [
        RowPlan(n, f"K{n}", RowAction.CREATE) for n in range(2, 2 + PREVIEW_LIMIT + 5)
    ]
    plans += [
        RowPlan(100, "K100", RowAction.UNCHANGED),
        RowPlan(101, "K101", RowAction.SKIP),
        RowPlan(102, "K102", RowAction.UPDATE, ("name",)),
    ]
    issues = [
        Issue(101, "sku", "REQUIRED", IssueSeverity.ERROR, "sku is required."),
        Issue(102, "unit_price", "PRICE_ZERO", IssueSeverity.WARNING, "zero"),
        Issue(102, "unit_cost", "NEGATIVE_MARGIN", IssueSeverity.WARNING, "margin"),
    ]
    result = ValidationResult(plans=plans, issues=issues)
    result.file_warnings = [Issue(None, "x", "UNKNOWN_COLUMN", IssueSeverity.WARNING, "x")]

    summary = result.summary()

    assert summary["rows_total"] == PREVIEW_LIMIT + 8
    assert summary["rows_with_errors"] == 1
    assert summary["rows_valid"] == PREVIEW_LIMIT + 7
    assert summary["rows_with_warnings"] == 1
    assert (summary["creates"], summary["updates"], summary["unchanged"]) == (
        PREVIEW_LIMIT + 5,
        1,
        1,
    )
    assert summary["issue_counts_by_code"] == {
        "NEGATIVE_MARGIN": 1,
        "PRICE_ZERO": 1,
        "REQUIRED": 1,
        "UNKNOWN_COLUMN": 1,
    }
    assert len(summary["preview"]) == PREVIEW_LIMIT
    assert summary["preview"][0] == {
        "row_number": 2,
        "key": "K2",
        "action": "CREATE",
        "changed_fields": [],
    }
