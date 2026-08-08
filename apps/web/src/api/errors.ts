/**
 * The AQOS error envelope, as the browser sees it.
 *
 * Every backend failure arrives in one shape, and this module is the only
 * place that knows it. The `request_id` is carried through deliberately: it is
 * what ties a user's screenshot to a logged failure, and it is useless if the
 * client drops it on the way to the screen.
 */

export const AQOS_API_ERRORS_VERSION = "1.0";

export interface AqosApiErrorBody {
  readonly code: string;
  readonly message: string;
  readonly details: Record<string, unknown>;
  readonly request_id: string | null;
}

export interface AqosApiErrorEnvelope {
  readonly error: AqosApiErrorBody;
}

/** What the UI shows when the server said nothing intelligible. */
export const UNREADABLE_ERROR_MESSAGE =
  "The server returned a response this app could not read.";

export const NETWORK_ERROR_MESSAGE =
  "The AQOS API could not be reached. Check your connection and try again.";

/**
 * Codes the UI reacts to structurally rather than by reading the message.
 *
 * Messages are for people; a screen that changes behaviour should key off the
 * code, which is stable.
 */
export const API_ERROR_CODES = {
  validation: "validation_error",
  notFound: "not_found",
  conflict: "conflict",
  unauthorized: "unauthorized",
  forbidden: "forbidden",
  rateLimited: "rate_limited",
  payloadTooLarge: "payload_too_large",
  databaseUnavailable: "database_unavailable",
  notReady: "not_ready",
  internal: "internal_error",
  network: "network_error",
  unreadable: "unreadable_response",
} as const;

export class AqosApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(init: {
    code: string;
    message: string;
    status: number;
    details?: Record<string, unknown>;
    requestId?: string | null;
  }) {
    super(init.message);

    this.name = "AqosApiError";
    this.code = init.code;
    this.status = init.status;
    this.details = init.details ?? {};
    this.requestId = init.requestId ?? null;
  }

  /** Whether the caller should be sent back to the login screen. */
  get isUnauthenticated(): boolean {
    return this.status === 401 || this.code === API_ERROR_CODES.unauthorized;
  }

  /** Whether the caller is known but not allowed to do this. */
  get isForbidden(): boolean {
    return this.status === 403 || this.code === API_ERROR_CODES.forbidden;
  }

  /** Whether waiting and retrying is the right response. */
  get isRetryable(): boolean {
    return (
      this.status === 429 ||
      this.status === 503 ||
      this.code === API_ERROR_CODES.rateLimited ||
      this.code === API_ERROR_CODES.notReady ||
      this.code === API_ERROR_CODES.databaseUnavailable
    );
  }

  /** Seconds to wait, when the server said. Never a guess. */
  get retryAfterSeconds(): number | null {
    const value = this.details["retry_after_seconds"];

    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Turn a failed response body into an error, without trusting its shape.
 *
 * A proxy, a load balancer or a crash can produce something that is not the
 * AQOS envelope at all, so every field is checked rather than assumed. What
 * cannot be read becomes an honest "unreadable" rather than an empty message.
 */
export function parseApiError(
  status: number,
  body: unknown,
  fallbackRequestId: string | null = null,
): AqosApiError {
  if (!isRecord(body) || !isRecord(body["error"])) {
    return new AqosApiError({
      code: API_ERROR_CODES.unreadable,
      message: UNREADABLE_ERROR_MESSAGE,
      status,
      requestId: fallbackRequestId,
    });
  }

  const error = body["error"];
  const code = typeof error["code"] === "string" ? error["code"] : API_ERROR_CODES.unreadable;
  const message =
    typeof error["message"] === "string" && error["message"].trim()
      ? error["message"]
      : UNREADABLE_ERROR_MESSAGE;
  const details = isRecord(error["details"]) ? error["details"] : {};
  const requestId =
    typeof error["request_id"] === "string" && error["request_id"]
      ? error["request_id"]
      : fallbackRequestId;

  return new AqosApiError({ code, message, status, details, requestId });
}

/** The error for a request that never reached the API. */
export function networkError(requestId: string | null = null): AqosApiError {
  return new AqosApiError({
    code: API_ERROR_CODES.network,
    message: NETWORK_ERROR_MESSAGE,
    status: 0,
    requestId,
  });
}

export function isAqosApiError(value: unknown): value is AqosApiError {
  return value instanceof AqosApiError;
}
