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
  readonly user_id: string;
  readonly account_name: string;
  readonly account_type: string;
  readonly venue: string | null;
  readonly status: string;
  readonly currency: string | null;
  readonly execution_mode: string | null;
  readonly auto_trade_enabled: boolean;
  readonly is_default: boolean;
  readonly is_real_money: boolean;
  readonly created_at_utc: string | null;
}

export interface AccountDetail extends AccountSummary {
  readonly initial_balance: number | null;
  readonly current_balance: number | null;
  readonly equity: number | null;
  readonly leverage: number | null;
  readonly is_tradable: boolean;
  readonly updated_at_utc: string | null;
}

export interface ExecutionConstraint {
  readonly source: string;
  readonly allowed_mode: string;
  readonly reason: string | null;
}

export interface ExecutionConstraints {
  readonly account_id: string;
  readonly stored_execution_mode: string | null;
  readonly auto_trade_enabled: boolean;
  readonly requested_execution_mode: string | null;
  readonly effective_execution_mode: string | null;
  readonly was_downgraded: boolean;
  readonly allows_orders: boolean;
  readonly requires_manual_approval: boolean;
  readonly binding_sources: readonly string[];
  readonly explanation: string | null;
  readonly constraints: readonly ExecutionConstraint[];
}

export interface FundedRules {
  readonly rules_id: string;
  readonly account_id: string;
  readonly status: string;
  readonly is_blocking: boolean;
  readonly is_breached: boolean;
  readonly breached_at_utc: string | null;
  readonly breach_reason: string | null;
  readonly execution_ceiling: string | null;
  readonly max_daily_loss_fraction: number | null;
  readonly max_total_drawdown_fraction: number | null;
  readonly profit_target_fraction: number | null;
  readonly max_risk_per_trade_fraction: number | null;
  readonly drawdown_basis: string | null;
  readonly max_open_positions: number | null;
  readonly max_daily_trades: number | null;
  readonly min_trading_days: number | null;
  readonly weekend_holding_allowed: boolean | null;
  readonly news_restriction_enabled: boolean | null;
  readonly copied_from_template_id: string | null;
  readonly created_at_utc: string | null;
  readonly updated_at_utc: string | null;
}

/**
 * Why trade metrics are or are not measured.
 *
 * Present on the live analytics endpoint, which connects no trade source. It
 * exists so "unavailable" can never be read as a measured zero, and so a
 * client knows where the real numbers do live.
 */
export interface TradeMetricsSource {
  readonly connected: boolean;
  readonly reason_code: string;
  readonly reason: string;
  readonly measured_metrics_endpoint: string;
}

export interface SignalMetrics {
  readonly signals_received: number;
  readonly signals_executed: number;
  readonly signals_rejected: number;
  readonly signals_missed: number;
  readonly execution_rate: number | null;
  readonly rejection_rate: number | null;
}

export interface TradeMetrics {
  readonly is_available: boolean;
  readonly unavailable_reason: string | null;
  readonly total_trades: number | null;
  readonly win_rate: number | null;
  readonly net_pnl: number | null;
  readonly profit_factor: number | null;
  readonly profit_factor_state: string | null;
  readonly max_drawdown: number | null;
}

export interface AccountAnalytics {
  readonly scope: string;
  readonly account_id: string | null;
  readonly calculated_at_utc: string | null;
  readonly has_trade_metrics: boolean;
  readonly signal_metrics: SignalMetrics;
  readonly trade_metrics: TradeMetrics;
  readonly trade_metrics_source?: TradeMetricsSource;
}

export interface AnalyticsSnapshot {
  readonly snapshot_id: string;
  readonly account_id: string;
  readonly scope: string;
  readonly period_start_utc: string | null;
  readonly period_end_utc: string | null;
  readonly calculated_at_utc: string | null;
  readonly signals_received: number | null;
  readonly signals_executed: number | null;
  readonly trade_metrics_available: boolean;
  readonly total_trades: number | null;
  readonly win_rate: number | null;
  readonly net_pnl: number | null;
  readonly profit_factor: number | null;
  readonly profit_factor_state: string | null;
  readonly has_infinite_profit_factor: boolean;
  readonly max_drawdown: number | null;
}

export interface ReportSummary {
  readonly report_id: string;
  readonly account_id: string;
  readonly account_type: string | null;
  readonly report_type: string;
  readonly analytics_snapshot_id: string | null;
  readonly period_start_utc: string | null;
  readonly period_end_utc: string | null;
  readonly generated_at_utc: string | null;
  readonly trade_metrics_available: boolean;
  readonly artifact_format: string | null;
  readonly has_artifact: boolean;
}

export interface ReportDetail extends ReportSummary {
  readonly payload: Record<string, unknown>;
}

export interface PaperSessionSummary {
  readonly session_id: string;
  readonly user_id: string;
  readonly account_id: string;
  readonly session_name: string;
  readonly session_type: string;
  readonly status: string;
  readonly is_terminal: boolean;
  readonly started_at_utc: string | null;
  readonly ended_at_utc: string | null;
  readonly total_trades: number | null;
  readonly net_pnl: number | null;
  readonly profit_factor: number | null;
  readonly profit_factor_state: string | null;
}

