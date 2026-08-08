import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { API_ERROR_CODES, AqosApiError } from "@/api/errors";
import { AqosApiClient } from "@/api/client";
import { backtests, paper } from "@/api/resources";
import PaperPage from "@/app/paper/page";
import PaperSessionDetailPage from "@/app/paper/sessions/[sessionId]/page";
import BacktestsPage from "@/app/backtests/page";
import BacktestDetailPage from "@/app/backtests/[backtestId]/page";
import {
  PaperDecisionsTable,
  PaperResultSummary,
} from "@/components/paper";
import {
  EMPTY_PAPER_FILTERS,
  buildPaperQuery,
} from "@/components/paper/PaperSessionFilters";
import { NotReadyPanel } from "@/components/backtests";
import type { PaperSessionResult } from "@/api/types";

const fetchMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/paper",
  useParams: () => ({ sessionId: "papersession_1", backtestId: "backtest_1" }),
  useRouter: () => ({ push: vi.fn() }),
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

function ok(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req_ok" },
  });
}

function fail(status: number, code: string, message = "Refused."): Response {
  return new Response(
    JSON.stringify({
      error: { code, message, details: {}, request_id: "req_pb_err" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function pageOf<T>(items: T[], total = items.length) {
  return { items, count: items.length, total, limit: 25, offset: 0 };
}

const SESSION = {
  session_id: "papersession_1",
  user_id: "user_1",
  account_id: "account_1",
  session_name: "Morning run",
  session_type: "manual_paper_session",
  status: "completed",
  is_terminal: true,
  started_at_utc: "2026-01-01T00:00:00",
  ended_at_utc: "2026-01-01T04:00:00",
  total_trades: 1,
  net_pnl: 10,
  profit_factor: null,
  profit_factor_state: "infinite_no_losses",
  status_reason: null,
  strategy_name: "Breakout",
  model_id: null,
  model_version: null,
  symbol: "XAUUSD",
  timeframe: "H1",
  initial_balance: 10000,
  final_balance: 10010,
  realized_pnl: 10,
  max_drawdown: 0,
};

function result(overrides: Partial<PaperSessionResult> = {}): PaperSessionResult {
  return {
    session_id: "papersession_1",
    account_id: "account_1",
    has_trades: true,
    total_orders: 2,
    total_fills: 2,
    total_trades: 1,
    winning_trades: 1,
    losing_trades: 0,
    win_rate: 1,
    net_pnl: 10,
    gross_profit: 10,
    gross_loss: 0,
    profit_factor: null,
    profit_factor_state: "infinite_no_losses",
    has_infinite_profit_factor: true,
    max_drawdown: 0,
    ending_balance: 10010,
    symbols_traded: ["XAUUSD"],
    decisions_allowed: 1,
    decisions_rejected: 1,
    total_decisions: 2,
    rejection_rate: 0.5,
    top_rejection_reasons: [{ reason_code: "symbol_blocked", total: 1 }],
    calculated_at_utc: "2026-01-01T04:00:00",
    ...overrides,
  };
}

const BACKTEST = {
  backtest_id: "backtest_1",
  created_at_utc: "2026-01-01T00:00:00",
  kind: "rule_based",
  strategy_name: "csv_signal_strategy",
  symbol: "XAUUSD",
  timeframe: "H1",
  model_id: null,
  model_version: null,
  metrics: { net_profit: 4, total_trades: 1, win_rate: 1 },
  tags: [],
};

function routeFor(url: string): Response {
  if (url.includes("/paper/sessions/papersession_1/result")) return ok(result());
  if (url.includes("/paper/sessions/papersession_1/orders")) return ok(pageOf([]));
  if (url.includes("/paper/sessions/papersession_1/fills")) return ok(pageOf([]));
  if (url.includes("/paper/sessions/papersession_1/positions")) return ok(pageOf([]));
  if (url.includes("/paper/sessions/papersession_1/trades")) return ok(pageOf([]));
  if (url.includes("/paper/sessions/papersession_1/decisions")) return ok(pageOf([]));
  if (/\/paper\/sessions\/papersession_1(\?|$)/.test(url)) return ok(SESSION);
  if (url.includes("/paper/sessions")) return ok(pageOf([SESSION]));

  if (url.includes("/backtests/backtest_1/trades")) return ok(pageOf([]));
  if (url.includes("/backtests/backtest_1/orders")) return ok(pageOf([]));
  if (url.includes("/backtests/backtest_1/equity")) return ok(pageOf([]));
  if (/\/backtests\/backtest_1(\?|$)/.test(url)) return ok(BACKTEST);

  return ok(pageOf([BACKTEST]));
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: unknown) => routeFor(String(url)));
});

describe("paper query building", () => {
  it("sends only the filters a caller set", () => {
    expect(
      buildPaperQuery({ ...EMPTY_PAPER_FILTERS, status: "running", symbol: " XAUUSD " }, 25, 0),
    ).toEqual({ limit: 25, offset: 0, status: "running", symbol: "XAUUSD" });
  });

  it("carries no user_id", () => {
    const query = buildPaperQuery(EMPTY_PAPER_FILTERS, 25, 0) as Record<string, unknown>;

    expect(query["user_id"]).toBeUndefined();
  });
});

describe("the paper sessions page", () => {
  it("renders the list it fetched", async () => {
    render(<PaperPage />);

    expect(await screen.findByText("Morning run")).toBeInTheDocument();
  });

  it("says plainly that everything is simulated", async () => {
    render(<PaperPage />);

    expect(
      await screen.findByText(/No order reached a venue and no real/i),
    ).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    render(<PaperPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading sessions…");
  });

  it("shows an empty state rather than a bare table", async () => {
    fetchMock.mockImplementation(async () => ok(pageOf([])));
    render(<PaperPage />);

    expect(await screen.findByText("No paper sessions match")).toBeInTheDocument();
  });

  it("shows an API failure with its request id", async () => {
    fetchMock.mockImplementation(async () => fail(503, API_ERROR_CODES.databaseUnavailable));
    render(<PaperPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("request-id")).toHaveTextContent("req_pb_err");
  });

  it("sends the filters a caller applied", async () => {
    const user = userEvent.setup();

    render(<PaperPage />);
    await screen.findByText("Morning run");

    await user.selectOptions(screen.getByLabelText("Status"), "running");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("status=running"))).toBe(true);
    });
  });

  it("pages forward", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async () => ok(pageOf([SESSION], 100)));
    render(<PaperPage />);
    await screen.findByText("Morning run");

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("offset=25"))).toBe(true);
    });
  });

  it("offers no user_id filter and no session controls", async () => {
    render(<PaperPage />);
    await screen.findByText("Morning run");

    expect(screen.queryByLabelText(/^user/i)).toBeNull();
    expect(
      screen.queryByRole("button", { name: /new session|start|place order|submit order/i }),
    ).toBeNull();
  });
});

