import { describe, expect, it, vi } from "vitest";

import { AqosApiClient, REQUEST_ID_HEADER } from "@/api/client";
import type { AqosApiError} from "@/api/errors";
import { API_ERROR_CODES, isAqosApiError } from "@/api/errors";

const BASE = "http://localhost:8000";

function jsonResponse(status: number, body: unknown, requestId = "req_1"): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      [REQUEST_ID_HEADER]: requestId,
    },
  });
}

function envelope(code: string, message: string, details: object = {}) {
  return { error: { code, message, details, request_id: "req_from_body" } };
}

function buildClient(
  impl: typeof fetch,
  getToken: () => string | null = () => null,
): AqosApiClient {
  return new AqosApiClient({ baseUrl: BASE, getToken, fetchImpl: impl });
}

type FetchMock = { mock: { calls: unknown[][] } };

function requestInit(fetchImpl: FetchMock): RequestInit {
  const call = fetchImpl.mock.calls[0];

  if (!call) {
    throw new Error("fetch was never called");
  }

  return call[1] as RequestInit;
}

function requestHeaders(fetchImpl: FetchMock): Record<string, string> {
  return (requestInit(fetchImpl).headers ?? {}) as Record<string, string>;
}

function requestUrl(fetchImpl: FetchMock): string {
  const call = fetchImpl.mock.calls[0];

  if (!call) {
    throw new Error("fetch was never called");
  }

  return String(call[0]);
}

async function captureError(promise: Promise<unknown>): Promise<AqosApiError> {
  try {
    await promise;
  } catch (cause) {
    if (isAqosApiError(cause)) {
      return cause;
    }

    throw cause;
  }

  throw new Error("the request should have failed");
}

describe("AqosApiClient success paths", () => {
  it("parses a successful body", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { total: 2, items: [] }));
    const result = await buildClient(fetchImpl as unknown as typeof fetch).get<{
      total: number;
    }>("/api/v1/signals");

    expect(result.total).toBe(2);
  });

  it("attaches the bearer token", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));

    await buildClient(fetchImpl as unknown as typeof fetch, () => "tok_abc").get(
      "/api/v1/signals",
    );

    const headers = requestHeaders(fetchImpl);

    expect(headers["Authorization"]).toBe("Bearer tok_abc");
  });

  it("sends no token when signed out", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));

    await buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals");

    expect(requestHeaders(fetchImpl)["Authorization"]).toBeUndefined();
  });

  it("omits the token on purpose for anonymous calls", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(201, {}));

    await buildClient(fetchImpl as unknown as typeof fetch, () => "stale").post(
      "/api/v1/auth/login",
      { email: "a@b.c", password: "x" },
      { anonymous: true },
    );

    expect(requestHeaders(fetchImpl)["Authorization"]).toBeUndefined();
  });

  it("builds a query string and drops undefined values", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));

    await buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals", {
      query: { limit: 10, offset: undefined, symbol: "XAUUSD" },
    });

    expect(requestUrl(fetchImpl)).toBe(
      BASE + "/api/v1/signals?limit=10&symbol=XAUUSD",
    );
  });
});

describe("AqosApiClient error handling", () => {
  const cases = [
    { status: 401, code: API_ERROR_CODES.unauthorized },
    { status: 403, code: API_ERROR_CODES.forbidden },
    { status: 404, code: API_ERROR_CODES.notFound },
    { status: 409, code: API_ERROR_CODES.conflict },
    { status: 413, code: API_ERROR_CODES.payloadTooLarge },
    { status: 429, code: API_ERROR_CODES.rateLimited },
    { status: 503, code: API_ERROR_CODES.notReady },
  ];

  it.each(cases)("turns $status into an AqosApiError", async ({ status, code }) => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(status, envelope(code, "Refused.")),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.status).toBe(status);
    expect(error.code).toBe(code);
  });

  it("preserves the request id from the body", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(403, envelope(API_ERROR_CODES.forbidden, "No.")),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.requestId).toBe("req_from_body");
  });

  it("falls back to the header request id when the body has none", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response("not json at all", {
          status: 429,
          headers: { [REQUEST_ID_HEADER]: "req_from_header" },
        }),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.requestId).toBe("req_from_header");
    expect(error.code).toBe(API_ERROR_CODES.unreadable);
  });

  it("keeps the structured details", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        429,
        envelope(API_ERROR_CODES.rateLimited, "Slow down.", {
          retry_after_seconds: 30,
        }),
      ),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.retryAfterSeconds).toBe(30);
    expect(error.isRetryable).toBe(true);
  });

  it("classifies an unauthenticated failure", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(401, envelope(API_ERROR_CODES.unauthorized, "No token.")),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.isUnauthenticated).toBe(true);
    expect(error.isForbidden).toBe(false);
  });

  it("reports an unreachable API as a network error", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("connection refused");
    });
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.code).toBe(API_ERROR_CODES.network);
    expect(error.status).toBe(0);
  });

  it("never invents a retry delay", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(503, envelope(API_ERROR_CODES.notReady, "Not ready.")),
    );
    const error = await captureError(
      buildClient(fetchImpl as unknown as typeof fetch).get("/api/v1/signals"),
    );

    expect(error.retryAfterSeconds).toBeNull();
  });
});
