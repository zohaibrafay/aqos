/**
 * Client-side checks for the paper and backtest action forms.
 *
 * The server validates all of this again — these rules exist so a caller is
 * told what is wrong without a round trip, never so a check can be skipped.
 * Each one mirrors a rule the backend already enforces rather than inventing a
 * policy of its own.
 */

/** A bar the simulator would accept. */
export interface MarketBarValues {
  readonly open: string;
  readonly high: string;
  readonly low: string;
  readonly close: string;
  readonly volume: string;
  readonly timestamp_utc: string;
}

export const EMPTY_MARKET_BAR: MarketBarValues = {
  open: "",
  high: "",
  low: "",
  close: "",
  volume: "",
  timestamp_utc: "",
};

/** Datasets are named, never located. Mirrors the backend pattern exactly. */
export const DATASET_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

/** The strategies the backend supports. Not a free-text field. */
export const SUPPORTED_STRATEGIES = ["csv_signal_strategy"] as const;

/** The widest window one run may cover, matching the backend bound. */
export const MAX_BACKTEST_DAYS = 3660;

export function parseNumber(value: string): number | null {
  const trimmed = value.trim();

  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);

  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * Check a bar the way the simulator will.
 *
 * A high that does not cover the close, or a low above the open, is not a
 * market that ever existed — and a caller who could submit one could
 * manufacture a favourable fill.
 */
export function validateMarketBar(values: MarketBarValues): string | null {
  const open = parseNumber(values.open);
  const high = parseNumber(values.high);
  const low = parseNumber(values.low);
  const close = parseNumber(values.close);

  if (open === null || high === null || low === null || close === null) {
    return "Enter the open, high, low and close.";
  }

  for (const [name, value] of [
    ["open", open],
    ["high", high],
    ["low", low],
    ["close", close],
  ] as const) {
    if (value <= 0) {
      return `The ${name} must be greater than zero.`;
    }
  }

  if (high < Math.max(open, close) || high < low) {
    return "The high must cover the open, the close and the low.";
  }

  if (low > Math.min(open, close) || low > high) {
    return "The low must sit at or below the open, the close and the high.";
  }

  const volume = parseNumber(values.volume);

  if (volume !== null && volume < 0) {
    return "The volume cannot be negative.";
  }

  if (!values.timestamp_utc.trim()) {
    return "Enter the bar timestamp.";
  }

  return null;
}

/** A dataset name, or the reason it is not one. */
export function validateDatasetName(value: string): string | null {
  const name = value.trim();

  if (!name) {
    return "Choose a dataset.";
  }

  if (!DATASET_NAME_PATTERN.test(name)) {
    // Anything with a separator, a dot or a scheme is a location, not a name.
    return "A dataset is named, not located. Use the configured dataset name.";
  }

  return null;
}

/** A window that runs backwards, or forever, is refused. */
export function validatePeriod(start: string, end: string): string | null {
  if (!start.trim() || !end.trim()) {
    return null;
  }

  const from = new Date(start);
  const to = new Date(end);

  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return "Enter both dates as ISO timestamps.";
  }

  if (to < from) {
    return "The end of the period cannot come before its start.";
  }

  const days = (to.getTime() - from.getTime()) / 86_400_000;

  if (days > MAX_BACKTEST_DAYS) {
    return `A backtest may cover at most ${MAX_BACKTEST_DAYS} days.`;
  }

  return null;
}
