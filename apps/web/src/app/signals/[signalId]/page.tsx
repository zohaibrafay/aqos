"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback } from "react";

import { models, signals } from "@/api/resources";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Alert, LoadingState } from "@/components/states";
import { Card, PageHeader } from "@/components/ui";
import {
  PromotionStatusBadge,
  SignalDetailCard,
  SignalEventsTimeline,
  SignalReasonsPanel,
} from "@/components/signals";
import { SignalActionPanel } from "@/components/signals/SignalActionPanel";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

/**
 * One signal, its audit trail and its structured reasons.
 *
 * Lifecycle actions record a decision about the signal and nothing more. A
 * successful one refetches all three panels, so what is on screen is always
 * the server's own view rather than an assumption about what it did.
 */
export default function SignalDetailPage() {
  const params = useParams<{ signalId: string }>();
  const signalId = params?.signalId ?? "";

  const loadSignal = useCallback(
    () => signals.get(getApiClient(), signalId),
    [signalId],
  );
  const loadEvents = useCallback(
    () => signals.events(getApiClient(), signalId),
    [signalId],
  );
  const loadReasons = useCallback(
    () => signals.reasons(getApiClient(), signalId),
    [signalId],
  );

  const signal = useApiResource(loadSignal, [signalId]);
  const events = useApiResource(loadEvents, [signalId]);
  const reasons = useApiResource(loadReasons, [signalId]);

  const modelId = signal.data?.model_id ?? null;
  const loadPromotion = useCallback(
    () =>
      modelId
        ? models.promotionStatus(getApiClient(), modelId)
        : Promise.resolve(null),
    [modelId],
  );
  const promotion = useApiResource(loadPromotion, [modelId]);

  return (
    <>
      <PageHeader title="Signal" description={signalId} />

      <Link href="/signals" className="mb-4 inline-block text-sm text-sky-400">
        Back to signals
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          {signal.loading ? <LoadingState label="Loading signal…" /> : null}
          {!signal.loading && signal.error ? (
            <ApiErrorPanel error={signal.error} onRetry={signal.reload} />
          ) : null}
          {!signal.loading && !signal.error && signal.data ? (
            <>
              <SignalDetailCard signal={signal.data} />
              <SignalActionPanel
                signal={signal.data}
                onCompleted={() => {
                  // All three, because a rejection writes an event and a
                  // reason, and the detail carries the new status.
                  signal.reload();
                  events.reload();
                  reasons.reload();
                }}
              />
            </>
          ) : null}

          {modelId ? (
            <Card title="Model promotion">
              {promotion.loading ? <LoadingState label="Checking promotion…" /> : null}
              {!promotion.loading && promotion.error ? (
                // A registry that is not configured is reported as unavailable
                // by the API. Showing it as "not promoted" would be a finding
                // nobody made.
                <ApiErrorPanel error={promotion.error} onRetry={promotion.reload} />
              ) : null}
              {!promotion.loading && !promotion.error && promotion.data ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <PromotionStatusBadge status={promotion.data} />
                    <span className="text-sm text-muted">{modelId}</span>
                  </div>
                  {promotion.data.reason ? (
                    <p className="text-sm text-slate-200">{promotion.data.reason}</p>
                  ) : null}
                  {promotion.data.state !== "promoted" ? (
                    <Alert tone="info">
                      This signal&apos;s model is not confirmed promoted. A backtest or
                      a signal is not evidence a model is ready for production.
                    </Alert>
                  ) : null}
                </div>
              ) : null}
            </Card>
          ) : null}
        </div>

        <div className="flex flex-col gap-6">
          <Card title="Lifecycle">
            {events.loading ? <LoadingState label="Loading events…" /> : null}
            {!events.loading && events.error ? (
              <ApiErrorPanel error={events.error} onRetry={events.reload} />
            ) : null}
            {!events.loading && !events.error && events.data ? (
              <SignalEventsTimeline events={events.data.items} />
            ) : null}
          </Card>

          <Card title="Reasons">
            {reasons.loading ? <LoadingState label="Loading reasons…" /> : null}
            {!reasons.loading && reasons.error ? (
              <ApiErrorPanel error={reasons.error} onRetry={reasons.reload} />
            ) : null}
            {!reasons.loading && !reasons.error && reasons.data ? (
              <SignalReasonsPanel reasons={reasons.data.items} />
            ) : null}
          </Card>
        </div>
      </div>
    </>
  );
}
