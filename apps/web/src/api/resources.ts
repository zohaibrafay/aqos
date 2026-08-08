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
  AccountAnalytics,
  AccountDetail,
  AccountSummary,
  AnalyticsSnapshot,
  ExecutionConstraints,
  FundedRules,
  ReportDetail,
  ReportSummary,
  BacktestSummary,
  LoginResult,
  Page,
  BacktestRow,
  PaperDecision,
  PaperFill,
  PaperOrder,
  PaperPosition,
  PaperSessionDetail,
  PaperSessionResult,
  PaperSessionSummary,
  PaperTrade,
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

/**
 * The lifecycle result the server returns for every action.
 *
 * The signal comes back as the server now holds it, which is what lets the UI
 * refuse to change a status until the transition actually happened.
 */
export interface SignalActionResult {
  readonly signal: SignalDetail;
  readonly event: SignalEvent | null;
  readonly reason: SignalReason | null;
}

/**
 * The lifecycle actions this app may take.
 *
 * An allow list, not a template. Every value here is a Sprint 059 signal
 * lifecycle endpoint; none of them places an order, touches an account or
 * reaches a broker, and `executed` and `failed` have no entry because those
 * describe what a broker did.
 */
export const SIGNAL_ACTIONS = {
  approve: "approve",
  reject: "reject",
  miss: "miss",
  expire: "expire",
  cancel: "cancel",
  markPendingApproval: "mark-pending-approval",
} as const;

export type SignalActionName =
  (typeof SIGNAL_ACTIONS)[keyof typeof SIGNAL_ACTIONS];

function actionPath(signalId: string, action: SignalActionName): string {
  return `${API_PREFIX}/signals/${signalId}/${action}`;
}

