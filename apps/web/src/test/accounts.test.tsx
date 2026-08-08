import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { API_ERROR_CODES } from "@/api/errors";
import { AqosApiClient } from "@/api/client";
import { accounts } from "@/api/resources";
import AccountsPage from "@/app/accounts/page";
import AccountDetailPage from "@/app/accounts/[accountId]/page";
import {
  AnalyticsSnapshotsTable,
  AnalyticsSummaryPanel,
  FundedRulesPanel,
  MetricValue,
  ProfitFactorValue,
  formatMoney,
  formatPercent,
} from "@/components/accounts";
import {
  EMPTY_ACCOUNT_FILTERS,
  buildAccountQuery,
} from "@/components/accounts/AccountFilters";
import type { AccountAnalytics, AnalyticsSnapshot } from "@/api/types";

const fetchMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts",
  useParams: () => ({ accountId: "account_1" }),
}));

vi.mock("@/lib/api", async () => {
  const { AqosApiClient: Client } = await import("@/api/client");

  return {
    getApiClient: () =>
      new Client({
        baseUrl: "http://localhost:8000",
        getToken: () => "tok",
        fetchImpl: (...args: unknown[]) => fetchMock(...args),
      }),
    resetApiClientForTests: () => undefined,
  };
});

function ok(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req_ok" },
  });
}

