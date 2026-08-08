"use client";

import Link from "next/link";

import type { AqosApiError } from "@/api/errors";
import { API_ERROR_CODES } from "@/api/errors";
import type { BacktestRow, BacktestSummary } from "@/api/types";
import { MetricValue, ProfitFactorValue } from "@/components/accounts";
import { formatTimestamp } from "@/components/signals";
import { EmptyState } from "@/components/states";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Badge, Card, TableShell } from "@/components/ui";

/**
 * Backtest presentation.
 *
 * A backtest replays stored history. Nothing here implies a run reached a
 * venue, and a model named by a run is traceability, not an endorsement.
 */

/**
 * The difference between "not configured" and "nothing to show".
 *
 * The API reports an unconfigured or missing registry as unavailable, and an
 * empty list only when it really looked and found nothing. Collapsing the two
 * would tell somebody they have no backtests when in fact nobody told the
 * deployment where to look.
 */
export function NotReadyPanel({
  error,
  onRetry,
}: {
  readonly error: AqosApiError;
  readonly onRetry?: () => void;
}) {
  const notReady =
    error.code === API_ERROR_CODES.notReady ||
    error.code === API_ERROR_CODES.databaseUnavailable;

  if (!notReady) {
    return <ApiErrorPanel error={error} onRetry={onRetry} />;
  }

  return (
    <div
      role="alert"
      data-testid="not-ready"
      className="rounded border border-amber-800 bg-amber-950/40 p-4"
    >
      <Badge tone="warn">not ready</Badge>
      <p className="mt-2 text-sm text-slate-100">{error.message}</p>
      <p className="mt-1 text-xs text-muted">
        This is not the same as having no results. Nothing has been read, so
        nothing can be reported.
      </p>
      {error.requestId ? (
        <p className="mt-2 text-xs text-muted">
          Reference: <code data-testid="request-id">{error.requestId}</code>
        </p>
      ) : null}
    </div>
  );
}

export function BacktestStatusBadge({ kind }: { readonly kind: string }) {
  return <Badge tone="neutral">{kind}</Badge>;
}

function metric(row: BacktestSummary, key: string): number | null {
  const value = row.metrics[key];

  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function BacktestListTable({
  items,
}: {
  readonly items: readonly BacktestSummary[];
}) {
  return (
    <TableShell
      columns={["Run", "Kind", "Strategy", "Symbol", "Net profit", "Trades", "Created"]}
    >
      {items.map((run) => (
        <tr key={run.backtest_id} className="border-b border-edge/60">
          <td className="px-3 py-2">
            <Link
              href={`/backtests/${run.backtest_id}`}
              className="text-sky-400 hover:text-sky-300"
            >
              {run.backtest_id.slice(0, 22)}
            </Link>
          </td>
          <td className="px-3 py-2">
            <BacktestStatusBadge kind={run.kind} />
          </td>
          <td className="px-3 py-2">{run.strategy_name}</td>
          <td className="px-3 py-2">{run.symbol ?? "—"}</td>
          <td className="px-3 py-2">
            <MetricValue value={metric(run, "net_profit")} />
          </td>
          <td className="px-3 py-2">
            <MetricValue value={metric(run, "total_trades")} digits={0} />
          </td>
          <td className="px-3 py-2 text-muted">{formatTimestamp(run.created_at_utc)}</td>
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

export function BacktestDetailCard({ run }: { readonly run: BacktestSummary }) {
  return (
    <Card title="Backtest">
      <Row label="Run ID">{run.backtest_id}</Row>
      <Row label="Kind">
        <BacktestStatusBadge kind={run.kind} />
      </Row>
      <Row label="Strategy">{run.strategy_name}</Row>
      <Row label="Symbol">{run.symbol ?? "—"}</Row>
      <Row label="Timeframe">{run.timeframe ?? "—"}</Row>
      <Row label="Model">{run.model_id ?? "—"}</Row>
      <Row label="Model version">{run.model_version ?? "—"}</Row>
      <Row label="Created">{formatTimestamp(run.created_at_utc)}</Row>
      {run.model_id ? (
        <p className="mt-3 text-xs text-muted">
          A backtest result is not evidence that a model is fit for production.
        </p>
      ) : null}
    </Card>
  );
}

/**
 * The measured metrics, with the profit factor's state alongside it.
 *
 * The registry keeps only numeric metrics, so a null profit factor is dropped
 * from the map entirely. The state is what says whether that means "won every
 * trade" or "nothing to divide".
 */
export function BacktestMetricsPanel({
  run,
  profitFactorState,
}: {
  readonly run: BacktestSummary;
  readonly profitFactorState?: string | null;
}) {
  const keys = Object.keys(run.metrics).sort();

  if (keys.length === 0) {
    return <EmptyState title="No metrics recorded" />;
  }

  return (
    <div className="flex flex-col">
      {keys
        .filter((key) => key !== "profit_factor")
        .map((key) => (
          <Row key={key} label={key.replace(/_/g, " ")}>
            <MetricValue value={run.metrics[key] ?? null} />
          </Row>
        ))}
      <Row label="profit factor">
        <ProfitFactorValue
          value={run.metrics["profit_factor"] ?? null}
          state={profitFactorState ?? null}
        />
      </Row>
    </div>
  );
}

/**
 * A table over rows the runner wrote.
 *
 * Columns come from the data rather than from a fixed list: the report shape
 * belongs to the backtesting package, and mirroring it here would be a second
 * definition to keep in step.
 */
export function BacktestRowsTable({
  rows,
  empty,
}: {
  readonly rows: readonly BacktestRow[];
  readonly empty: string;
}) {
  if (rows.length === 0) {
    return <EmptyState title={empty} />;
  }

  const columns = Object.keys(rows[0] ?? {});

  return (
    <TableShell columns={columns}>
      {rows.map((row, index) => (
        <tr key={index} className="border-b border-edge/60">
          {columns.map((column) => {
            const value = row[column];

            return (
              <td key={column} className="px-3 py-2">
                {value === null || value === undefined ? (
                  <span className="text-muted">—</span>
                ) : typeof value === "number" ? (
                  <MetricValue value={value} />
                ) : (
                  <span className="text-slate-100">{String(value)}</span>
                )}
              </td>
            );
          })}
        </tr>
      ))}
    </TableShell>
  );
}

export function BacktestTradesTable({ rows }: { readonly rows: readonly BacktestRow[] }) {
  return <BacktestRowsTable rows={rows} empty="No trades in this run" />;
}

export function BacktestOrdersTable({ rows }: { readonly rows: readonly BacktestRow[] }) {
  return <BacktestRowsTable rows={rows} empty="No orders in this run" />;
}

export function BacktestEquityTable({ rows }: { readonly rows: readonly BacktestRow[] }) {
  return <BacktestRowsTable rows={rows} empty="No equity curve in this run" />;
}
