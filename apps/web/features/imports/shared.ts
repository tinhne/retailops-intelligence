import type { ImportStatus } from "@/lib/status-maps";

/** Upload validation and apply run inside their requests, so these statuses are rare and short-lived. */
export const IN_FLIGHT: ImportStatus[] = ["UPLOADED", "VALIDATING", "APPLYING"];
export const POLL_MS = 2000;

export const formatFileSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