function fail(status: number, code: string, message = "Refused."): Response {
  return new Response(
    JSON.stringify({
      error: { code, message, details: {}, request_id: "req_acc_err" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function pageOf<T>(items: T[], total = items.length) {
  return { items, count: items.length, total, limit: 25, offset: 0 };
}

const ACCOUNT = {
  account_id: "account_1",
  user_id: "user_1",
  account_name: "Paper One",
  account_type: "paper",
  venue: "internal_paper",
  status: "active",
  currency: "USD",
  execution_mode: "manual_approval",
  auto_trade_enabled: false,
  is_default: true,
  is_real_money: false,
  created_at_utc: "2026-01-01T00:00:00",
  initial_balance: 10000,
  current_balance: 10000,
  equity: 10000,
  leverage: 100,
  is_tradable: true,
  updated_at_utc: "2026-01-02T00:00:00",
};

const CONSTRAINTS = {
  account_id: "account_1",
  stored_execution_mode: "manual_approval",
  auto_trade_enabled: false,
  requested_execution_mode: "auto_trade",
  effective_execution_mode: "manual_approval",
  was_downgraded: true,
  allows_orders: true,
  requires_manual_approval: true,
  binding_sources: ["account_settings"],
  explanation: "Auto-trade is not enabled on this account.",
  constraints: [
    {
      source: "account_settings",
      allowed_mode: "manual_approval",
      reason: "Auto-trade capability is off.",
    },
  ],
};

const UNAVAILABLE_ANALYTICS: AccountAnalytics = {
  scope: "account",
  account_id: "account_1",
  calculated_at_utc: "2026-01-02T00:00:00",
  has_trade_metrics: false,
  signal_metrics: {
    signals_received: 10,
    signals_executed: 0,
    signals_rejected: 3,
    signals_missed: 0,
    execution_rate: 0,
    rejection_rate: 0.3,
  },
  trade_metrics: {
    is_available: false,
    unavailable_reason: "No trade source is connected to this endpoint.",
    total_trades: null,
    win_rate: null,
    net_pnl: null,
    profit_factor: null,
    profit_factor_state: null,
    max_drawdown: null,
  },
  trade_metrics_source: {
    connected: false,
    reason_code: "trade_source_not_connected",
    reason: "This endpoint connects no trade source.",
    measured_metrics_endpoint: "/accounts/account_1/analytics/snapshots",
  },
};

function snapshot(overrides: Partial<AnalyticsSnapshot> = {}): AnalyticsSnapshot {
  return {
    snapshot_id: "snap_1",
    account_id: "account_1",
    scope: "account",
    period_start_utc: "2026-01-01T00:00:00",
    period_end_utc: "2026-01-02T00:00:00",
    calculated_at_utc: "2026-01-02T00:00:00",
    signals_received: 10,
    signals_executed: 2,
    trade_metrics_available: true,
    total_trades: 2,
    win_rate: 1,
    net_pnl: 15,
    profit_factor: null,
    profit_factor_state: "infinite_no_losses",
    has_infinite_profit_factor: true,
    max_drawdown: 0,
    ...overrides,
  };
}

const REPORT = {
  report_id: "report_1",
  account_id: "account_1",
  account_type: "paper",
  report_type: "account_performance",
  analytics_snapshot_id: "snap_1",
  period_start_utc: "2026-01-01T00:00:00",
  period_end_utc: "2026-01-02T00:00:00",
  generated_at_utc: "2026-01-02T00:00:00",
  trade_metrics_available: true,
  artifact_format: "json",
  has_artifact: true,
};

function routeFor(url: string): Response {
  if (url.includes("/execution-constraints")) return ok(CONSTRAINTS);
  if (url.includes("/funded-rules")) return ok(null);
  if (url.includes("/analytics/snapshots")) return ok(pageOf([snapshot()]));
  if (url.includes("/analytics")) return ok(UNAVAILABLE_ANALYTICS);
  if (/\/reports\/report_1$/.test(url)) {
    return ok({ ...REPORT, payload: { net_pnl: 15, total_trades: 2 } });
  }
  if (url.includes("/reports")) return ok(pageOf([REPORT]));
  if (/\/accounts\/account_1(\?|$)/.test(url)) return ok(ACCOUNT);

  return ok(pageOf([ACCOUNT]));
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: unknown) => routeFor(String(url)));
});

describe("account query building", () => {
  it("sends only the filters a caller set", () => {
    expect(
      buildAccountQuery(
        { ...EMPTY_ACCOUNT_FILTERS, account_type: "paper", status: "active" },
        25,
        0,
      ),
    ).toEqual({ limit: 25, offset: 0, account_type: "paper", status: "active" });
  });

  it("carries no user_id", () => {
    const query = buildAccountQuery(EMPTY_ACCOUNT_FILTERS, 25, 0) as Record<
      string,
      unknown
    >;

    expect(query["user_id"]).toBeUndefined();
  });
});

describe("unknown never becomes zero", () => {
  it("renders an absent number as a dash", () => {
    render(<MetricValue value={null} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders a measured zero as zero", () => {
    // A measured nought is a fact. A dash would hide it.
    render(<MetricValue value={0} digits={0} />);

    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("renders an absent percentage as a dash and a zero one as zero", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0.0%");
  });

  it("renders an absent amount as a dash and a zero one as zero", () => {
    expect(formatMoney(null, "USD")).toBe("—");
    expect(formatMoney(0, "USD")).toBe("0.00 USD");
  });

  it("never renders a non-finite number", () => {
    render(<MetricValue value={Number.POSITIVE_INFINITY} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("a profit factor says which kind of blank it is", () => {
  it("shows a wins-only run as having no losing trades", () => {
    render(<ProfitFactorValue value={null} state="infinite_no_losses" />);

    expect(screen.getByTestId("profit-factor")).toHaveTextContent(
      "no losing trades",
    );
  });

  it("shows an uncalculable one as unavailable", () => {
    render(<ProfitFactorValue value={null} state="unavailable" />);

    expect(screen.getByTestId("profit-factor")).toHaveTextContent("unavailable");
  });

  it("keeps the two apart", () => {
    // Both arrive as null. Only the state separates them.
    const { unmount } = render(
      <ProfitFactorValue value={null} state="infinite_no_losses" />,
    );
    const infinite = screen.getByTestId("profit-factor").textContent;

    unmount();
    render(<ProfitFactorValue value={null} state="unavailable" />);

    expect(screen.getByTestId("profit-factor").textContent).not.toBe(infinite);
  });

  it("shows a measured factor as a number", () => {
    render(<ProfitFactorValue value={3} state="finite" />);

    expect(screen.getByTestId("profit-factor")).toHaveTextContent("3.00");
  });

  it("never prints an Infinity token", () => {
    const { container } = render(
      <ProfitFactorValue value={null} state="infinite_no_losses" />,
    );

    expect(container.textContent).not.toContain("Infinity");
    expect(container.textContent).not.toContain("NaN");
  });
});

describe("the accounts page", () => {
  it("renders the list it fetched", async () => {
    render(<AccountsPage />);

    expect(await screen.findByText("Paper One")).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    render(<AccountsPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading accounts…");
  });

  it("shows an empty state rather than a bare table", async () => {
    fetchMock.mockImplementation(async () => ok(pageOf([])));
    render(<AccountsPage />);

    expect(await screen.findByText("No accounts match")).toBeInTheDocument();
  });

  it("shows an API failure with its request id", async () => {
    fetchMock.mockImplementation(async () =>
      fail(503, API_ERROR_CODES.databaseUnavailable),
    );
    render(<AccountsPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("request-id")).toHaveTextContent("req_acc_err");
  });

  it("sends the filters a caller applied", async () => {
    const user = userEvent.setup();

    render(<AccountsPage />);
    await screen.findByText("Paper One");

    await user.selectOptions(screen.getByLabelText("Type"), "paper");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("account_type=paper"))).toBe(true);
    });
  });

  it("pages forward", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async () => ok(pageOf([ACCOUNT], 100)));
    render(<AccountsPage />);
    await screen.findByText("Paper One");

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("offset=25"))).toBe(true);
    });
  });

  it("offers no user_id filter and no create button", async () => {
    render(<AccountsPage />);
    await screen.findByText("Paper One");

    expect(screen.queryByLabelText(/user/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /new account|create/i })).toBeNull();
  });
});

