/**
 * Typed wrappers over the AQOS endpoints this foundation reads.
 *
 * Read-only by design. Sprint 063 builds the shell, not the screens, so no
 * wrapper here calls a signal action, submits a paper order or starts a
 * backtest — those endpoints exist on the server and stay unreachable from
 * this app until a sprint deliberately opens them.
 */

import type { AqosApiClient } from "@/api/client";
import type {
  AccountSummary,
  BacktestSummary,
  LoginResult,
  Page,
  PaperSessionSummary,
  PredictionSummary,
  PromotionStatus,
  PromotionSummary,
  SessionUser,
  SignalDetail,
  SignalEvent,
  SignalReason,
  SignalSummary,
  SystemInfo,
} from "@/api/types";

export const API_PREFIX = "/api/v1";

/**
 * Paging options for a list endpoint.
 *
 * A type alias rather than an interface: only aliases get an implicit index
 * signature, which is what lets this be passed straight to the client's
 * query parameter without a cast at every call site.
 */
export type ListQuery = {
  readonly limit?: number;
  readonly offset?: number;
};

export const auth = {
  /** Exchange credentials for an opaque bearer token. */
  login(client: AqosApiClient, email: string, password: string, clientLabel?: string) {
    return client.post<LoginResult>(
      `${API_PREFIX}/auth/login`,
      { email, password, client_label: clientLabel },
      // The one call that must not send a stale token: logging in while
      // holding a dead one should still work.
      { anonymous: true },
    );
  },

  me(client: AqosApiClient) {
    return client.get<SessionUser>(`${API_PREFIX}/auth/me`);
  },

  logout(client: AqosApiClient) {
    return client.post<{ revoked: boolean }>(`${API_PREFIX}/auth/logout`);
  },
};

export const system = {
  info(client: AqosApiClient) {
    return client.get<SystemInfo>(`${API_PREFIX}/system/info`);
  },

  /** Liveness is public, so it answers before anybody has signed in. */
  live(client: AqosApiClient) {
    return client.get<{ status: string }>("/health/live", { anonymous: true });
  },
};

/**
 * What a caller may narrow a signal list by.
 *
 * `user_id` is deliberately absent. The backend already scopes every list to
 * the caller, and offering the field would only let somebody discover that
 * asking for another user is forbidden.
 */
export type SignalListQuery = ListQuery & {
  readonly symbol?: string;
  readonly status?: string;
  readonly source?: string;
  readonly action?: string;
  readonly generated_from?: string;
  readonly generated_to?: string;
};

export const signals = {
  list(client: AqosApiClient, query: SignalListQuery = {}) {
    return client.get<Page<SignalSummary>>(`${API_PREFIX}/signals`, { query });
  },

  get(client: AqosApiClient, signalId: string) {
    return client.get<SignalDetail>(`${API_PREFIX}/signals/${signalId}`);
  },

  events(client: AqosApiClient, signalId: string) {
    return client.get<Page<SignalEvent>>(
      `${API_PREFIX}/signals/${signalId}/events`,
    );
  },

  reasons(client: AqosApiClient, signalId: string) {
    return client.get<Page<SignalReason>>(
      `${API_PREFIX}/signals/${signalId}/reasons`,
    );
  },
};

export const predictions = {
  list(client: AqosApiClient, query: ListQuery = {}) {
    return client.get<Page<PredictionSummary>>(`${API_PREFIX}/predictions`, {
      query,
    });
  },

  get(client: AqosApiClient, predictionId: string) {
    return client.get<PredictionSummary>(
      `${API_PREFIX}/predictions/${predictionId}`,
    );
  },
};

export const models = {
  listPromotions(client: AqosApiClient, query: ListQuery = {}) {
    return client.get<Page<PromotionSummary>>(`${API_PREFIX}/models/promotions`, {
      query,
    });
  },

  /**
   * Whether one model is promoted.
   *
   * The answer may be `unknown`, which the UI must show as unknown rather than
   * resolving it to either of the other two.
   */
  promotionStatus(client: AqosApiClient, modelId: string) {
    return client.get<PromotionStatus>(
      `${API_PREFIX}/models/${modelId}/promotion-status`,
    );
  },
};

export const accounts = {
  list(client: AqosApiClient, query: ListQuery = {}) {
    return client.get<Page<AccountSummary>>(`${API_PREFIX}/accounts`, { query });
  },
};

export const paper = {
  listSessions(client: AqosApiClient, query: ListQuery = {}) {
    return client.get<Page<PaperSessionSummary>>(`${API_PREFIX}/paper/sessions`, {
      query,
    });
  },
};

export const backtests = {
  list(client: AqosApiClient, query: ListQuery = {}) {
    return client.get<Page<BacktestSummary>>(`${API_PREFIX}/backtests`, { query });
  },
};
