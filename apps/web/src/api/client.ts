/**
 * The only place this app talks to the network.
 *
 * Everything goes through {@link AqosApiClient}: one place that knows the base
 * URL, attaches the bearer token, parses the AQOS error envelope and preserves
 * the request id. Scattering `fetch` across components would mean each of them
 * re-deciding all four, and a guard test fails the build if one tries.
 */

import { AqosApiError, networkError, parseApiError } from "@/api/errors";

export const AQOS_API_CLIENT_VERSION = "1.0";

export const REQUEST_ID_HEADER = "X-Request-ID";

/** Verbs this client will send. */
export type HttpMethod = "GET" | "POST";

/**
 * Query parameters, as any object of scalar values.
 *
 * Declared readonly and open so a closed interface like ``ListQuery`` can be
 * passed straight in; a `Record` index signature would force every caller to
 * cast, which is exactly the sort of noise that hides a real mistake.
 */
export type QueryValues = {
  readonly [key: string]: string | number | boolean | undefined;
};

export interface RequestOptions {
  readonly method?: HttpMethod;
  readonly body?: unknown;
  readonly query?: QueryValues;
  readonly signal?: AbortSignal;
  /** Send without a token even when one is held, for login and health. */
  readonly anonymous?: boolean;
}

/** Supplies the current bearer token, or nothing when signed out. */
export type TokenReader = () => string | null;

export interface AqosApiClientOptions {
  readonly baseUrl: string;
  readonly getToken?: TokenReader;
  readonly fetchImpl?: typeof fetch;
}

function buildQuery(query: QueryValues | undefined): string {
  if (!query) {
    return "";
  }

  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  }

  const rendered = params.toString();

  return rendered ? `?${rendered}` : "";
}

export class AqosApiClient {
  private readonly baseUrl: string;
  private readonly getToken: TokenReader;
  private readonly fetchImpl: typeof fetch;

  constructor(options: AqosApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.getToken = options.getToken ?? (() => null);
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  /**
   * Send one request and return its parsed body.
   *
   * Failures always become an {@link AqosApiError}, whether the server refused,
   * returned something unreadable, or was never reached at all — so a caller
   * has exactly one kind of thing to catch.
   */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? "GET";
    const headers: Record<string, string> = { Accept: "application/json" };
    const token = options.anonymous ? null : this.getToken();

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    let response: Response;

    try {
      response = await this.fetchImpl(
        `${this.baseUrl}${path}${buildQuery(options.query)}`,
        {
          method,
          headers,
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
          signal: options.signal,
        },
      );
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") {
        throw cause;
      }

      throw networkError();
    }

    // Read from the header as well as the body: a refusal produced by
    // middleware still carries the id, and a body that failed to parse has
    // none to give.
    const headerRequestId = response.headers.get(REQUEST_ID_HEADER);
    const payload = await this.readBody(response);

    if (!response.ok) {
      throw parseApiError(response.status, payload, headerRequestId);
    }

    return payload as T;
  }

  private async readBody(response: Response): Promise<unknown> {
    if (response.status === 204) {
      return null;
    }

    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  get<T>(path: string, options: Omit<RequestOptions, "method" | "body"> = {}) {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options: Omit<RequestOptions, "method"> = {}) {
    return this.request<T>(path, { ...options, method: "POST", body });
  }
}

export { AqosApiError };
