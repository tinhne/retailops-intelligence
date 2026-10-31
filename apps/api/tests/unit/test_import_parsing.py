"""File-level checks, CSV parsing and templates (BR-601..604). No database needed."""

import io
import os

import pytest

from app.domains.imports import parsing
from app.domains.imports.models import ImportType, IssueSeverity
from app.domains.imports.service import escape_cell
from app.domains.imports.templates import CONTRACTS, PRODUCTS, contract_for, render_template
from tests.factories_imports import PRODUCT_HEADER, SAMPLE_DATA, csv_bytes, product_row


def _upload(content: bytes, filename: str = "products.csv") -> parsing.Upload:
    return parsing.read_upload(io.BytesIO(content), filename)


def _parse(content: bytes) -> parsing.ParsedFile | parsing.FileIssue:
    text = parsing.decode(content)
    assert isinstance(text, str)
    return parsing.parse_csv(text, PRODUCTS)


def test_read_upload_hashes_whole_file_but_keeps_only_limit_plus_one_byte() -> None:
    content = b"x" * (parsing.MAX_FILE_BYTES + 10)

    upload = _upload(content)

    assert upload.size_bytes == parsing.MAX_FILE_BYTES + 10
    assert len(upload.content) == parsing.MAX_FILE_BYTES + 1
    assert len(upload.sha256) == 64


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("C:\\Users\\ops\\products.csv", "products.csv"), ("../../etc/x.csv", "x.csv"), (None, "")],
)
def test_clean_filename_keeps_only_the_base_name(filename: str | None, expected: str) -> None:
    assert parsing.clean_filename(filename) == expected


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("products.xlsx", b"sku\n", "FILE_TYPE"),
        ("products", b"sku\n", "FILE_TYPE"),
        ("products.csv", b"", "FILE_EMPTY"),
        ("products.csv", b"a" * (parsing.MAX_FILE_BYTES + 1), "FILE_TOO_LARGE"),
    ],
)
def test_br602_upload_checks(filename: str, content: bytes, code: str) -> None:
    issue = parsing.check_upload(_upload(content, filename))
    assert issue is not None
    assert issue.code == code


def test_br602_upload_at_exact_limit_and_uppercase_extension_pass() -> None:
    assert parsing.check_upload(_upload(b"a" * parsing.MAX_FILE_BYTES, "PRODUCTS.CSV")) is None


def test_br602_cp1252_byte_is_rejected_with_line_number() -> None:
    content = csv_bytes(PRODUCT_HEADER, product_row("KHK-1", name="Caf\xe9 Cup")).replace(
        "Café".encode(), "Café".encode("cp1252")
    )
    issue = parsing.decode(content)
    assert isinstance(issue, parsing.FileIssue)
    assert issue.code == "FILE_ENCODING"
    assert "0xe9" in issue.message
    assert "line 2" in issue.message


def test_br602_utf8_bom_is_accepted() -> None:
    text = parsing.decode(b"\xef\xbb\xbf" + csv_bytes(PRODUCT_HEADER, product_row("KHK-1")))
    assert isinstance(text, str)
    parsed = parsing.parse_csv(text, PRODUCTS)
    assert isinstance(parsed, parsing.ParsedFile)
    assert parsed.has_column("sku")


def test_headers_are_case_and_whitespace_insensitive() -> None:
    header = " SKU , Name ,Status, Unit Price ,REORDER_POINT"
    parsed = _parse(csv_bytes(header, "KHK-1,Mug,ACTIVE,16.00,4"))
    assert isinstance(parsed, parsing.ParsedFile)
    assert parsed.rows[0].values == {
        "sku": "KHK-1",
        "name": "Mug",
        "status": "ACTIVE",
        "unit_price": "16.00",
        "reorder_point": "4",
    }


def test_br603_missing_required_columns_reject_the_file() -> None:
    issue = _parse(csv_bytes("sku,name,status", "KHK-1,Mug,ACTIVE"))
    assert isinstance(issue, parsing.FileIssue)
    assert issue.code == "MISSING_COLUMNS"
    assert issue.raw_value == "unit_price, reorder_point"


