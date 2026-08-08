"use client";

import { useCallback, useMemo, useState } from "react";

import { signals } from "@/api/resources";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { EmptyState, LoadingState } from "@/components/states";
import { Button, Card, PageHeader } from "@/components/ui";
import { SignalListTable } from "@/components/signals";
import {
  EMPTY_FILTERS,
  SignalFilters,
  buildSignalQuery,
  type SignalFilterValues,
} from "@/components/signals/SignalFilters";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

const PAGE_SIZE = 25;

/**
 * The signal list.
 *
 * Read-only. The backend scopes every result to the caller, so this page shows
 * one user their own signals and offers no way to ask for anybody else's.
 */
export default function SignalsPage() {
  const [draft, setDraft] = useState<SignalFilterValues>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<SignalFilterValues>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);

  const query = useMemo(
    () => buildSignalQuery(applied, PAGE_SIZE, offset),
    [applied, offset],
  );

  const load = useCallback(() => signals.list(getApiClient(), query), [query]);
  const { data, error, loading, reload } = useApiResource(load, [query]);

  const apply = () => {
    setOffset(0);
    setApplied(draft);
  };

  const reset = () => {
    setOffset(0);
    setDraft(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
  };

  const total = data?.total ?? null;
  const hasMore =
    data !== null && (total === null ? data.count === PAGE_SIZE : offset + PAGE_SIZE < total);

  return (
    <>
      <PageHeader
        title="Signals"
        description="Your trading signals and where each one ended up."
      />

      <SignalFilters
        values={draft}
        onChange={setDraft}
        onApply={apply}
        onReset={reset}
        disabled={loading}
      />

      <Card>
        {loading ? <LoadingState label="Loading signals…" /> : null}

        {!loading && error ? <ApiErrorPanel error={error} onRetry={reload} /> : null}

        {!loading && !error && data && data.items.length === 0 ? (
          <EmptyState
            title="No signals match"
            description="Nothing here yet, or nothing matching these filters."
          />
        ) : null}

        {!loading && !error && data && data.items.length > 0 ? (
          <>
            <SignalListTable items={data.items} />
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-muted" data-testid="page-summary">
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
