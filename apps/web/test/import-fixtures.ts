import type { ImportDetail, ImportIssue } from "@/lib/api/imports-api";

export function importFixture(overrides: Partial<ImportDetail> = {}): ImportDetail {
  return {
    id: "i1",
    import_type: "orders",
    status: "VALIDATED",
    mode: null,
    original_filename: "orders_2026-10-31.csv",
    file_sha256: "9f2c4e1a7b3d5c6e8f9012345678901234567890abcdef1234567890abcdef12",
    size_bytes: 422_502,
    row_count: 120,
    summary: {
      rows_total: 120,
      rows_valid: 116,
      rows_with_errors: 4,
      rows_with_warnings: 3,
      creates: 30,
      updates: 80,
      unchanged: 6,
      issue_counts_by_code: { INVALID_DATETIME: 4, TIMEZONE_ASSUMED: 3 },
      preview: [
        { row_number: 2, key: "KHK-100611", action: "UPDATE", changed_fields: ["status", "fulfillment_status"] },
        { row_number: 3, key: "KHK-100612", action: "CREATE", changed_fields: [] },
        { row_number: 4, key: "KHK-100613", action: "SKIP", changed_fields: [] },
      ],
      applied: null,
      evaluation_error: null,
    },
    created_at: "2026-10-31T12:00:00Z",
    updated_at: "2026-10-31T12:00:02Z",
    validated_at: "2026-10-31T12:00:02Z",
    applied_at: null,
    expires_at: "2026-11-01T12:00:02Z",
    created_by: "u1",
    applied_by: null,
    evaluation_run_id: null,
    failure_reason: null,
    can_revalidate: false,
    file_issues: [],
    ...overrides,
  };
}

export function issueFixture(overrides: Partial<ImportIssue> = {}): ImportIssue {
  return {
    id: "iss-1",
    row_number: 41,
    column: "placed_at",
    code: "INVALID_DATETIME",
    severity: "ERROR",
    message: "Not an ISO-8601 timestamp.",
    raw_value: "11/05/2026 2:00 PM",
    ...overrides,
  };
}
