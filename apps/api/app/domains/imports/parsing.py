"""File-level checks and CSV parsing (BR-602, BR-603).

Uploads are read with the ``csv`` module and never evaluated. Anything that fails here rejects the
whole file (``REJECTED``) before a single row is validated.
"""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import BinaryIO

from app.domains.imports.models import IssueSeverity
from app.domains.imports.templates import ImportContract

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_DATA_ROWS = 20_000
MAX_FILENAME_LENGTH = 255
_READ_CHUNK_BYTES = 64 * 1024
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class FileIssue:
    """An issue that is not tied to one data row (row_number NULL)."""

    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.ERROR
    column: str | None = None
    raw_value: str | None = None


@dataclass(frozen=True)
class Upload:
    filename: str
    size_bytes: int
    sha256: str
    # At most MAX_FILE_BYTES + 1 bytes are retained; larger files are rejected anyway.
    content: bytes


@dataclass(frozen=True)
class ParsedRow:
    """One non-blank data row. ``row_number`` is the spreadsheet line number (header = 1)."""

    row_number: int
    values: dict[str, str]  # recognised column -> trimmed cell ("" when empty)
    extra_values: tuple[str, ...] = ()  # non-empty cells beyond the last header column


@dataclass(frozen=True)
class ParsedFile:
    columns: frozenset[str]  # recognised contract columns present in the header
    rows: list[ParsedRow]
    warnings: list[FileIssue] = field(default_factory=list)

    def has_column(self, name: str) -> bool:
        return name in self.columns


def clean_filename(filename: str | None) -> str:
    """Keep only the base name a browser sent; never trust a path."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name[:MAX_FILENAME_LENGTH]


def read_upload(stream: BinaryIO, filename: str | None) -> Upload:
    """Hash and measure the whole upload while keeping at most ``MAX_FILE_BYTES + 1`` bytes."""
    digest = hashlib.sha256()
    size = 0
    kept = bytearray()
    while chunk := stream.read(_READ_CHUNK_BYTES):
        digest.update(chunk)
        size += len(chunk)
        room = MAX_FILE_BYTES + 1 - len(kept)
        if room > 0:
            kept.extend(chunk[:room])
    return Upload(
        filename=clean_filename(filename),
        size_bytes=size,
        sha256=digest.hexdigest(),
        content=bytes(kept),
    )


def normalize_header(raw: str) -> str:
    """Headers are case- and whitespace-insensitive: `` Unit Price `` -> ``unit_price``."""
    return _WHITESPACE.sub("_", raw.strip().lower())


def check_upload(upload: Upload) -> FileIssue | None:
    """Extension, size and emptiness checks that need no decoding."""
    if not upload.filename.lower().endswith(".csv"):
        return FileIssue("FILE_TYPE", "Only .csv files can be imported.", raw_value=upload.filename)
    if upload.size_bytes > MAX_FILE_BYTES:
        return FileIssue(
            "FILE_TOO_LARGE",
            f"The file is {upload.size_bytes:,} bytes; the limit is {MAX_FILE_BYTES:,} bytes "
            "(5 MB).",
        )
    if upload.size_bytes == 0:
        return FileIssue("FILE_EMPTY", "The file is empty.")
    return None


def decode(content: bytes) -> str | FileIssue:
    """UTF-8 with an optional BOM (BR-602)."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        bad = content[exc.start : exc.start + 1].hex()
        line = content.count(b"\n", 0, exc.start) + 1
        return FileIssue(
            "FILE_ENCODING",
            f"The file is not valid UTF-8 (byte 0x{bad} on line {line}). "
            "Save it as 'CSV UTF-8' and upload it again.",
        )


def parse_csv(text: str, contract: ImportContract) -> ParsedFile | FileIssue:
    """Parse decoded text against a column contract.

    Returns a ``FileIssue`` for any file-level failure: empty file, duplicate or missing required
    headers, malformed CSV, or more than ``MAX_DATA_ROWS`` data rows. Unknown columns become
    ``UNKNOWN_COLUMN`` warnings and their values are ignored (BR-603).
    """
    if not text.strip():
        return FileIssue("FILE_EMPTY", "The file is empty.")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader, [])
        names = [normalize_header(cell) for cell in header]
        issue = _check_header(names, contract)
        if issue is not None:
            return issue
        known = set(contract.column_names)
        rows: list[ParsedRow] = []
        for index, cells in enumerate(reader, start=2):
            if not any(cell.strip() for cell in cells):
                continue  # blank lines are not data rows
            if len(rows) == MAX_DATA_ROWS:
                return FileIssue(
                    "TOO_MANY_ROWS",
                    f"The file has more than {MAX_DATA_ROWS:,} data rows. Split it into smaller "
                    "files.",
                )
            values = {
                name: (cells[i].strip() if i < len(cells) else "")
                for i, name in enumerate(names)
                if name in known
            }
            extra = tuple(cell for cell in cells[len(names) :] if cell.strip())
            rows.append(ParsedRow(row_number=index, values=values, extra_values=extra))
    except csv.Error as exc:
        return FileIssue("FILE_TYPE", f"The file is not valid CSV (line {reader.line_num}): {exc}.")
    if not rows:
        return FileIssue("FILE_EMPTY", "The file has a header row but no data rows.")
    warnings = [
        FileIssue(
            "UNKNOWN_COLUMN",
            f"Column '{raw.strip() or f'#{position}'}' is not part of the "
            f"{contract.import_type.value} format and was ignored.",
            severity=IssueSeverity.WARNING,
            column=(raw.strip() or f"#{position}")[:64],
        )
        for position, (raw, name) in enumerate(zip(header, names, strict=True), start=1)
        if name not in known
    ]
    return ParsedFile(
        columns=frozenset(n for n in names if n in known), rows=rows, warnings=warnings
    )


def _check_header(names: list[str], contract: ImportContract) -> FileIssue | None:
    present = [name for name in names if name]
    duplicates = sorted({name for name in present if present.count(name) > 1})
    if duplicates:
        return FileIssue(
            "DUPLICATE_COLUMN",
            f"The header repeats column(s): {', '.join(duplicates)}. Each column may appear once.",
            raw_value=", ".join(duplicates),
        )
    missing = [name for name in contract.required_columns if name not in present]
    if missing:
        return FileIssue(
            "MISSING_COLUMNS",
            f"Required column(s) missing: {', '.join(missing)}. Download the "
            f"{contract.import_type.value} template for the expected header.",
            raw_value=", ".join(missing),
        )
    return None
