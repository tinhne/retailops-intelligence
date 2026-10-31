/** One entry of `error.details` in the API error envelope (API_CONVENTIONS). */
export type ApiErrorDetail = {
  /** Field name for request validation errors (the last element of `loc`). */
  field?: string;
  message?: string;
  [key: string]: unknown;
};

type ApiErrorInit = {
  status: number;
  code: string;
  message: string;
  details?: ApiErrorDetail[];
  requestId?: string;
  retryAfterSeconds?: number;
};

/**
 * Every failed API call surfaces as an `ApiError`. `status` is 0 when the request never got a
 * response (offline, DNS, connection refused).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];
  readonly requestId?: string;
  readonly retryAfterSeconds?: number;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? [];
    this.requestId = init.requestId;
    this.retryAfterSeconds = init.retryAfterSeconds;
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

const GENERIC_SERVER_MESSAGE = "Something went wrong on our side.";
const UNAVAILABLE_MESSAGE = "The service is temporarily unavailable.";

/** The message to show a person: API messages for 4xx, generic text for 5xx and network. */
export function userMessage(error: unknown): string {
  if (!isApiError(error)) return GENERIC_SERVER_MESSAGE;
  if (error.isNetworkError) return "We couldn't reach the server. Check your connection and try again.";
  if ([502, 503, 504].includes(error.status)) return UNAVAILABLE_MESSAGE;
  if (error.isServerError) return GENERIC_SERVER_MESSAGE;
  return error.message;
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.ceil(seconds);
  const date = Date.parse(value);
  if (Number.isNaN(date)) return undefined;
  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

function asDetails(raw: unknown): ApiErrorDetail[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => {
      const loc = Array.isArray(item.loc) ? item.loc : undefined;
      const last = loc?.[loc.length - 1];
      return {
        ...item,
        field: typeof item.field === "string" ? item.field : typeof last === "string" ? last : undefined,
        message: typeof item.message === "string" ? item.message : undefined,
      };
    });
}

/** Builds an `ApiError` from a non-2xx response and its (possibly non-JSON) body. */
export async function errorFromResponse(response: Response): Promise<ApiError> {
  let envelope: unknown = null;
  try {
    envelope = await response.json();
  } catch {
    // Proxies and gateways can answer with HTML or an empty body.
  }
  const body =
    typeof envelope === "object" && envelope !== null && "error" in envelope
      ? (envelope as { error: Record<string, unknown> }).error
      : null;

  return new ApiError({
    status: response.status,
    code: typeof body?.code === "string" ? body.code : `HTTP_${response.status}`,
    message:
      typeof body?.message === "string"
        ? body.message
        : response.status >= 500
          ? GENERIC_SERVER_MESSAGE
          : "The request failed.",
    details: asDetails(body?.details),
    requestId:
      (typeof body?.request_id === "string" ? body.request_id : undefined) ??
      response.headers.get("x-request-id") ??
      undefined,
    retryAfterSeconds: parseRetryAfter(response.headers.get("retry-after")),
  });
}
