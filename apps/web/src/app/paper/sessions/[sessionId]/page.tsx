"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";

import { paper } from "@/api/resources";
import {
  PaperDecisionsTable,
  PaperFillsTable,
  PaperOrdersTable,
  PaperPositionsTable,
  PaperResultSummary,
  PaperSessionDetailCard,
  PaperTradesTable,
  SimulatedNotice,
} from "@/components/paper";
import {
  PaperOrderSubmitForm,
  PaperSessionActionsPanel,
} from "@/components/paper/actions";
import { LoadingState } from "@/components/states";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

/**
 * One simulated run, in full.
 *
 * Each panel fetches and fails on its own, so an unavailable result does not
 * hide the orders and a missing decision log does not blank the trades.
 *
 * The controls below act on the simulator only. Nothing on screen moves until
 * a refetch returns the server's own view of what happened.
 */
export default function PaperSessionDetailPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params?.sessionId ?? "";
  const client = getApiClient;

  const session = useApiResource(
    useCallback(() => paper.getSession(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const result = useApiResource(
    useCallback(() => paper.result(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const orders = useApiResource(
    useCallback(() => paper.orders(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const fills = useApiResource(
    useCallback(() => paper.fills(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const positions = useApiResource(
    useCallback(() => paper.positions(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const trades = useApiResource(
    useCallback(() => paper.trades(client(), sessionId), [sessionId, client]),
    [sessionId],
  );
  const decisions = useApiResource(
    useCallback(() => paper.decisions(client(), sessionId), [sessionId, client]),
    [sessionId],
  );

  /** Everything a simulated action can change, refetched together. */
  const refreshAll = () => {
    session.reload();
    result.reload();
    orders.reload();
    fills.reload();
    positions.reload();
    trades.reload();
    decisions.reload();
  };

  return (
    <>
      <PageHeader title="Paper session" description={sessionId} />
      <SimulatedNotice />

      <Link href="/paper" className="mb-4 inline-block text-sm text-sky-400">
        Back to paper sessions
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          {session.loading ? <LoadingState label="Loading session…" /> : null}
          {!session.loading && session.error ? (
            <ApiErrorPanel error={session.error} onRetry={session.reload} />
          ) : null}
          {!session.loading && !session.error && session.data ? (
            <>
              <PaperSessionDetailCard session={session.data} />
              <PaperSessionActionsPanel
                session={session.data}
                onCompleted={refreshAll}
              />
              {session.data.status === "running" ? (
                <PaperOrderSubmitForm
                  sessionId={sessionId}
                  onCompleted={refreshAll}
                />
              ) : null}
            </>
          ) : null}

          <Card title="Result">
            {result.loading ? <LoadingState label="Loading result…" /> : null}
            {!result.loading && result.error ? (
              <ApiErrorPanel error={result.error} onRetry={result.reload} />
            ) : null}
            {!result.loading && !result.error && result.data ? (
              <PaperResultSummary result={result.data} />
            ) : null}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card title="Orders">
            {orders.loading ? <LoadingState label="Loading orders…" /> : null}
            {!orders.loading && orders.error ? (
              <ApiErrorPanel error={orders.error} onRetry={orders.reload} />
            ) : null}
            {!orders.loading && !orders.error && orders.data ? (
              <PaperOrdersTable items={orders.data.items} />
            ) : null}
          </Card>

          <Card title="Fills">
            {fills.loading ? <LoadingState label="Loading fills…" /> : null}
            {!fills.loading && fills.error ? (
              <ApiErrorPanel error={fills.error} onRetry={fills.reload} />
            ) : null}
            {!fills.loading && !fills.error && fills.data ? (
              <PaperFillsTable items={fills.data.items} />
            ) : null}
          </Card>

          <Card title="Positions">
            {positions.loading ? <LoadingState label="Loading positions…" /> : null}
            {!positions.loading && positions.error ? (
              <ApiErrorPanel error={positions.error} onRetry={positions.reload} />
            ) : null}
            {!positions.loading && !positions.error && positions.data ? (
              <PaperPositionsTable items={positions.data.items} />
            ) : null}
          </Card>

          <Card title="Trades">
            {trades.loading ? <LoadingState label="Loading trades…" /> : null}
            {!trades.loading && trades.error ? (
              <ApiErrorPanel error={trades.error} onRetry={trades.reload} />
            ) : null}
            {!trades.loading && !trades.error && trades.data ? (
              <PaperTradesTable items={trades.data.items} />
            ) : null}
          </Card>

          <Card title="Execution decisions">
            {decisions.loading ? <LoadingState label="Loading decisions…" /> : null}
            {!decisions.loading && decisions.error ? (
              <ApiErrorPanel error={decisions.error} onRetry={decisions.reload} />
            ) : null}
            {!decisions.loading && !decisions.error && decisions.data ? (
              <PaperDecisionsTable items={decisions.data.items} />
            ) : null}
          </Card>
        </div>
      </div>
    </>
  );
}