describe("the account detail page", () => {
  it("renders the safe fields", async () => {
    render(<AccountDetailPage />);

    expect(await screen.findByText("Paper One")).toBeInTheDocument();
    // Initial balance, current balance and equity all read the same here.
    expect(screen.getAllByText("10000.00 USD").length).toBeGreaterThan(0);
  });

  it("renders no credential, connection reference or raw metadata", async () => {
    const { container } = render(<AccountDetailPage />);

    await screen.findByText("Paper One");

    for (const forbidden of [
      "broker_credential_ref",
      "broker_account_ref",
      "extra_metadata",
      "_sa_instance_state",
      "password",
      "token",
    ]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });

  it("shows the execution constraints read-only", async () => {
    render(<AccountDetailPage />);

    expect(
      await screen.findByText("Auto-trade is not enabled on this account."),
    ).toBeInTheDocument();
    // Shown as the binding source and again in the constraint list.
    expect(screen.getAllByText("account_settings").length).toBeGreaterThan(0);
  });

  it("offers no control to change execution mode or auto-trade", async () => {
    render(<AccountDetailPage />);
    await screen.findByText("Paper One");

    expect(screen.queryByRole("button", { name: /enable auto|change mode|save/i })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("shows an account that is not found as an error with its reference", async () => {
    fetchMock.mockImplementation(async (url: unknown) =>
      /\/accounts\/account_1$/.test(String(url))
        ? fail(404, API_ERROR_CODES.notFound, "Account was not found.")
        : routeFor(String(url)),
    );
    render(<AccountDetailPage />);

    expect(await screen.findByText("Account was not found.")).toBeInTheDocument();
    expect(screen.getAllByTestId("request-id")[0]).toHaveTextContent("req_acc_err");
  });

  it("keeps panels independent when one fails", async () => {
    // A funded-rules outage must not blank the balances.
    fetchMock.mockImplementation(async (url: unknown) =>
      String(url).includes("/funded-rules")
        ? fail(503, API_ERROR_CODES.databaseUnavailable)
        : routeFor(String(url)),
    );
    render(<AccountDetailPage />);

    expect(await screen.findByText("Paper One")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("analytics tells the truth about what it measured", () => {
  it("explains why trade metrics are unavailable", () => {
    render(<AnalyticsSummaryPanel analytics={UNAVAILABLE_ANALYTICS} />);

    expect(screen.getByTestId("trade-metrics-unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/No trade source is connected to this endpoint./),
    ).toBeInTheDocument();
  });

  it("points at where the measured numbers live", () => {
    render(<AnalyticsSummaryPanel analytics={UNAVAILABLE_ANALYTICS} />);

    expect(screen.getByText(/analytics snapshots/i)).toBeInTheDocument();
  });

  it("shows no trade figures at all when none were measured", () => {
    // Zeros here would claim the account traded and broke even.
    render(<AnalyticsSummaryPanel analytics={UNAVAILABLE_ANALYTICS} />);

    expect(screen.queryByText("Total trades")).toBeNull();
    expect(screen.queryByText("Win rate")).toBeNull();
  });

  it("still shows the measured signal figures, including a real zero", () => {
    render(<AnalyticsSummaryPanel analytics={UNAVAILABLE_ANALYTICS} />);

    expect(screen.getByText("Received")).toBeInTheDocument();
    expect(screen.getByText("0.0%")).toBeInTheDocument();
  });

  it("shows trade figures when they were measured", () => {
    render(
      <AnalyticsSummaryPanel
        analytics={{
          ...UNAVAILABLE_ANALYTICS,
          has_trade_metrics: true,
          trade_metrics: {
            is_available: true,
            unavailable_reason: null,
            total_trades: 4,
            win_rate: 0.5,
            net_pnl: 12.5,
            profit_factor: 2,
            profit_factor_state: "finite",
            max_drawdown: 3,
          },
        }}
      />,
    );

    expect(screen.getByText("Total trades")).toBeInTheDocument();
    expect(screen.getByTestId("profit-factor")).toHaveTextContent("2.00");
  });
});

describe("snapshots carry measured trade metrics", () => {
  it("renders a stored snapshot", () => {
    render(<AnalyticsSnapshotsTable items={[snapshot()]} />);

    expect(screen.getByText("15.00")).toBeInTheDocument();
    expect(screen.getByTestId("profit-factor")).toHaveTextContent(
      "no losing trades",
    );
  });

  it("says nothing is stored rather than showing an empty table", () => {
    render(<AnalyticsSnapshotsTable items={[]} />);

    expect(screen.getByText("No stored snapshots")).toBeInTheDocument();
  });

  it("keeps a measured zero drawdown visible", () => {
    render(<AnalyticsSnapshotsTable items={[snapshot({ max_drawdown: 0 })]} />);

    expect(screen.getByText("0.00")).toBeInTheDocument();
  });
});

describe("funded rules are honest about absence", () => {
  it("says there are none rather than showing blanks", () => {
    render(<FundedRulesPanel rules={null} />);

    expect(screen.getByText("No funded rules")).toBeInTheDocument();
  });

  it("names no firm", () => {
    const { container } = render(<FundedRulesPanel rules={null} />);

    for (const firm of ["FTMO", "MyForexFunds", "Topstep", "Apex"]) {
      expect(container.textContent).not.toContain(firm);
    }
  });
});

describe("reports expose no location", () => {
  it("lists a report and opens its detail", async () => {
    const user = userEvent.setup();

    render(<AccountDetailPage />);
    await screen.findByText("Paper One");

    await user.click(await screen.findByRole("button", { name: "account_performance" }));

    expect(await screen.findByTestId("report-payload")).toBeInTheDocument();
  });

  it("renders no filesystem path or checksum", async () => {
    const user = userEvent.setup();
    const { container } = render(<AccountDetailPage />);

    await screen.findByText("Paper One");
    await user.click(await screen.findByRole("button", { name: "account_performance" }));
    await screen.findByTestId("report-payload");

    for (const forbidden of [
      "artifact_path",
      "report_path",
      "/srv/",
      "C:\\",
      "checksum",
      "sha256",
    ]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });

  it("offers no download", async () => {
    render(<AccountDetailPage />);
    await screen.findByText("Paper One");

    expect(screen.queryByRole("button", { name: /download/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /download/i })).toBeNull();
  });
});

describe("the account API is read-only", () => {
  const client = () =>
    new AqosApiClient({
      baseUrl: "http://localhost:8000",
      getToken: () => "tok",
      fetchImpl: (...args: unknown[]) => fetchMock(...args),
    });

  it("requests every account path", async () => {
    await accounts.list(client());
    await accounts.get(client(), "account_1");
    await accounts.executionConstraints(client(), "account_1");
    await accounts.fundedRules(client(), "account_1");
    await accounts.analytics(client(), "account_1");
    await accounts.analyticsSnapshots(client(), "account_1");
    await accounts.reports(client(), "account_1");
    await accounts.report(client(), "account_1", "report_1");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(urls[1]).toContain("/api/v1/accounts/account_1");
    expect(urls[2]).toContain("/execution-constraints");
    expect(urls[3]).toContain("/funded-rules");
    expect(urls[4]).toContain("/analytics");
    expect(urls[5]).toContain("/analytics/snapshots");
    expect(urls[6]).toContain("/reports");
    expect(urls[7]).toContain("/reports/report_1");
  });

  it("uses GET for every one", async () => {
    await accounts.list(client());
    await accounts.get(client(), "account_1");
    await accounts.analytics(client(), "account_1");

    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit).method).toBe("GET");
    }
  });

  it("exposes no mutation method", () => {
    const names = Object.keys(accounts);

    for (const forbidden of ["create", "update", "delete", "setExecutionMode", "setFundedRules"]) {
      expect(names).not.toContain(forbidden);
    }
  });

  it.each([
    [401, API_ERROR_CODES.unauthorized],
    [403, API_ERROR_CODES.forbidden],
    [404, API_ERROR_CODES.notFound],
    [409, API_ERROR_CODES.conflict],
    [422, API_ERROR_CODES.validation],
    [429, API_ERROR_CODES.rateLimited],
    [503, API_ERROR_CODES.notReady],
  ])("turns %i into an error carrying its request id", async (status, code) => {
    fetchMock.mockImplementation(async () => fail(status, code));

    await expect(accounts.get(client(), "account_1")).rejects.toMatchObject({
      status,
      code,
      requestId: "req_acc_err",
    });
  });
});
