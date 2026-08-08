"use client";

import { useCallback, useMemo, useState } from "react";

import { paper } from "@/api/resources";
import { PaperSessionListTable, SimulatedNotice } from "@/components/paper";
import {
  EMPTY_PAPER_FILTERS,
  PaperSessionFilters,
  buildPaperQuery,
  type PaperFilterValues,
} from "@/components/paper/PaperSessionFilters";
import { EmptyState, LoadingState } from "@/components/states";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Button, Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

const PAGE_SIZE = 25;

/**
 * Simulated trading runs.
 *
 * Read-only in this sprint. Creating a session, starting one or submitting an
 * order are decisions with their own confirmation rules, and they arrive with
 * their own sprint rather than half-built here.
 */
export default function PaperPage() {
  const [draft, setDraft] = useState<PaperFilterValues>(EMPTY_PAPER_FILTERS);
  const [applied, setApplied] = useState<PaperFilterValues>(EMPTY_PAPER_FILTERS);
  const [offset, setOffset] = useState(0);

  const query = useMemo(
    () => buildPaperQuery(applied, PAGE_SIZE, offset),
    [applied, offset],
  );
  const load = useCallback(() => paper.listSessions(getApiClient(), query), [query]);
  const { data, error, loading, reload } = useApiResource(load, [query]);

  const total = data?.total ?? null;
  const hasMore =
    data !== null &&
    (total === null ? data.count === PAGE_SIZE : offset + PAGE_SIZE < total);

  return (
    <>
      <PageHeader
        title="Paper trading"
        description="Simulated runs, their results and every decision behind them."
      />
      <SimulatedNotice />

      <PaperSessionFilters
        values={draft}
        onChange={setDraft}
        onApply={() => {
          setOffset(0);
          setApplied(draft);
        }}
        onReset={() => {
          setOffset(0);
          setDraft(EMPTY_PAPER_FILTERS);
          setApplied(EMPTY_PAPER_FILTERS);
        }}
        disabled={loading}
      />

      <Card>
        {loading ? <LoadingState label="Loading sessions…" /> : null}
        {!loading && error ? <ApiErrorPanel error={error} onRetry={reload} /> : null}
        {!loading && !error && data && data.items.length === 0 ? (
          <EmptyState
            title="No paper sessions match"
            description="Nothing here yet, or nothing matching these filters."
          />
        ) : null}
        {!loading && !error && data && data.items.length > 0 ? (
          <>
            <PaperSessionListTable items={data.items} />
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-muted" data-testid="paper-page-summary">
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
