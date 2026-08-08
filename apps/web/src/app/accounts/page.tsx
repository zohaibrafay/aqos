"use client";

import { useCallback, useMemo, useState } from "react";

import { accounts } from "@/api/resources";
import { AccountListTable } from "@/components/accounts";
import {
  AccountFilters,
  EMPTY_ACCOUNT_FILTERS,
  buildAccountQuery,
  type AccountFilterValues,
} from "@/components/accounts/AccountFilters";
import { EmptyState, LoadingState } from "@/components/states";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Button, Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

const PAGE_SIZE = 25;

/**
 * The account list.
 *
 * Read-only. There is no button here to create, edit or close an account, and
 * no way to change how one executes.
 */
export default function AccountsPage() {
  const [draft, setDraft] = useState<AccountFilterValues>(EMPTY_ACCOUNT_FILTERS);
  const [applied, setApplied] = useState<AccountFilterValues>(EMPTY_ACCOUNT_FILTERS);
  const [offset, setOffset] = useState(0);

  const query = useMemo(
    () => buildAccountQuery(applied, PAGE_SIZE, offset),
    [applied, offset],
  );

  const load = useCallback(() => accounts.list(getApiClient(), query), [query]);
  const { data, error, loading, reload } = useApiResource(load, [query]);

  const total = data?.total ?? null;
  const hasMore =
    data !== null &&
    (total === null ? data.count === PAGE_SIZE : offset + PAGE_SIZE < total);

  return (
    <>
      <PageHeader
        title="Accounts"
        description="Your trading accounts and what each one is allowed to do."
      />

      <AccountFilters
        values={draft}
        onChange={setDraft}
        onApply={() => {
          setOffset(0);
          setApplied(draft);
        }}
        onReset={() => {
          setOffset(0);
          setDraft(EMPTY_ACCOUNT_FILTERS);
          setApplied(EMPTY_ACCOUNT_FILTERS);
        }}
        disabled={loading}
      />

      <Card>
        {loading ? <LoadingState label="Loading accounts…" /> : null}

        {!loading && error ? <ApiErrorPanel error={error} onRetry={reload} /> : null}

        {!loading && !error && data && data.items.length === 0 ? (
          <EmptyState
            title="No accounts match"
            description="Nothing here yet, or nothing matching these filters."
          />
        ) : null}

        {!loading && !error && data && data.items.length > 0 ? (
          <>
            <AccountListTable items={data.items} />
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-muted" data-testid="account-page-summary">
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
