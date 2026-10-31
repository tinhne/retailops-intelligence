"use client";

import { CircleAlert } from "lucide-react";

import { CopyButton } from "@/components/states/copy-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { isApiError, userMessage } from "@/lib/api/errors";

/** A field's validation message, linked to its input through `aria-describedby`. */
export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="flex items-center gap-1 text-xs text-tone-danger-fg">
      <CircleAlert aria-hidden className="size-3.5 shrink-0" />
      {message}
    </p>
  );
}

/** A failed submit: the API message and request ID, with the input kept for a retry. */
export function ServerError({ error }: { error: unknown }) {
  if (!error) return null;
  const requestId = isApiError(error) ? error.requestId : undefined;
  return (
    <Alert tone="danger" role="alert">
      <CircleAlert aria-hidden />
      <AlertDescription>
        <p>{userMessage(error)}</p>
        {requestId ? (
          <p className="flex items-center gap-1 text-xs">
            Request ID <code className="font-mono break-all">{requestId}</code>
            <CopyButton value={requestId} label="Copy request ID" />
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

/**
 * Field messages from a 422 envelope. FastAPI reports `loc` such as
 * `["body", "priority_weights", "severity", "HIGH"]`; the result is keyed by the dotted path
 * without `body` (`priority_weights.severity.HIGH`), so it matches react-hook-form names.
 */
export function validationFieldErrors(error: unknown): Map<string, string> {
  const fields = new Map<string, string>();
  if (!isApiError(error) || error.status !== 422) return fields;
  for (const detail of error.details) {
    const loc = Array.isArray(detail.loc) ? detail.loc.map(String) : [];
    if (loc[0] !== "body" || loc.length < 2 || !detail.message) continue;
    const path = loc.slice(1).join(".");
    if (!fields.has(path)) fields.set(path, detail.message.replace(/^Value error, /, ""));
  }
  return fields;
}