export const signalActions = {
  approve(client: AqosApiClient, signalId: string, note?: string) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.approve),
      note ? { note } : {},
    );
  },

  markPendingApproval(client: AqosApiClient, signalId: string, note?: string) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.markPendingApproval),
      note ? { note } : {},
    );
  },

  /**
   * Refuse a signal, with a taxonomy code.
   *
   * Only the code and an optional human message are sent. The category and the
   * severity are resolved from the code on the server, and no metadata is sent
   * at all — the API refuses unknown fields, and there is nothing here a client
   * should be deciding.
   */
  reject(
    client: AqosApiClient,
    signalId: string,
    reasonCode: string,
    message?: string,
  ) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.reject),
      message ? { reason_code: reasonCode, message } : { reason_code: reasonCode },
    );
  },

  miss(
    client: AqosApiClient,
    signalId: string,
    reasonCode: string,
    message?: string,
  ) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.miss),
      message ? { reason_code: reasonCode, message } : { reason_code: reasonCode },
    );
  },

  /** Retire a signal whose expiry has passed. The server checks that it has. */
  expire(client: AqosApiClient, signalId: string) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.expire),
    );
  },

  /** Withdraw a signal deliberately. The note is required by the API. */
  cancel(client: AqosApiClient, signalId: string, note: string) {
    return client.post<SignalActionResult>(
      actionPath(signalId, SIGNAL_ACTIONS.cancel),
      { note },
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

/**
 * What a caller may narrow their account list by.
 *
 * No `user_id`, for the same reason signals has none: the backend scopes every
 * list to the caller already.
 */
export type AccountListQuery = ListQuery & {
  readonly account_type?: string;
  readonly venue?: string;
  readonly status?: string;
  readonly execution_mode?: string;
};

/**
 * Account reads. Every method is a GET.
 *
 * There is no create, update or delete here, and no way to change an execution
 * mode, toggle auto-trade or edit a funded rule. Those endpoints do not exist
 * on the server either; this module simply does not invent them.
 */
export const accounts = {
  list(client: AqosApiClient, query: AccountListQuery = {}) {
    return client.get<Page<AccountSummary>>(`${API_PREFIX}/accounts`, { query });
  },

  get(client: AqosApiClient, accountId: string) {
    return client.get<AccountDetail>(`${API_PREFIX}/accounts/${accountId}`);
  },

  executionConstraints(client: AqosApiClient, accountId: string) {
    return client.get<ExecutionConstraints>(
      `${API_PREFIX}/accounts/${accountId}/execution-constraints`,
    );
  },

  fundedRules(client: AqosApiClient, accountId: string) {
    return client.get<FundedRules | null>(
      `${API_PREFIX}/accounts/${accountId}/funded-rules`,
    );
  },

  analytics(client: AqosApiClient, accountId: string) {
    return client.get<AccountAnalytics>(
      `${API_PREFIX}/accounts/${accountId}/analytics`,
    );
  },

  analyticsSnapshots(
    client: AqosApiClient,
    accountId: string,
    query: ListQuery = {},
  ) {
    return client.get<Page<AnalyticsSnapshot>>(
      `${API_PREFIX}/accounts/${accountId}/analytics/snapshots`,
      { query },
    );
  },

  reports(client: AqosApiClient, accountId: string, query: ListQuery = {}) {
    return client.get<Page<ReportSummary>>(
      `${API_PREFIX}/accounts/${accountId}/reports`,
      { query },
    );
  },

  report(client: AqosApiClient, accountId: string, reportId: string) {
    return client.get<ReportDetail>(
      `${API_PREFIX}/accounts/${accountId}/reports/${reportId}`,
    );
  },
};

/**
 * What a caller may narrow their paper sessions by.
 *
 * No `user_id`: the backend scopes every list to the caller already.
 */
export type PaperSessionListQuery = ListQuery & {
  readonly account_id?: string;
  readonly session_type?: string;
  readonly status?: string;
  readonly symbol?: string;
  readonly strategy_name?: string;
  readonly model_id?: string;
  readonly started_from?: string;
  readonly started_to?: string;
};

/**
 * Paper trading reads. Every method is a GET.
 *
 * Simulated activity only, and only ever read here. Creating a session,
 * submitting an order or closing a position are decisions with their own
 * confirmation rules; they are not part of this module.
 */
export const paper = {
  listSessions(client: AqosApiClient, query: PaperSessionListQuery = {}) {
    return client.get<Page<PaperSessionSummary>>(`${API_PREFIX}/paper/sessions`, {
      query,
    });
  },

  getSession(client: AqosApiClient, sessionId: string) {
    return client.get<PaperSessionDetail>(`${API_PREFIX}/paper/sessions/${sessionId}`);
  },

  result(client: AqosApiClient, sessionId: string) {
    return client.get<PaperSessionResult>(
      `${API_PREFIX}/paper/sessions/${sessionId}/result`,
    );
  },

  orders(client: AqosApiClient, sessionId: string, query: ListQuery = {}) {
    return client.get<Page<PaperOrder>>(
      `${API_PREFIX}/paper/sessions/${sessionId}/orders`,
      { query },
    );
  },

  fills(client: AqosApiClient, sessionId: string, query: ListQuery = {}) {
    return client.get<Page<PaperFill>>(
      `${API_PREFIX}/paper/sessions/${sessionId}/fills`,
      { query },
    );
  },

  positions(client: AqosApiClient, sessionId: string, query: ListQuery = {}) {
    return client.get<Page<PaperPosition>>(
      `${API_PREFIX}/paper/sessions/${sessionId}/positions`,
      { query },
    );
  },

  trades(client: AqosApiClient, sessionId: string, query: ListQuery = {}) {
    return client.get<Page<PaperTrade>>(
      `${API_PREFIX}/paper/sessions/${sessionId}/trades`,
      { query },
    );
  },

  decisions(client: AqosApiClient, sessionId: string, query: ListQuery = {}) {
    return client.get<Page<PaperDecision>>(
      `${API_PREFIX}/paper/sessions/${sessionId}/decisions`,
      { query },
    );
  },
};

export type BacktestListQuery = ListQuery & {
  readonly kind?: string;
  readonly symbol?: string;
  readonly strategy_name?: string;
};

/** Historical backtest reads. Every method is a GET. */
export const backtests = {
  list(client: AqosApiClient, query: BacktestListQuery = {}) {
    return client.get<Page<BacktestSummary>>(`${API_PREFIX}/backtests`, { query });
  },

  get(client: AqosApiClient, backtestId: string) {
    return client.get<BacktestSummary>(`${API_PREFIX}/backtests/${backtestId}`);
  },

  trades(client: AqosApiClient, backtestId: string, query: ListQuery = {}) {
    return client.get<Page<BacktestRow>>(
      `${API_PREFIX}/backtests/${backtestId}/trades`,
      { query },
    );
  },

  orders(client: AqosApiClient, backtestId: string, query: ListQuery = {}) {
    return client.get<Page<BacktestRow>>(
      `${API_PREFIX}/backtests/${backtestId}/orders`,
      { query },
    );
  },

  equity(client: AqosApiClient, backtestId: string, query: ListQuery = {}) {
    return client.get<Page<BacktestRow>>(
      `${API_PREFIX}/backtests/${backtestId}/equity`,
      { query },
    );
  },
};