describe("the paper session detail page", () => {
  it("renders the session and its result", async () => {
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("Morning run")).toBeInTheDocument();
    expect(await screen.findByText("Breakout")).toBeInTheDocument();
  });

  it("renders every history table", async () => {
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("No simulated orders")).toBeInTheDocument();
    expect(screen.getByText("No simulated fills")).toBeInTheDocument();
    expect(screen.getByText("No simulated positions")).toBeInTheDocument();
    expect(screen.getByText("No simulated trades")).toBeInTheDocument();
    expect(screen.getByText("No execution decisions")).toBeInTheDocument();
  });

  it("renders no raw metadata or internal field", async () => {
    const { container } = render(<PaperSessionDetailPage />);

    await screen.findByText("Morning run");

    for (const forbidden of ["extra_metadata", "_sa_instance_state", "payload_json"]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });

  it("shows a missing session as an error with its reference", async () => {
    fetchMock.mockImplementation(async (url: unknown) =>
      /\/paper\/sessions\/papersession_1$/.test(String(url))
        ? fail(404, API_ERROR_CODES.notFound, "Paper session was not found.")
        : routeFor(String(url)),
    );
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("Paper session was not found.")).toBeInTheDocument();
  });

  it("keeps panels independent when one fails", async () => {
    fetchMock.mockImplementation(async (url: unknown) =>
      String(url).includes("/result")
        ? fail(503, API_ERROR_CODES.databaseUnavailable)
        : routeFor(String(url)),
    );
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("Morning run")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("offers no live, broker or order control", async () => {
    const { container } = render(<PaperSessionDetailPage />);

    await screen.findByText("Morning run");

    for (const wording of ["MetaTrader", "Binance", "live account", "real money order"]) {
      expect(container.textContent).not.toContain(wording);
    }

    expect(
      screen.queryByRole("button", { name: /place order|submit order|close position|execute/i }),
    ).toBeNull();
  });
});