def test_repeated_header_is_rejected() -> None:
    issue = _parse(csv_bytes(PRODUCT_HEADER + ",SKU", product_row("KHK-1") + ",KHK-2"))
    assert isinstance(issue, parsing.FileIssue)
    assert issue.code == "DUPLICATE_COLUMN"


def test_br603_unknown_columns_are_warnings_and_ignored() -> None:
    parsed = _parse(csv_bytes(PRODUCT_HEADER + ",barcode", product_row("KHK-1") + ",4006381333931"))
    assert isinstance(parsed, parsing.ParsedFile)
    assert [(w.code, w.severity, w.column) for w in parsed.warnings] == [
        ("UNKNOWN_COLUMN", IssueSeverity.WARNING, "barcode")
    ]
    assert "barcode" not in parsed.rows[0].values


def test_row_numbers_are_spreadsheet_lines_and_blank_lines_are_not_rows() -> None:
    content = csv_bytes(PRODUCT_HEADER, product_row("KHK-1"), ",,,,,,,,,", "", product_row("KHK-2"))
    parsed = _parse(content)
    assert isinstance(parsed, parsing.ParsedFile)
    assert [row.row_number for row in parsed.rows] == [2, 5]


def test_quoted_fields_with_commas_and_newlines_stay_one_row() -> None:
    row = '"KHK-1","Mug, Sage\nlarge",Drinkware,ACTIVE,16.00,5.40,10,30,,'
    parsed = _parse(csv_bytes(PRODUCT_HEADER, row, product_row("KHK-2")))
    assert isinstance(parsed, parsing.ParsedFile)
    assert parsed.rows[0].values["name"] == "Mug, Sage\nlarge"
    assert [r.row_number for r in parsed.rows] == [2, 3]


def test_extra_values_beyond_the_header_are_kept_for_validation() -> None:
    parsed = _parse(csv_bytes(PRODUCT_HEADER, product_row("KHK-1") + ",oops"))
    assert isinstance(parsed, parsing.ParsedFile)
    assert parsed.rows[0].extra_values == ("oops",)


def test_header_only_file_is_empty() -> None:
    issue = _parse(csv_bytes(PRODUCT_HEADER))
    assert isinstance(issue, parsing.FileIssue)
    assert issue.code == "FILE_EMPTY"


def test_br602_more_than_20000_data_rows_is_rejected() -> None:
    rows = [product_row(f"KHK-{i}") for i in range(parsing.MAX_DATA_ROWS + 1)]
    issue = _parse(csv_bytes(PRODUCT_HEADER, *rows))
    assert isinstance(issue, parsing.FileIssue)
    assert issue.code == "TOO_MANY_ROWS"


def test_br602_exactly_20000_data_rows_is_accepted() -> None:
    rows = [product_row(f"KHK-{i}") for i in range(parsing.MAX_DATA_ROWS)]
    parsed = _parse(csv_bytes(PRODUCT_HEADER, *rows))
    assert isinstance(parsed, parsing.ParsedFile)
    assert len(parsed.rows) == parsing.MAX_DATA_ROWS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('=HYPERLINK("http://x")', '\'=HYPERLINK("http://x")'),
        ("+1", "'+1"),
        ("-12.00", "'-12.00"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("\rcmd", "'\rcmd"),
        ("KHK-1", "KHK-1"),
        (None, ""),
        (7, "7"),
    ],
)
def test_escape_cell_neutralises_formula_injection(value: object, expected: str) -> None:
    assert escape_cell(value) == expected


def test_br601_every_type_has_a_contract_whose_template_parses_cleanly() -> None:
    assert set(CONTRACTS) == set(ImportType)
    for import_type in ImportType:
        parsed = parsing.parse_csv(render_template(import_type), contract_for(import_type))
        assert isinstance(parsed, parsing.ParsedFile)
        assert parsed.warnings == []
        assert len(parsed.rows) == 2


@pytest.mark.skipif(not os.path.isdir(SAMPLE_DATA), reason="sample-data/ is not available")
@pytest.mark.parametrize("import_type", list(ImportType))
def test_sample_data_templates_match_the_contract(import_type: ImportType) -> None:
    path = os.path.join(SAMPLE_DATA, "templates", f"{import_type.value}.csv")
    with open(path, encoding="utf-8", newline="") as handle:
        assert handle.read() == render_template(import_type)
