/**
 * Wire shapes the AQOS API returns.
 *
 * Hand-written rather than generated: a generator would be another dependency
 * to keep honest, and these are the few shapes the foundation actually reads.
 * Fields the backend deliberately withholds — artifact paths, broker
 * references, free-form metadata — are absent here too.
 */

export interface Page<T> {
  readonly items: readonly T[];
  readonly count: number;
  readonly total: number | null;
  readonly limit: number;
  readonly offset: number;
}

export interface SessionUser {
  readonly user_id: string;
  readonly email: string;
  readonly display_name: string;
  readonly role: string;
  readonly status: string;
}

export interface AuthSession {
  readonly session_id: string;
  readonly created_at_utc: string | null;
  readonly expires_at_utc: string | null;
  readonly last_seen_at_utc: string | null;
  readonly client_label: string | null;
}

export interface LoginResult {
  readonly token: string;
  readonly expires_at_utc: string | null;
  readonly user: SessionUser;
  readonly session: AuthSession;
}

export interface SystemInfo {
  readonly api: Record<string, unknown>;
  readonly request_id: string | null;
}

export interface SignalSummary {
  readonly signal_id: string;
  readonly user_id: string;
  readonly account_id: string | null;
  readonly symbol: string;
  readonly timeframe: string | null;
  readonly action: string;
  readonly source: string;
  readonly status: string;
  readonly confidence: number | null;
  readonly generated_at_utc: string | null;
  readonly expires_at_utc: string | null;
}

export interface SignalDetail extends SignalSummary {
  readonly entry_price: number | null;
  readonly stop_loss: number | null;
  readonly take_profit: number | null;
  readonly strategy_name: string | null;
  readonly model_id: string | null;
  readonly model_version: string | null;
  readonly status_reason: string | null;
  readonly is_open: boolean;
  readonly created_at_utc: string | null;
  readonly updated_at_utc: string | null;
}

export interface SignalEvent {
  readonly event_id: string;
  readonly signal_id: string;
  readonly from_status: string | null;
  readonly to_status: string;
  readonly occurred_at_utc: string | null;
  readonly reason: string | null;
  readonly actor: string | null;
}

/** One structured reason from the Sprint 045 taxonomy. */
export interface SignalReason {
  readonly reason_id: string;
  readonly signal_id: string;
  readonly signal_status: string;
  readonly reason_code: string;
  readonly reason_category: string;
  readonly severity: string;
  readonly message: string;
  readonly source: string | null;
  readonly created_at_utc: string | null;
}

export interface PredictionSummary {
  readonly prediction_id: string;
  readonly created_at_utc: string | null;
  readonly model_name: string | null;
  readonly model_id: string | null;
  readonly model_version: string | null;
  readonly rows: number | null;
  readonly prediction_column: string | null;
  readonly probability_columns: readonly string[] | null;
  readonly input_features_rows: number | null;
  readonly input_features_columns_count: number | null;
}

export interface PromotionSummary {
  readonly promotion_id: string;
  readonly created_at_utc: string | null;
  readonly model_name: string | null;
  readonly model_id: string | null;
  readonly model_version: string | null;
  readonly target_stage: string | null;
  readonly status: string | null;
  readonly approved: boolean | null;
}

/**
 * Whether a model may be used, as far as the API can tell.
 *
 * `unknown` is a real answer, not a failure: no registry configured, or no
 * entry for this model. It must never be rendered as "not promoted", which is
 * a finding, nor as "promoted", which would be a claim nobody made.
 */
export type PromotionStateName = "promoted" | "not_promoted" | "unknown";

export interface PromotionStatus {
  readonly model_id: string;
  readonly state: PromotionStateName;
  readonly is_promoted: boolean;
  readonly reason: string | null;
  readonly latest_promotion: PromotionSummary | null;
  readonly promotion_count: number;
}

export interface AccountSummary {
  readonly account_id: string;
  readonly name: string;
  readonly account_type: string;
  readonly status: string;
  readonly currency: string | null;
  readonly current_balance: number | null;
  readonly equity: number | null;
}

export interface PaperSessionSummary {
  readonly session_id: string;
  readonly account_id: string;
  readonly session_name: string;
  readonly session_type: string;
  readonly status: string;
  readonly started_at_utc: string | null;
  readonly ended_at_utc: string | null;
}

export interface BacktestSummary {
  readonly backtest_id: string;
  readonly strategy_name: string;
  readonly symbol: string | null;
  readonly timeframe: string | null;
  readonly created_at_utc: string | null;
  readonly metrics: Record<string, number>;
}