describe("a paper result tells the truth", () => {
  it("shows measured figures when there were trades", () => {
    render(<PaperResultSummary result={result()} />);

    expect(screen.getByText("Win rate")).toBeInTheDocument();
    expect(screen.getByTestId("profit-factor")).toHaveTextContent("no losing trades");
  });

  it("says a run booked nothing rather than showing zeros", () => {
    // Nought trades and nought profit is a different claim from "never opened".
    render(
      <PaperResultSummary
        result={result({
          has_trades: false,
          total_trades: 0,
          winning_trades: 0,
          losing_trades: 0,
          win_rate: null,
          net_pnl: null,
          profit_factor: null,
          profit_factor_state: "unavailable",
        })}
      />,
    );

    expect(screen.getByTestId("no-trades")).toBeInTheDocument();
    expect(screen.queryByText("Win rate")).toBeNull();
  });

  it("keeps a measured zero visible", () => {
    render(<PaperResultSummary result={result({ max_drawdown: 0 })} />);

    expect(screen.getAllByText("0.00").length).toBeGreaterThan(0);
  });

  it("shows the refusal reasons it counted", () => {
    render(<PaperResultSummary result={result()} />);

    expect(screen.getByText(/symbol_blocked × 1/)).toBeInTheDocument();
  });

  it("prints no Infinity token", () => {
    const { container } = render(<PaperResultSummary result={result()} />);

    expect(container.textContent).not.toContain("Infinity");
    expect(container.textContent).not.toContain("NaN");
  });
});

describe("a refused decision reads as audited, not broken", () => {
  it("shows the refusal and its reason code", () => {
    render(
      <PaperDecisionsTable
        items={[
          {
            decision_id: "d1",
            session_id: "papersession_1",
            signal_id: null,
            order_id: null,
            symbol: "GBPUSD",
            is_allowed: false,
            requested_execution_mode: "manual_approval",
            effective_execution_mode: "manual_approval",
            primary_reason_code: "symbol_blocked",
            blocking_reason_count: 1,
            blocking_sources: ["symbol"],
            reasons: [],
            decided_at_utc: "2026-01-01T00:00:00",
          },
        ]}
      />,
    );

    expect(screen.getByText("refused")).toBeInTheDocument();
    expect(screen.getByText("symbol_blocked")).toBeInTheDocument();
    expect(screen.getByText("symbol")).toBeInTheDocument();
  });

  it("shows an allowed decision as allowed", () => {
    render(
      <PaperDecisionsTable
        items={[
          {
            decision_id: "d2",
            session_id: "papersession_1",
            signal_id: null,
            order_id: "o1",
            symbol: "XAUUSD",
            is_allowed: true,
            requested_execution_mode: "manual_approval",
            effective_execution_mode: "manual_approval",
            primary_reason_code: null,
            blocking_reason_count: 0,
            blocking_sources: [],
            reasons: [],
            decided_at_utc: "2026-01-01T00:00:00",
          },
        ]}
      />,
    );

    expect(screen.getByText("allowed")).toBeInTheDocument();
  });
});

