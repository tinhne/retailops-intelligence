import type { AnswerMeta, CopilotMessage, StructuredAnswer } from "@/lib/api/copilot-api";

export function answerFixture(overrides: Partial<StructuredAnswer> = {}): StructuredAnswer {
  return {
    summary: "Two exceptions need attention first: EXC-1010 and EXC-1015.",
    facts: [{ text: "EXC-1010 is a P1 oversold exception on KHK-KT-012.", refs: ["exception:exc-1", "product:p1"] }],
    metrics: [{ label: "Value at risk", value: "54.42", unit: "USD", formula: "sum(open line value)", refs: ["aggregate:t1"] }],
    estimates: [{ text: "Stock may run out in 3 days.", basis: "Based on the 28-day sales average" }],
    recommendations: [{ text: "Restock KHK-KT-012.", rationale: "Three paid orders are waiting." }],
    limitations: ["Data as of Oct 31, 10:00 AM EDT."],
    references: [
      { type: "exception", id: "exc-1", label: "EXC-1010" },
      { type: "product", id: "p1", label: "KHK-KT-012" },
      { type: "aggregate", id: "t1", label: "Dashboard summary" },
    ],
    data_window: { from: "2026-10-01T04:00:00Z", to: "2026-10-31T14:00:00Z" },
    generated_by: "deterministic",
    ...overrides,
  };
}

export function metaFixture(overrides: Partial<AnswerMeta> = {}): AnswerMeta {
  return {
    provider: "deterministic",
    model: null,
    fallback: { used: false, reason: null, notice: null },
    cache: { hit: false, generated_at: null },
    prompt_version: "v1",
    intent: "prioritise",
    tool_calls: [
      { tool_name: "list_exceptions", status: "SUCCESS", origin: "ROUTER", row_count: 12, duration_ms: 8 },
      { tool_name: "get_import_errors", status: "PERMISSION_DENIED", origin: "ROUTER", row_count: null, duration_ms: 1 },
    ],
    validation: { dropped_refs: 0, dropped_items: 0, flags: [] },
    as_of: "2026-10-31T14:00:00Z",
    latency_ms: 20,
    input_tokens: 0,
    output_tokens: 0,
    ...overrides,
  };
}

export function messagesFixture(): CopilotMessage[] {
  return [
    { id: "m1", role: "user", kind: "CHAT", created_at: "2026-10-31T14:00:00Z", text: "What should I work on first today?", answer: null, draft: null, meta: null },
    { id: "m2", role: "assistant", kind: "CHAT", created_at: "2026-10-31T14:00:01Z", text: null, answer: answerFixture(), draft: null, meta: metaFixture() },
  ];
}
