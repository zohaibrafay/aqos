"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useState } from "react";

import { accounts } from "@/api/resources";
import {
  AccountDetailCard,
  AnalyticsSnapshotsTable,
  AnalyticsSummaryPanel,
  ExecutionConstraintsPanel,
  FundedRulesPanel,
  ReportDetailPanel,
  ReportsTable,
} from "@/components/accounts";
import { LoadingState } from "@/components/states";
import { ApiErrorPanel } from "@/components/states/ApiErrorPanel";
import { Card, PageHeader } from "@/components/ui";
import { useApiResource } from "@/hooks/useApiResource";
import { getApiClient } from "@/lib/api";

/**
 * One account, with everything the API will say about it.
 *
 * Each panel fetches and fails on its own, so a funded-rules outage does not
 * hide the balances and an unavailable report does not blank the constraints.
 * Nothing on this page changes anything: it is a report, not a control panel.
 */
export default function AccountDetailPage() {
  const params = useParams<{ accountId: string }>();
  const accountId = params?.accountId ?? "";
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  const client = getApiClient;

  const account = useApiResource(
    useCallback(() => accounts.get(client(), accountId), [accountId, client]),
    [accountId],
  );
  const constraints = useApiResource(
    useCallback(
      () => accounts.executionConstraints(client(), accountId),
      [accountId, client],
    ),
    [accountId],
  );
  const funded = useApiResource(
    useCallback(() => accounts.fundedRules(client(), accountId), [accountId, client]),
    [accountId],
  );
  const analytics = useApiResource(
    useCallback(() => accounts.analytics(client(), accountId), [accountId, client]),
    [accountId],
  );
  const snapshots = useApiResource(
    useCallback(
      () => accounts.analyticsSnapshots(client(), accountId, { limit: 10 }),
      [accountId, client],
    ),
    [accountId],
  );
  const reports = useApiResource(
    useCallback(
      () => accounts.reports(client(), accountId, { limit: 25 }),
      [accountId, client],
    ),
    [accountId],
  );
  const report = useApiResource(
    useCallback(
      () =>
        selectedReportId
          ? accounts.report(client(), accountId, selectedReportId)
          : Promise.resolve(null),
      [accountId, selectedReportId, client],
    ),
    [accountId, selectedReportId],
  );

  return (
    <>
      <PageHeader title="Account" description={accountId} />

      <Link href="/accounts" className="mb-4 inline-block text-sm text-sky-400">
        Back to accounts
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          {account.loading ? <LoadingState label="Loading account…" /> : null}
          {!account.loading && account.error ? (
            <ApiErrorPanel error={account.error} onRetry={account.reload} />
          ) : null}
          {!account.loading && !account.error && account.data ? (
            <AccountDetailCard account={account.data} />
          ) : null}

          <Card title="Execution constraints">
            {constraints.loading ? <LoadingState label="Loading constraints…" /> : null}
            {!constraints.loading && constraints.error ? (
              <ApiErrorPanel error={constraints.error} onRetry={constraints.reload} />
            ) : null}
            {!constraints.loading && !constraints.error && constraints.data ? (
              <ExecutionConstraintsPanel constraints={constraints.data} />
            ) : null}
          </Card>

          <Card title="Funded rules">
            {funded.loading ? <LoadingState label="Loading rules…" /> : null}
            {!funded.loading && funded.error ? (
              <ApiErrorPanel error={funded.error} onRetry={funded.reload} />
            ) : null}
            {!funded.loading && !funded.error ? (
              <FundedRulesPanel rules={funded.data} />
            ) : null}
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          <Card title="Analytics">
            {analytics.loading ? <LoadingState label="Loading analytics…" /> : null}
            {!analytics.loading && analytics.error ? (
              <ApiErrorPanel error={analytics.error} onRetry={analytics.reload} />
            ) : null}
            {!analytics.loading && !analytics.error && analytics.data ? (
              <AnalyticsSummaryPanel analytics={analytics.data} />
            ) : null}
          </Card>

          <Card title="Stored snapshots">
            {snapshots.loading ? <LoadingState label="Loading snapshots…" /> : null}
            {!snapshots.loading && snapshots.error ? (
              <ApiErrorPanel error={snapshots.error} onRetry={snapshots.reload} />
            ) : null}
            {!snapshots.loading && !snapshots.error && snapshots.data ? (
              <AnalyticsSnapshotsTable items={snapshots.data.items} />
            ) : null}
          </Card>

          <Card title="Reports">
            {reports.loading ? <LoadingState label="Loading reports…" /> : null}
            {!reports.loading && reports.error ? (
              <ApiErrorPanel error={reports.error} onRetry={reports.reload} />
            ) : null}
            {!reports.loading && !reports.error && reports.data ? (
              <ReportsTable
                items={reports.data.items}
                selectedId={selectedReportId}
                onSelect={setSelectedReportId}
              />
            ) : null}

            {selectedReportId ? (
              <div className="mt-4 border-t border-edge pt-4">
                {report.loading ? <LoadingState label="Loading report…" /> : null}
                {!report.loading && report.error ? (
                  <ApiErrorPanel error={report.error} onRetry={report.reload} />
                ) : null}
                {!report.loading && !report.error && report.data ? (
                  <ReportDetailPanel report={report.data} />
                ) : null}
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    </>
  );
}