describe("unavailable is never shown as empty", () => {
  it("renders an unconfigured registry as not ready", () => {
    render(
      <NotReadyPanel
        error={
          new AqosApiError({
            code: API_ERROR_CODES.notReady,
            message: "This deployment has no backtest registry configured.",
            status: 503,
            requestId: "req_nr",
          })
        }
      />,
    );

    expect(screen.getByTestId("not-ready")).toBeInTheDocument();
    expect(screen.getByText(/not the same as having no results/i)).toBeInTheDocument();
    expect(screen.getByTestId("request-id")).toHaveTextContent("req_nr");
  });

  it("falls back to the ordinary error panel for other failures", () => {
    render(
      <NotReadyPanel
        error={
          new AqosApiError({
            code: API_ERROR_CODES.forbidden,
            message: "Not yours.",
            status: 403,
            requestId: "req_f",
          })
        }
      />,
    );

    expect(screen.queryByTestId("not-ready")).toBeNull();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("the backtests page", () => {
  it("renders the list it fetched", async () => {
    render(<BacktestsPage />);

    expect(await screen.findByText("csv_signal_strategy")).toBeInTheDocument();
  });

  it("shows an unconfigured registry as not ready, not empty", async () => {
    fetchMock.mockImplementation(async () =>
      fail(503, API_ERROR_CODES.notReady, "No backtest registry configured."),
    );
    render(<BacktestsPage />);

    expect(await screen.findByTestId("not-ready")).toBeInTheDocument();
    expect(screen.queryByText("No backtest runs")).toBeNull();
  });

  it("shows a configured empty registry as empty", async () => {
    fetchMock.mockImplementation(async () => ok(pageOf([])));
    render(<BacktestsPage />);

    expect(await screen.findByText("No backtest runs")).toBeInTheDocument();
    expect(screen.queryByTestId("not-ready")).toBeNull();
  });

  it("offers a run form but never a path or URL field", async () => {
    // Sprint 068 added the run form. What must stay absent is any way to name
    // a location: the dataset is a configured name and nothing else.
    render(<BacktestsPage />);
    await screen.findByText("csv_signal_strategy");

    expect(screen.getByLabelText("Dataset")).toBeInTheDocument();
    expect(screen.queryByLabelText(/file path|directory|url/i)).toBeNull();
  });
});

describe("the backtest detail page", () => {
  it("renders the run and its metrics", async () => {
    render(<BacktestDetailPage />);

    expect(await screen.findByText("csv_signal_strategy")).toBeInTheDocument();
    expect(await screen.findByText("net profit")).toBeInTheDocument();
  });

  it("renders a missing artifact as not ready, not an empty table", async () => {
    // An empty table would claim the run produced nothing.
    fetchMock.mockImplementation(async (url: unknown) =>
      String(url).includes("/trades")
        ? fail(503, API_ERROR_CODES.notReady, "The stored report is not available.")
        : routeFor(String(url)),
    );
    render(<BacktestDetailPage />);

    expect(await screen.findByTestId("not-ready")).toBeInTheDocument();
    expect(screen.queryByText("No trades in this run")).toBeNull();
  });

  it("renders no filesystem path", async () => {
    const { container } = render(<BacktestDetailPage />);

    await screen.findByText("csv_signal_strategy");

    for (const forbidden of ["report_path", "/srv/", "C:\\", ".csv", "data_path"]) {
      expect(container.textContent).not.toContain(forbidden);
    }
  });
});

describe("the paper and backtest APIs are read-only", () => {
  const client = () =>
    new AqosApiClient({
      baseUrl: "http://localhost:8000",
      getToken: () => "tok",
      fetchImpl: (...args: unknown[]) => fetchMock(...args),
    });

  it("requests every paper path", async () => {
    await paper.listSessions(client());
    await paper.getSession(client(), "s1");
    await paper.result(client(), "s1");
    await paper.orders(client(), "s1");
    await paper.fills(client(), "s1");
    await paper.positions(client(), "s1");
    await paper.trades(client(), "s1");
    await paper.decisions(client(), "s1");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(urls[2]).toContain("/paper/sessions/s1/result");
    expect(urls[7]).toContain("/paper/sessions/s1/decisions");
  });

  it("requests every backtest path", async () => {
    await backtests.list(client());
    await backtests.get(client(), "b1");
    await backtests.trades(client(), "b1");
    await backtests.orders(client(), "b1");
    await backtests.equity(client(), "b1");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(urls[2]).toContain("/backtests/b1/trades");
    expect(urls[4]).toContain("/backtests/b1/equity");
  });

  it("uses GET for every one", async () => {
    await paper.listSessions(client());
    await paper.result(client(), "s1");
    await backtests.list(client());
    await backtests.equity(client(), "b1");

    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit).method).toBe("GET");
    }
  });

  it("exposes no mutation method", () => {
    for (const forbidden of ["create", "start", "pause", "submitOrder", "run"]) {
      expect(Object.keys(paper)).not.toContain(forbidden);
      expect(Object.keys(backtests)).not.toContain(forbidden);
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

    await expect(paper.getSession(client(), "s1")).rejects.toMatchObject({
      status,
      code,
      requestId: "req_pb_err",
    });
  });
});
