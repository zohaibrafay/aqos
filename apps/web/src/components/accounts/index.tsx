"use client";

import Link from "next/link";

import type {
  AccountAnalytics,
  AccountDetail,
  AccountSummary,
  AnalyticsSnapshot,
  ExecutionConstraints,
  FundedRules,
  ReportDetail,
  ReportSummary,
} from "@/api/types";
import { EmptyState } from "@/components/states";
import { Badge, Card, TableShell } from "@/components/ui";
import type { BadgeTone } from "@/components/ui";
import { formatTimestamp } from "@/components/signals";

/**
 * Account presentation.
 *
 * Read-only throughout. There is no control here to change an execution mode,
 * toggle auto-trade, edit a funded rule or alter an account in any way — those
 * would be decisions, and this screen only reports them.
 *
 * The formatting helpers below all keep absent apart from zero. A blank metric
 * and a measured nought mean different things, and rendering both as `0` is
 * how a report starts lying.
 */

/** A number, or an explicit dash. Never a zero standing in for nothing. */
export function MetricValue({
  value,
  suffix = "",
  digits = 2,
}: {
  readonly value: number | null | undefined;
  readonly suffix?: string;
  readonly digits?: number;
}) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return <span className="text-muted">—</span>;
  }

  return (
    <span className="text-slate-100">
      {value.toFixed(digits)}
      {suffix}
    </span>
  );
}