export interface PaperSessionDetail extends PaperSessionSummary {
  readonly status_reason: string | null;
  readonly strategy_name: string | null;
  readonly model_id: string | null;
  readonly model_version: string | null;
  readonly symbol: string | null;
  readonly timeframe: string | null;
  readonly initial_balance: number | null;
  readonly final_balance: number | null;
  readonly realized_pnl: number | null;
  readonly max_drawdown: number | null;
}

export interface PaperRejectionCount {
  readonly reason_code: string;
  readonly total: number;
}

/**
 * What one simulated run measured.
 *
 * `profit_factor_state` travels beside the number because infinity has no JSON
 * form: without it a wins-and-no-losses run is indistinguishable from one that
 * measured nothing at all.
 */
export interface PaperSessionResult {
  readonly session_id: string;
  readonly account_id: string;
  readonly has_trades: boolean;
  readonly total_orders: number;
  readonly total_fills: number;
  readonly total_trades: number;
  readonly winning_trades: number;
  readonly losing_trades: number;
  readonly win_rate: number | null;
  readonly net_pnl: number | null;
  readonly gross_profit: number | null;
  readonly gross_loss: number | null;
  readonly profit_factor: number | null;
  readonly profit_factor_state: string | null;
  readonly has_infinite_profit_factor: boolean;
  readonly max_drawdown: number | null;
  readonly ending_balance: number | null;
  readonly symbols_traded: readonly string[];
  readonly decisions_allowed: number;
  readonly decisions_rejected: number;
  readonly total_decisions: number;
  readonly rejection_rate: number | null;
  readonly top_rejection_reasons: readonly PaperRejectionCount[];
  readonly calculated_at_utc: string | null;
}

export interface PaperOrder {
  readonly order_id: string;
  readonly session_id: string | null;
  readonly signal_id: string | null;
  readonly symbol: string;
  readonly action: string;
  readonly order_type: string;
  readonly status: string;
  readonly quantity: number | null;
  readonly filled_quantity: number | null;
  readonly average_fill_price: number | null;
  readonly requested_price: number | null;
  readonly stop_loss: number | null;
  readonly take_profit: number | null;
  readonly rejection_reason: string | null;
  readonly rejection_message: string | null;
  readonly created_at_utc: string | null;
}

export interface PaperFill {
  readonly fill_id: string;
  readonly order_id: string;
  readonly position_id: string | null;
  readonly quantity: number | null;
  readonly price: number | null;
  readonly commission: number | null;
  readonly filled_at_utc: string | null;
}

export interface PaperPosition {
  readonly position_id: string;
  readonly order_id: string | null;
  readonly signal_id: string | null;
  readonly symbol: string;
  readonly side: string;
  readonly status: string;
  readonly quantity: number | null;
  readonly closed_quantity: number | null;
  readonly entry_price: number | null;
  readonly stop_loss: number | null;
  readonly take_profit: number | null;
  readonly realized_pnl: number | null;
  readonly opened_at_utc: string | null;
  readonly closed_at_utc: string | null;
}

export interface PaperTrade {
  readonly trade_id: string;
  readonly position_id: string | null;
  readonly signal_id: string | null;
  readonly symbol: string;
  readonly side: string;
  readonly quantity: number | null;
  readonly entry_price: number | null;
  readonly exit_price: number | null;
  readonly gross_pnl: number | null;
  readonly commission: number | null;
  readonly net_pnl: number | null;
  readonly exit_reason: string | null;
  readonly balance_after: number | null;
  readonly opened_at_utc: string | null;
  readonly closed_at_utc: string | null;
}

export interface PaperDecisionReason {
  readonly code: string | null;
  readonly source: string | null;
  readonly category: string | null;
  readonly severity: string | null;
  readonly message: string | null;
  readonly is_blocking: boolean | null;
}

export interface PaperDecision {
  readonly decision_id: string;
  readonly session_id: string | null;
  readonly signal_id: string | null;
  readonly order_id: string | null;
  readonly symbol: string;
  readonly is_allowed: boolean;
  readonly requested_execution_mode: string | null;
  readonly effective_execution_mode: string | null;
  readonly primary_reason_code: string | null;
  readonly blocking_reason_count: number;
  readonly blocking_sources: readonly string[];
  readonly reasons: readonly PaperDecisionReason[];
  readonly decided_at_utc: string | null;
}

export interface BacktestSummary {
  readonly backtest_id: string;
  readonly created_at_utc: string | null;
  readonly kind: string;
  readonly strategy_name: string;
  readonly symbol: string | null;
  readonly timeframe: string | null;
  readonly model_id: string | null;
  readonly model_version: string | null;
  readonly metrics: Record<string, number>;
  readonly tags: readonly string[];
}

/**
 * One row from a stored backtest report.
 *
 * Deliberately open: the runner writes trade, order and equity rows in its own
 * shape, and re-declaring them here would be a second definition to keep in
 * step. The table renders whatever columns arrive.
 */
export type BacktestRow = Record<string, unknown>;
