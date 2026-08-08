"use client";

import { useCallback, useMemo, useState } from "react";

import { backtests } from "@/api/resources";
import { BacktestListTable, NotReadyPanel } from "@/components/backtests";
import { EmptyState, LoadingState } from "@/components/states";
import { Button, Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

const PAGE_SIZE = 25;

/**
 * Historical backtest runs.
 *
 * Read-only in this sprint. Starting a run needs a dataset picker and bounded
 * inputs done carefully, which is a sprint of its own rather than a form
 * bolted onto a list.
 */
export default function BacktestsPage() {
  const [offset, setOffset] = useState(0);

  const query = useMemo(() => ({ limit: PAGE_SIZE, offset }), [offset]);
  const load = useCallback(() => backtests.list(getApiClient(), query), [query]);
  const { data, error, loading, reload } = useApiResource(load, [query]);

  const total = data?.total ?? null;
  const hasMore =
    data !== null &&
    (total === null ? data.count === PAGE_SIZE : offset + PAGE_SIZE < total);

  return (
    <>
      <PageHeader
        title="Backtests"
        description="Historical strategy runs and what each one measured."
      />

      <Card>
        {loading ? <LoadingState label="Loading backtests…" /> : null}

        {/* An unconfigured registry is reported as not ready, never as empty. */}
        {!loading && error ? <NotReadyPanel error={error} onRetry={reload} /> : null}

        {!loading && !error && data && data.items.length === 0 ? (
          <EmptyState
            title="No backtest runs"
            description="The registry is configured and holds nothing yet."
          />
        ) : null}

        {!loading && !error && data && data.items.length > 0 ? (
          <>
            <BacktestListTable items={data.items} />
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-muted" data-testid="backtest-page-summary">
                Showing {data.count}
                {total === null ? "" : ` of ${total}`}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  disabled={!hasMore}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </Card>
    </>
  );
}
