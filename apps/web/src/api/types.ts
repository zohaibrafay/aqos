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
  readonly symbol: string;
  readonly timeframe: string | null;
  readonly action: string;
  readonly status: string;
  readonly source: string;
  readonly confidence: number | null;
  readonly generated_at_utc: string | null;
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
