import { API_BASE, CSRF_COOKIE, CSRF_HEADER, readCookie } from "./client";
import { ApiError, errorFromResponse } from "./errors";

/** Upload progress: the fraction of the request body sent, or `null` when the size is unknown. */
export type UploadProgress = { phase: "uploading"; fraction: number | null } | { phase: "processing" };

function responseHeaders(raw: string): Headers {
  const headers = new Headers();
  for (const line of raw.trim().split(/[\r\n]+/)) {
    const index = line.indexOf(":");
    if (index > 0) headers.append(line.slice(0, index).trim(), line.slice(index + 1).trim());
  }
  return headers;
}

/**
 * Posts a multipart form like `apiFetch`, but through XMLHttpRequest, because `fetch` reports no
 * upload progress. Same origin, same CSRF header and the same `ApiError` on failure. Once the
 * body is sent the phase turns to "processing" (the API validates inside the request, S-12).
 */
export function uploadForm<T>(
  path: string,
  form: FormData,
  onProgress: (progress: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    xhr.setRequestHeader("Accept", "application/json");
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) xhr.setRequestHeader(CSRF_HEADER, csrf);

    xhr.upload.onprogress = (event) =>
      onProgress({ phase: "uploading", fraction: event.lengthComputable && event.total > 0 ? event.loaded / event.total : null });
    xhr.upload.onload = () => onProgress({ phase: "processing" });

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError({ status: xhr.status, code: "MALFORMED_RESPONSE", message: "The server sent an unreadable answer." }));
        }
        return;
      }
      const response = new Response(xhr.responseText || null, { status: xhr.status, headers: responseHeaders(xhr.getAllResponseHeaders()) });
      void errorFromResponse(response).then(reject);
    };
    xhr.onerror = () =>
      reject(new ApiError({ status: 0, code: "NETWORK_ERROR", message: "We couldn't reach the server. Check your connection and try again." }));
    xhr.onabort = () => reject(new DOMException("The upload was cancelled.", "AbortError"));

    if (signal) {
      if (signal.aborted) {
        reject(new DOMException("The upload was cancelled.", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(form);
  });
}
