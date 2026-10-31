"""API input and output schemas for the imports module."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.imports.models import ImportMode, ImportStatus, ImportType, IssueSeverity
from app.domains.imports.validation import RowAction

ImportSort = Literal[
    "created_at",
    "-created_at",
    "applied_at",
    "-applied_at",
    "status",
    "-status",
    "import_type",
    "-import_type",
]
IssueSort = Literal["row_number", "-row_number", "code", "-code", "severity", "-severity"]


class PreviewRow(BaseModel):
    row_number: int
    key: str
    action: RowAction
    changed_fields: list[str]


class AppliedCounts(BaseModel):
    mode: ImportMode
    creates: int
    updates: int
    unchanged: int
    skipped: int


class ImportSummary(BaseModel):
    """Validation counts and the first planned changes (summary JSON of ``data_import``)."""

    rows_total: int = 0
    rows_valid: int = 0
    rows_with_errors: int = 0
    rows_with_warnings: int = 0
    creates: int = 0
    updates: int = 0
    unchanged: int = 0
    issue_counts_by_code: dict[str, int] = Field(default_factory=dict)
    preview: list[PreviewRow] = Field(default_factory=list)
    applied: AppliedCounts | None = None
    evaluation_error: str | None = None


class ImportIssueOut(BaseModel):
    id: uuid.UUID
    row_number: int | None
    column: str | None
    code: str
    severity: IssueSeverity
    message: str
    raw_value: str | None


class ImportOut(BaseModel):
    id: uuid.UUID
    import_type: ImportType
    status: ImportStatus
    mode: ImportMode | None
    original_filename: str
    file_sha256: str
    size_bytes: int
    row_count: int | None
    summary: ImportSummary
    created_at: datetime
    updated_at: datetime
    validated_at: datetime | None
    applied_at: datetime | None
    expires_at: datetime | None
    created_by: uuid.UUID | None
    applied_by: uuid.UUID | None
    evaluation_run_id: uuid.UUID | None
    failure_reason: str | None


class ImportDetailOut(ImportOut):
    """An import plus its file-level issues (row_number NULL): why it was rejected, warnings."""

    file_issues: list[ImportIssueOut]


class ApplyImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ImportMode = ImportMode.STRICT
    confirm_skipped_rows: int | None = Field(default=None, ge=0)