export function formatPercent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${(value * 100).toFixed(1)}%`
    : "—";
}

export function formatMoney(
  value: number | null | undefined,
  currency: string | null | undefined,
): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return `${value.toFixed(2)}${currency ? ` ${currency}` : ""}`;
}

const STATUS_TONES: Record<string, BadgeTone> = {
  active: "good",
  suspended: "warn",
  disabled: "bad",
  closed: "neutral",
};

export function AccountStatusBadge({ status }: { readonly status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{status}</Badge>;
}

/**
 * Whether this account can move real money.
 *
 * Paper is marked plainly and everything else is marked as carrying real
 * capital, because that is the distinction a reader most needs at a glance.
 */
export function AccountTypeBadge({ type }: { readonly type: string }) {
  return <Badge tone={type === "paper" ? "neutral" : "warn"}>{type}</Badge>;
}

export function VenueBadge({ venue }: { readonly venue: string | null }) {
  return <Badge tone="neutral">{venue ?? "—"}</Badge>;
}

const MODE_TONES: Record<string, BadgeTone> = {
  auto_trade: "warn",
  manual_approval: "neutral",
  signal_only: "neutral",
  disabled: "bad",
};

export function ExecutionModeBadge({ mode }: { readonly mode: string | null }) {
  if (!mode) {
    return <span className="text-muted">—</span>;
  }

  return <Badge tone={MODE_TONES[mode] ?? "neutral"}>{mode}</Badge>;
}

export function AccountListTable({
  items,
}: {
  readonly items: readonly AccountSummary[];
}) {
  return (
    <TableShell
      columns={["Account", "Type", "Venue", "Status", "Mode", "Auto-trade", "Currency"]}
    >
      {items.map((account) => (
        <tr key={account.account_id} className="border-b border-edge/60">
          <td className="px-3 py-2">
            <Link
              href={`/accounts/${account.account_id}`}
              className="text-sky-400 hover:text-sky-300"
            >
              {account.account_name}
            </Link>
          </td>
          <td className="px-3 py-2">
            <AccountTypeBadge type={account.account_type} />
          </td>
          <td className="px-3 py-2">
            <VenueBadge venue={account.venue} />
          </td>
          <td className="px-3 py-2">
            <AccountStatusBadge status={account.status} />
          </td>
          <td className="px-3 py-2">
            <ExecutionModeBadge mode={account.execution_mode} />
          </td>
          <td className="px-3 py-2">
            {account.auto_trade_enabled ? (
              <Badge tone="warn">enabled</Badge>
            ) : (
              <Badge tone="neutral">off</Badge>
            )}
          </td>
          <td className="px-3 py-2 text-muted">{account.currency ?? "—"}</td>
        </tr>
      ))}
    </TableShell>
  );
}

function Row({
  label,
  children,
}: {
  readonly label: string;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between gap-4 border-b border-edge/40 py-1.5 text-sm">
      <span className="text-muted">{label}</span>
      <span className="text-slate-100">{children}</span>
    </div>
  );
}

/**
 * One account's safe fields.
 *
 * No broker credential reference, no connection reference, no token and no raw
 * metadata: the API withholds all of them, and nothing here goes looking.
 */
export function AccountDetailCard({ account }: { readonly account: AccountDetail }) {
  return (
    <Card title="Account">
      <Row label="Name">{account.account_name}</Row>
      <Row label="Account ID">{account.account_id}</Row>
      <Row label="Type">
        <AccountTypeBadge type={account.account_type} />
      </Row>
      <Row label="Venue">
        <VenueBadge venue={account.venue} />
      </Row>
      <Row label="Status">
        <AccountStatusBadge status={account.status} />
      </Row>
      <Row label="Execution mode">
        <ExecutionModeBadge mode={account.execution_mode} />
      </Row>
      <Row label="Auto-trade">{account.auto_trade_enabled ? "enabled" : "off"}</Row>
      <Row label="Real money">{account.is_real_money ? "yes" : "no"}</Row>
      <Row label="Currency">{account.currency ?? "—"}</Row>
      <Row label="Initial balance">
        {formatMoney(account.initial_balance, account.currency)}
      </Row>
      <Row label="Current balance">
        {formatMoney(account.current_balance, account.currency)}
      </Row>
      <Row label="Equity">{formatMoney(account.equity, account.currency)}</Row>
      <Row label="Leverage">
        <MetricValue value={account.leverage} digits={0} />
      </Row>
      <Row label="Created">{formatTimestamp(account.created_at_utc)}</Row>
      <Row label="Updated">{formatTimestamp(account.updated_at_utc)}</Row>
    </Card>
  );
}

/**
 * What this account is actually allowed to do, and why.
 *
 * Read-only: the effective mode is the strictest combination of every
 * constraint, and raising it is a decision taken elsewhere, never a GET.
 */
export function ExecutionConstraintsPanel({
  constraints,
}: {
  readonly constraints: ExecutionConstraints;
}) {
  return (
    <div className="flex flex-col gap-3">
      <Row label="Stored mode">
        <ExecutionModeBadge mode={constraints.stored_execution_mode} />
      </Row>
      <Row label="Effective mode">
        <ExecutionModeBadge mode={constraints.effective_execution_mode} />
      </Row>
      <Row label="Downgraded">{constraints.was_downgraded ? "yes" : "no"}</Row>
      <Row label="Allows orders">{constraints.allows_orders ? "yes" : "no"}</Row>
      <Row label="Manual approval">
        {constraints.requires_manual_approval ? "required" : "not required"}
      </Row>

      {constraints.explanation ? (
        <p className="text-sm text-slate-200">{constraints.explanation}</p>
      ) : null}

      {constraints.binding_sources.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Binding:</span>
          {constraints.binding_sources.map((source) => (
            <Badge key={source} tone="warn">
              {source}
            </Badge>
          ))}
        </div>
      ) : null}

      {constraints.constraints.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {constraints.constraints.map((item) => (
            <li key={`${item.source}-${item.allowed_mode}`} className="text-sm">
              <span className="text-muted">{item.source}</span>{" "}
              <ExecutionModeBadge mode={item.allowed_mode} />
              {item.reason ? (
                <span className="ml-2 text-muted">{item.reason}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * The funded-account rules, if this account has any.
 *
 * No firm is named anywhere: the rules are whatever the account was given, and
 * the provenance is a template id rather than a brand.
 */
export function FundedRulesPanel({ rules }: { readonly rules: FundedRules | null }) {
  if (!rules) {
    return (
      <EmptyState
        title="No funded rules"
        description="This account is not governed by a funded programme."
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={rules.is_breached ? "bad" : "good"}>{rules.status}</Badge>
        {rules.is_blocking ? <Badge tone="bad">blocking</Badge> : null}
        {rules.execution_ceiling ? (
          <ExecutionModeBadge mode={rules.execution_ceiling} />
        ) : null}
      </div>

      {rules.is_breached ? (
        <p className="text-sm text-rose-300">
          Breached {formatTimestamp(rules.breached_at_utc)}
          {rules.breach_reason ? ` · ${rules.breach_reason}` : ""}
        </p>
      ) : null}

      <Row label="Max daily loss">{formatPercent(rules.max_daily_loss_fraction)}</Row>
      <Row label="Max total drawdown">
        {formatPercent(rules.max_total_drawdown_fraction)}
      </Row>
      <Row label="Profit target">{formatPercent(rules.profit_target_fraction)}</Row>
      <Row label="Max risk per trade">
        {formatPercent(rules.max_risk_per_trade_fraction)}
      </Row>
      <Row label="Drawdown basis">{rules.drawdown_basis ?? "—"}</Row>
      <Row label="Max open positions">
        <MetricValue value={rules.max_open_positions} digits={0} />
      </Row>
      <Row label="Max daily trades">
        <MetricValue value={rules.max_daily_trades} digits={0} />
      </Row>
      <Row label="Min trading days">
        <MetricValue value={rules.min_trading_days} digits={0} />
      </Row>
      <Row label="From template">{rules.copied_from_template_id ?? "—"}</Row>
    </div>
  );
}

/**
 * Live analytics.
 *
 * Signal metrics are measured. Trade metrics report as unavailable here
 * because this endpoint connects no trade source, and that is stated rather
 * than shown as zeros — a nought would claim the account traded and lost
 * nothing, which is a different and false statement.
 */
export function AnalyticsSummaryPanel({
  analytics,
}: {
  readonly analytics: AccountAnalytics;
}) {
  const signals = analytics.signal_metrics;
  const trades = analytics.trade_metrics;
  const source = analytics.trade_metrics_source;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="mb-2 text-xs uppercase text-muted">Signals</h3>
        <Row label="Received">
          <MetricValue value={signals.signals_received} digits={0} />
        </Row>
        <Row label="Executed">
          <MetricValue value={signals.signals_executed} digits={0} />
        </Row>
        <Row label="Rejected">
          <MetricValue value={signals.signals_rejected} digits={0} />
        </Row>
        <Row label="Missed">
          <MetricValue value={signals.signals_missed} digits={0} />
        </Row>
        <Row label="Execution rate">{formatPercent(signals.execution_rate)}</Row>
        <Row label="Rejection rate">{formatPercent(signals.rejection_rate)}</Row>
      </div>

      <div>
        <h3 className="mb-2 text-xs uppercase text-muted">Trades</h3>
        <Row label="Measured">
          <Badge tone={analytics.has_trade_metrics ? "good" : "warn"}>
            {analytics.has_trade_metrics ? "available" : "unavailable"}
          </Badge>
        </Row>

        {analytics.has_trade_metrics ? (
          <>
            <Row label="Total trades">
              <MetricValue value={trades.total_trades} digits={0} />
            </Row>
            <Row label="Win rate">{formatPercent(trades.win_rate)}</Row>
            <Row label="Net P&L">
              <MetricValue value={trades.net_pnl} />
            </Row>
            <Row label="Profit factor">
              <ProfitFactorValue
                value={trades.profit_factor}
                state={trades.profit_factor_state}
              />
            </Row>
          </>
        ) : (
          <div data-testid="trade-metrics-unavailable" className="mt-2">
            <p className="text-sm text-slate-200">
              {trades.unavailable_reason ??
                "Trade metrics are not measured by this endpoint."}
            </p>
            {source && !source.connected ? (
              <p className="mt-2 text-sm text-muted">
                {source.reason} Measured trade metrics are stored under this
                account&apos;s analytics snapshots.
              </p>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * A profit factor, with the state that tells you which kind of blank it is.
 *
 * Infinity has no JSON form, so a wins-and-no-losses run arrives as `null`
 * exactly like a run that measured nothing. Only the state separates them, and
 * neither may ever render as zero.
 */
export function ProfitFactorValue({
  value,
  state,
}: {
  readonly value: number | null | undefined;
  readonly state: string | null | undefined;
}) {
  if (state === "infinite_no_losses") {
    return (
      <span className="text-emerald-300" data-testid="profit-factor">
        no losing trades
      </span>
    );
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return (
      <span className="text-slate-100" data-testid="profit-factor">
        {value.toFixed(2)}
      </span>
    );
  }

  return (
    <span className="text-muted" data-testid="profit-factor">
      unavailable
    </span>
  );
}

export function AnalyticsSnapshotsTable({
  items,
}: {
  readonly items: readonly AnalyticsSnapshot[];
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No stored snapshots"
        description="Nothing has been calculated and saved for this account yet."
      />
    );
  }

  return (
    <TableShell
      columns={[
        "Calculated",
        "Trades",
        "Net P&L",
        "Win rate",
        "Profit factor",
        "Max drawdown",
        "Measured",
      ]}
    >
      {items.map((snapshot) => (
        <tr key={snapshot.snapshot_id} className="border-b border-edge/60">
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(snapshot.calculated_at_utc)}
          </td>
          <td className="px-3 py-2">
            <MetricValue value={snapshot.total_trades} digits={0} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={snapshot.net_pnl} />
          </td>
          <td className="px-3 py-2">{formatPercent(snapshot.win_rate)}</td>
          <td className="px-3 py-2">
            <ProfitFactorValue
              value={snapshot.profit_factor}
              state={snapshot.profit_factor_state}
            />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={snapshot.max_drawdown} />
          </td>
          <td className="px-3 py-2">
            <Badge tone={snapshot.trade_metrics_available ? "good" : "warn"}>
              {snapshot.trade_metrics_available ? "yes" : "no"}
            </Badge>
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

export function ReportsTable({
  items,
  onSelect,
  selectedId,
}: {
  readonly items: readonly ReportSummary[];
  readonly onSelect: (reportId: string) => void;
  readonly selectedId: string | null;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="No reports"
        description="Nothing has been generated for this account yet."
      />
    );
  }

  return (
    <TableShell columns={["Type", "Period", "Generated", "Measured", "Artifact"]}>
      {items.map((report) => (
        <tr
          key={report.report_id}
          className={
            report.report_id === selectedId
              ? "border-b border-edge/60 bg-edge/30"
              : "border-b border-edge/60"
          }
        >
          <td className="px-3 py-2">
            <button
              type="button"
              className="text-sky-400 hover:text-sky-300"
              onClick={() => onSelect(report.report_id)}
            >
              {report.report_type}
            </button>
          </td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(report.period_start_utc)} →{" "}
            {formatTimestamp(report.period_end_utc)}
          </td>
          <td className="px-3 py-2 text-muted">
            {formatTimestamp(report.generated_at_utc)}
          </td>
          <td className="px-3 py-2">
            <Badge tone={report.trade_metrics_available ? "good" : "warn"}>
              {report.trade_metrics_available ? "yes" : "no"}
            </Badge>
          </td>
          <td className="px-3 py-2">
            {/* Whether an artifact exists, never where it lives. */}
            <Badge tone={report.has_artifact ? "neutral" : "warn"}>
              {report.has_artifact ? (report.artifact_format ?? "stored") : "none"}
            </Badge>
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

/**
 * One report and the payload the server already made JSON-safe.
 *
 * The payload is rendered as formatted JSON rather than interpreted: the API
 * decided what belongs in it, and re-deciding here would be a second opinion
 * nobody asked for. No path and no checksum appears, because none is returned.
 */
export function ReportDetailPanel({ report }: { readonly report: ReportDetail }) {
  return (
    <div className="flex flex-col gap-2">
      <Row label="Report ID">{report.report_id}</Row>
      <Row label="Type">{report.report_type}</Row>
      <Row label="Period">
        {formatTimestamp(report.period_start_utc)} →{" "}
        {formatTimestamp(report.period_end_utc)}
      </Row>
      <Row label="Generated">{formatTimestamp(report.generated_at_utc)}</Row>
      <Row label="Trade metrics">
        {report.trade_metrics_available ? "measured" : "unavailable"}
      </Row>
      <pre
        data-testid="report-payload"
        className="mt-2 max-h-80 overflow-auto rounded border border-edge bg-surface p-3 text-xs text-slate-200"
      >
        {JSON.stringify(report.payload, null, 2)}
      </pre>
    </div>
  );
}
