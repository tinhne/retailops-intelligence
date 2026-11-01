import type { Schema } from "@retailops/contracts";

import { apiFetch } from "./client";

export type Conversation = Schema<"ConversationOut">;
export type ConversationDetail = Schema<"ConversationDetail">;
export type CopilotMessage = Schema<"MessageOut">;
export type CopilotTurn = Schema<"CopilotTurnOut">;
export type StructuredAnswer = Schema<"StructuredAnswer">;
export type AnswerMeta = Schema<"AnswerMeta">;
export type CopilotReference = Schema<"Reference">;
export type ToolCall = Schema<"ToolCallOut">;
export type ExceptionSummary = Schema<"ExceptionSummaryOut">;
export type NoteDraftResult = Schema<"NoteDraftOut">;
export type ConversationContext = Schema<"ConversationContext">;

const base = (storeId: string) => `/stores/${storeId}/copilot`;

/** The copilot reads through read-only tools and never changes data (S-14, docs/ai). */
export const copilotApi = {
  conversations: (storeId: string, signal?: AbortSignal) =>
    apiFetch<Schema<"Page_ConversationOut_">>(`${base(storeId)}/conversations`, { query: { page_size: 50 }, signal }),
  conversation: (storeId: string, conversationId: string, signal?: AbortSignal) =>
    apiFetch<ConversationDetail>(`${base(storeId)}/conversations/${conversationId}`, { signal }),
  create: (storeId: string, context: { context_type: ConversationContext; context_id?: string | null }) =>
    apiFetch<Conversation>(`${base(storeId)}/conversations`, { method: "POST", body: context }),
  ask: (storeId: string, conversationId: string, question: string) =>
    apiFetch<CopilotTurn>(`${base(storeId)}/conversations/${conversationId}/messages`, { method: "POST", body: { question } }),
  exceptionSummary: (storeId: string, exceptionId: string, refresh = false) =>
    apiFetch<ExceptionSummary>(`${base(storeId)}/exception-summaries`, { method: "POST", body: { exception_id: exceptionId, refresh } }),
  noteDraft: (storeId: string, exceptionId: string, userHint?: string) =>
    apiFetch<NoteDraftResult>(`${base(storeId)}/note-drafts`, {
      method: "POST",
      body: { exception_id: exceptionId, user_hint: userHint || undefined },
    }),
};

export const copilotKeys = {
  conversations: (storeId: string) => ["store", storeId, "copilot", "conversations"] as const,
  conversation: (storeId: string, conversationId: string) => ["store", storeId, "copilot", "conversations", conversationId] as const,
};
