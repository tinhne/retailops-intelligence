import { API_BASE } from "./client";
import { errorFromResponse } from "./errors";

/**
 * Downloads a file the API serves (CSV templates, issue exports) through `fetch`, so a failure
 * surfaces as an `ApiError` the caller can toast instead of a downloaded error body.
 */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "same-origin" });
  if (!response.ok) throw await errorFromResponse(response);
  const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
