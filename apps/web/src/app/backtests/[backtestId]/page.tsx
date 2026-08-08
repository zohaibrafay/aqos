"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";

import { backtests } from "@/api/resources";
import {
  BacktestDetailCard,
  BacktestEquityTable,
  BacktestMetricsPanel,
  BacktestOrdersTable,
  BacktestTradesTable,
  NotReadyPanel,
} from "@/components/backtests";
import { LoadingState } from "@/components/states";
import { Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

/**
 * One historical run, with the rows it produced.
 *
 * A registered run whose report has gone missing is reported as not ready
 * rather than as an empty table, because an empty table would claim the run
 * produced nothing.
 */
export default function BacktestDetailPage() {
  const params = useParams<{ backtestId: string }>();
  const backtestId = params?.backtestId ?? "";
  const client = getApiClient;

  const run = useApiResource(
    useCallback(() => backtests.get(client(), backtestId), [backtestId, client]),
    [backtestId],
  );
  const trades = useApiResource(
    useCallback(() => backtests.trades(client(), backtestId), [backtestId, client]),
    [backtestId],
  );
  const orders = useApiResource(
    useCallback(() => backtests.orders(client(), backtestId), [backtestId, client]),
    [backtestId],
  );
  const equity = useApiResource(
    useCallback(() => backtests.equity(client(), backtestId), [backtestId, client]),
    [backtestId],
  );

  return (
    <>
      <PageHeader title="Backtest" description={backtestId} />

      <Link href="/backtests" className="mb-4 inline-block text-sm text-sky-400">
        Back to backtests
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          {run.loading ? <LoadingState label="Loading run…" /> : null}
          {!run.loading && run.error ? (
            <NotReadyPanel error={run.error} onRetry={run.reload} />
          ) : null}
          {!run.loading && !run.error && run.data ? (
            <>
              <BacktestDetailCard run={run.data} />
              <Card title="Metrics">
                <BacktestMetricsPanel run={run.data} />
              </Card>
            </>
          ) : null}
        </div>

        <div className="flex flex-col gap-6">
          <Card title="Trades">
            {trades.loading ? <LoadingState label="Loading trades…" /> : null}
            {!trades.loading && trades.error ? (
              <NotReadyPanel error={trades.error} onRetry={trades.reload} />
            ) : null}
            {!trades.loading && !trades.error && trades.data ? (
              <BacktestTradesTable rows={trades.data.items} />
            ) : null}
          </Card>

          <Card title="Orders">
            {orders.loading ? <LoadingState label="Loading orders…" /> : null}
            {!orders.loading && orders.error ? (
              <NotReadyPanel error={orders.error} onRetry={orders.reload} />
            ) : null}
            {!orders.loading && !orders.error && orders.data ? (
              <BacktestOrdersTable rows={orders.data.items} />
            ) : null}
          </Card>

          <Card title="Equity curve">
            {equity.loading ? <LoadingState label="Loading equity…" /> : null}
            {!equity.loading && equity.error ? (
              <NotReadyPanel error={equity.error} onRetry={equity.reload} />
            ) : null}
            {!equity.loading && !equity.error && equity.data ? (
              <BacktestEquityTable rows={equity.data.items} />
            ) : null}
          </Card>
        </div>
      </div>
    </>
  );
}
