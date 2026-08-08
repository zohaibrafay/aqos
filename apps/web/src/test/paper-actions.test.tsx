import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { API_ERROR_CODES } from "@/api/errors";
import { AqosApiClient } from "@/api/client";
import {
  PAPER_REASON_REQUIRED,
  PAPER_SESSION_ACTIONS,
  backtestActions,
  paperActions,
} from "@/api/resources";
import PaperSessionDetailPage from "@/app/paper/sessions/[sessionId]/page";
import BacktestsPage from "@/app/backtests/page";
import {
  CONFIRMED_PAPER_ACTIONS,
  PAPER_ACTIONS_BY_STATUS,
} from "@/components/paper/actions";
import {
  SUPPORTED_STRATEGIES,
  validateDatasetName,
  validateMarketBar,
  validatePeriod,
} from "@/components/paper/validation";

const fetchMock = vi.fn();
const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/paper",
  useParams: () => ({ sessionId: "papersession_1", backtestId: "backtest_1" }),
  useRouter: () => ({ push: pushMock }),
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
      error: { code, message, details: {}, request_id: "req_act_err" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function pageOf<T>(items: T[]) {
  return { items, count: items.length, total: items.length, limit: 25, offset: 0 };
}

function sessionWith(status: string) {
  return {
    session_id: "papersession_1",
    user_id: "user_1",
    account_id: "account_1",
    session_name: "Morning run",
    session_type: "manual_paper_session",
    status,
    is_terminal: false,
    started_at_utc: "2026-01-01T00:00:00",
    ended_at_utc: null,
    total_trades: 0,
    net_pnl: null,
    profit_factor: null,
    profit_factor_state: "unavailable",
    status_reason: null,
    strategy_name: null,
    model_id: null,
    model_version: null,
    symbol: "XAUUSD",
    timeframe: "H1",
    initial_balance: 10000,
    final_balance: null,
    realized_pnl: null,
    max_drawdown: null,
  };
}

const DECISION = {
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
};

function routeFor(
  status: string,
  override?: (url: string, method: string) => Response | null,
) {
  return async (url: unknown, init?: unknown) => {
    const target = String(url);
    const method = ((init as RequestInit)?.method ?? "GET").toUpperCase();
    const custom = override?.(target, method);

    if (custom) {
      return custom;
    }

    if (target.includes("/result")) {
      return ok({
        session_id: "papersession_1",
        account_id: "account_1",
        has_trades: false,
        total_orders: 0,
        total_fills: 0,
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: null,
        net_pnl: null,
        gross_profit: null,
        gross_loss: null,
        profit_factor: null,
        profit_factor_state: "unavailable",
        has_infinite_profit_factor: false,
        max_drawdown: null,
        ending_balance: 10000,
        symbols_traded: [],
        decisions_allowed: 0,
        decisions_rejected: 0,
        total_decisions: 0,
        rejection_rate: null,
        top_rejection_reasons: [],
        calculated_at_utc: null,
      });
    }

    if (/\/(orders|fills|positions|trades|decisions)(\?|$)/.test(target)) {
      return ok(pageOf([]));
    }

    if (/\/paper\/sessions\/papersession_1(\?|$)/.test(target)) {
      return ok(sessionWith(status));
    }

    return ok(pageOf([]));
  };
}

function posts(): { url: string; body: Record<string, unknown> }[] {
  return fetchMock.mock.calls
    .filter((call) => (call[1] as RequestInit)?.method === "POST")
    .map((call) => ({
      url: String(call[0]),
      body: JSON.parse(String((call[1] as RequestInit).body ?? "{}")),
    }));
}

beforeEach(() => {
  fetchMock.mockReset();
  pushMock.mockReset();
  fetchMock.mockImplementation(routeFor("running"));
});

describe("the paper action surface is an allow list", () => {
  it("names only paper session commands", () => {
    expect(Object.values(PAPER_SESSION_ACTIONS).sort()).toEqual([
      "cancel",
      "complete",
      "fail",
      "pause",
      "resume",
      "start",
    ]);
  });

  it("confirms every command that stops a run", () => {
    expect([...CONFIRMED_PAPER_ACTIONS].sort()).toEqual([
      "cancel",
      "complete",
      "fail",
    ]);
  });

  it("requires a reason where the server does", () => {
    expect([...PAPER_REASON_REQUIRED].sort()).toEqual(["cancel", "fail"]);
  });

  it("treats every terminal status as final", () => {
    for (const status of ["completed", "failed", "cancelled"]) {
      expect(PAPER_ACTIONS_BY_STATUS[status]).toEqual([]);
    }
  });
});

describe("market bar validation mirrors the simulator", () => {
  const bar = {
    open: "100",
    high: "101",
    low: "99",
    close: "100",
    volume: "10",
    timestamp_utc: "2026-01-01T00:00:00",
  };

  it("accepts a real bar", () => {
    expect(validateMarketBar(bar)).toBeNull();
  });

  it("refuses a high that does not cover the close", () => {
    expect(validateMarketBar({ ...bar, high: "50" })).toMatch(/high must cover/i);
  });

  it("refuses a low above the open", () => {
    expect(validateMarketBar({ ...bar, low: "150", high: "200" })).toMatch(
      /low must sit/i,
    );
  });

  it.each(["open", "high", "low", "close"])("refuses a non-positive %s", (field) => {
    expect(validateMarketBar({ ...bar, [field]: "0" })).toBeTruthy();
  });

  it("refuses a negative volume", () => {
    expect(validateMarketBar({ ...bar, volume: "-1" })).toMatch(/volume/i);
  });

  it("requires a timestamp", () => {
    expect(validateMarketBar({ ...bar, timestamp_utc: "" })).toMatch(/timestamp/i);
  });
});

describe("a dataset is a name, never a location", () => {
  it.each([
    "../secrets",
    "/etc/passwd",
    "C:\\data\\file",
    "sub/dir",
    "data.csv",
    "https://example.com/data.csv",
    "os.system",
    "",
  ])("refuses %s", (value) => {
    expect(validateDatasetName(value)).toBeTruthy();
  });

  it("accepts a plain name", () => {
    expect(validateDatasetName("xauusd_h1")).toBeNull();
  });

  it("offers only the strategies the backend supports", () => {
    expect(SUPPORTED_STRATEGIES).toEqual(["csv_signal_strategy"]);

    for (const name of SUPPORTED_STRATEGIES) {
      expect(name).not.toContain(".");
      expect(name).not.toContain("/");
    }
  });
});

describe("a backtest period is bounded", () => {
  it("refuses a window that runs backwards", () => {
    expect(validatePeriod("2026-06-01", "2026-01-01")).toMatch(/before its start/i);
  });

  it("refuses an unbounded window", () => {
    expect(validatePeriod("1800-01-01", "2026-01-01")).toMatch(/at most/i);
  });

  it("accepts a sensible window", () => {
    expect(validatePeriod("2026-01-01", "2026-02-01")).toBeNull();
  });

  it("allows an open-ended period", () => {
    expect(validatePeriod("", "")).toBeNull();
  });
});

describe("session controls", () => {
  it("render on the detail page", async () => {
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("Run controls")).toBeInTheDocument();
  });

  it("say they reach no venue", async () => {
    render(<PaperSessionDetailPage />);

    expect(
      await screen.findByText(/start and stop a simulated run/i),
    ).toBeInTheDocument();
  });

  it("pause acts directly and calls the paper endpoint", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Pause" }));

    await waitFor(() => {
      expect(posts()[0]?.url).toContain("/api/v1/paper/sessions/papersession_1/pause");
    });
  });

  it("asks before completing a run", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Complete run" }));

    expect(screen.getByRole("dialog", { name: /confirm complete run/i })).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it("refuses to cancel without a reason", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Cancel run" }));
    await user.click(screen.getByRole("button", { name: /confirm cancel run/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Say why this run is stopping.");
    expect(posts()).toHaveLength(0);
  });

  it("sends the reason it was given", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Cancel run" }));
    await user.type(screen.getByLabelText("Why?"), "Data was wrong.");
    await user.click(screen.getByRole("button", { name: /confirm cancel run/i }));

    await waitFor(() => expect(posts()).toHaveLength(1));

    expect(posts()[0]?.url).toContain("/paper/sessions/papersession_1/cancel");
    expect(posts()[0]?.body).toEqual({ reason: "Data was wrong." });
  });

  it("disables what the status cannot do", async () => {
    fetchMock.mockImplementation(routeFor("created"));
    render(<PaperSessionDetailPage />);

    await screen.findByText("Run controls");

    expect(screen.getByRole("button", { name: "Start run" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
  });

  it("shows a refused transition with its request id", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeFor("running", (url, method) =>
        method === "POST" && url.includes("/pause")
          ? fail(409, API_ERROR_CODES.conflict, "Cannot pause.")
          : null,
      ),
    );

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Pause" }));

    expect(await screen.findByText("Cannot pause.")).toBeInTheDocument();
    expect(screen.getAllByTestId("request-id")[0]).toHaveTextContent("req_act_err");
  });

  it("leaves the status alone when the action fails", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeFor("running", (url, method) =>
        method === "POST" && url.includes("/pause")
          ? fail(409, API_ERROR_CODES.conflict)
          : null,
      ),
    );

    render(<PaperSessionDetailPage />);
    await screen.findByText("Run controls");

    await user.click(screen.getByRole("button", { name: "Pause" }));
    await screen.findByRole("alert");

    expect(screen.getAllByText("running").length).toBeGreaterThan(0);
    expect(screen.queryByText("paused")).toBeNull();
  });
});

describe("submitting a simulated order", () => {
  const fillBar = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Quantity"), "1");
    await user.type(screen.getByLabelText("Open"), "100");
    await user.type(screen.getByLabelText("High"), "101");
    await user.type(screen.getByLabelText("Low"), "99");
    await user.type(screen.getByLabelText("Close"), "100");
    await user.type(screen.getByLabelText("Bar timestamp"), "2026-01-01T00:00:00");
  };

  it("renders only while the run is going", async () => {
    render(<PaperSessionDetailPage />);

    expect(await screen.findByText("Submit a simulated order")).toBeInTheDocument();
  });

  it("is absent once the run has stopped", async () => {
    fetchMock.mockImplementation(routeFor("completed"));
    render(<PaperSessionDetailPage />);

    await screen.findByText("Run controls");

    expect(screen.queryByText("Submit a simulated order")).toBeNull();
  });

  it("refuses an impossible bar before any request", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Submit a simulated order");

    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Quantity"), "1");
    await user.type(screen.getByLabelText("Open"), "100");
    await user.type(screen.getByLabelText("High"), "50");
    await user.type(screen.getByLabelText("Low"), "99");
    await user.type(screen.getByLabelText("Close"), "100");
    await user.type(screen.getByLabelText("Bar timestamp"), "2026-01-01T00:00:00");
    await user.click(screen.getByRole("button", { name: "Review order" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/high must cover/i);
    expect(posts()).toHaveLength(0);
  });

  it("asks before submitting", async () => {
    const user = userEvent.setup();

    render(<PaperSessionDetailPage />);
    await screen.findByText("Submit a simulated order");

    await fillBar(user);
    await user.click(screen.getByRole("button", { name: "Review order" }));

    expect(
      screen.getByRole("dialog", { name: /confirm simulated order/i }),
    ).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it("posts to the paper orders endpoint with no metadata", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeFor("running", (url, method) =>
        method === "POST" && /\/orders$/.test(url)
          ? ok({
              accepted: true,
              decision: DECISION,
              order: null,
              fills: [],
              position: null,
              trade: null,
              rejection_reason: null,
              rejection_message: null,
            })
          : null,
      ),
    );

    render(<PaperSessionDetailPage />);
    await screen.findByText("Submit a simulated order");

    await fillBar(user);
    await user.click(screen.getByRole("button", { name: "Review order" }));
    await user.click(screen.getByRole("button", { name: /submit simulated order/i }));

    await waitFor(() => expect(posts()).toHaveLength(1));

    const call = posts()[0];

    expect(call?.url).toContain("/api/v1/paper/sessions/papersession_1/orders");
    expect(call?.body["symbol"]).toBe("XAUUSD");
    expect(call?.body["market"]).toMatchObject({ open: 100, high: 101, low: 99 });

    for (const forbidden of ["metadata", "extra_metadata", "user_id", "account_id", "severity"]) {
      expect(call?.body).not.toHaveProperty(forbidden);
    }
  });

  it("renders a refusal as audited rather than broken", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeFor("running", (url, method) =>
        method === "POST" && /\/orders$/.test(url)
          ? ok({
              accepted: false,
              decision: DECISION,
              order: null,
              fills: [],
              position: null,
              trade: null,
              rejection_reason: "symbol_blocked",
              rejection_message: "Symbol is blocked for this user.",
            })
          : null,
      ),
    );

    render(<PaperSessionDetailPage />);
    await screen.findByText("Submit a simulated order");

    await fillBar(user);
    await user.click(screen.getByRole("button", { name: "Review order" }));
    await user.click(screen.getByRole("button", { name: /submit simulated order/i }));

    expect(await screen.findByTestId("audited-refusal")).toBeInTheDocument();
    expect(screen.getByText("Symbol is blocked for this user.")).toBeInTheDocument();
    expect(screen.getByText(/stored with the run/i)).toBeInTheDocument();
  });

  it("refetches the whole run after an attempt", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeFor("running", (url, method) =>
        method === "POST" && /\/orders$/.test(url)
          ? ok({
              accepted: true,
              decision: DECISION,
              order: null,
              fills: [],
              position: null,
              trade: null,
              rejection_reason: null,
              rejection_message: null,
            })
          : null,
      ),
    );

    render(<PaperSessionDetailPage />);
    await screen.findByText("Submit a simulated order");

    await fillBar(user);
    await user.click(screen.getByRole("button", { name: "Review order" }));

    const before = fetchMock.mock.calls.length;

    await user.click(screen.getByRole("button", { name: /submit simulated order/i }));

    await waitFor(() => {
      const after = fetchMock.mock.calls.slice(before).map((call) => String(call[0]));

      expect(after.some((url) => url.includes("/decisions"))).toBe(true);
      expect(after.some((url) => url.includes("/result"))).toBe(true);
      expect(after.some((url) => url.includes("/trades"))).toBe(true);
    });
  });
});

describe("the backtest run form", () => {
  it("renders on the backtests page", async () => {
    render(<BacktestsPage />);

    expect(await screen.findByText("Run a historical backtest")).toBeInTheDocument();
  });

  it("says the run replays stored history", async () => {
    render(<BacktestsPage />);

    expect(await screen.findByText(/replays stored history/i)).toBeInTheDocument();
  });

  it("offers a strategy list, not a text field", async () => {
    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    const select = screen.getByLabelText("Strategy") as HTMLSelectElement;

    expect(select.tagName).toBe("SELECT");
    expect([...select.options].map((option) => option.value)).toEqual([
      "csv_signal_strategy",
    ]);
  });

  it("refuses a path as a dataset", async () => {
    const user = userEvent.setup();

    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    await user.type(screen.getByLabelText("Dataset"), "../secrets");
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Timeframe"), "H1");
    await user.click(screen.getByRole("button", { name: "Review run" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/named, not located/i);
    expect(posts()).toHaveLength(0);
  });

  it("refuses a URL as a dataset", async () => {
    const user = userEvent.setup();

    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    await user.type(screen.getByLabelText("Dataset"), "https://example.com/x.csv");
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Timeframe"), "H1");
    await user.click(screen.getByRole("button", { name: "Review run" }));

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });

  it("refuses a backwards period", async () => {
    const user = userEvent.setup();

    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    await user.type(screen.getByLabelText("Dataset"), "xauusd_h1");
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Timeframe"), "H1");
    await user.type(screen.getByLabelText("Period start"), "2026-06-01");
    await user.type(screen.getByLabelText("Period end"), "2026-01-01");
    await user.click(screen.getByRole("button", { name: "Review run" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/before its start/i);
    expect(posts()).toHaveLength(0);
  });

  it("posts to the backtests endpoint and navigates to the run", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (_url: unknown, init: unknown) => {
      if ((init as RequestInit)?.method === "POST") {
        return ok({
          backtest: {
            backtest_id: "backtest_new",
            status: "completed",
            strategy_name: "csv_signal_strategy",
            dataset: "xauusd_h1",
            symbol: "XAUUSD",
            timeframe: "H1",
            metrics: {},
            profit_factor_state: "unavailable",
            failure_reason: null,
          },
        });
      }

      return ok(pageOf([]));
    });

    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    await user.type(screen.getByLabelText("Dataset"), "xauusd_h1");
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Timeframe"), "H1");
    await user.click(screen.getByRole("button", { name: "Review run" }));
    await user.click(screen.getByRole("button", { name: "Run backtest" }));

    await waitFor(() => {
      expect(posts()[0]?.url).toMatch(/\/api\/v1\/backtests$/);
      expect(pushMock).toHaveBeenCalledWith("/backtests/backtest_new");
    });
  });

  it("shows an unconfigured deployment as not ready", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async (_url: unknown, init: unknown) =>
      (init as RequestInit)?.method === "POST"
        ? fail(503, API_ERROR_CODES.notReady, "No dataset directory is configured.")
        : ok(pageOf([])),
    );

    render(<BacktestsPage />);
    await screen.findByText("Run a historical backtest");

    await user.type(screen.getByLabelText("Dataset"), "xauusd_h1");
    await user.type(screen.getByLabelText("Symbol"), "XAUUSD");
    await user.type(screen.getByLabelText("Timeframe"), "H1");
    await user.click(screen.getByRole("button", { name: "Review run" }));
    await user.click(screen.getByRole("button", { name: "Run backtest" }));

    expect(await screen.findByTestId("not-ready")).toBeInTheDocument();
    expect(screen.getAllByTestId("request-id")[0]).toHaveTextContent("req_act_err");
  });

  it("never claims a run is queued", async () => {
    const { container } = render(<BacktestsPage />);

    await screen.findByText("Run a historical backtest");

    expect(container.textContent).not.toContain("queued");
    expect(container.textContent).not.toContain("Queued");
  });
});

describe("the action client stays inside its endpoints", () => {
  const client = () =>
    new AqosApiClient({
      baseUrl: "http://localhost:8000",
      getToken: () => "tok",
      fetchImpl: (...args: unknown[]) => fetchMock(...args),
    });

  it("posts every paper action under /paper", async () => {
    fetchMock.mockImplementation(async () => ok({}));

    await paperActions.createSession(client(), {
      account_id: "a",
      session_name: "n",
      session_type: "manual_paper_session",
    });
    await paperActions.command(client(), "s1", "start");
    await paperActions.submitOrder(client(), "s1", {
      symbol: "X",
      action: "buy",
      order_type: "market",
      quantity: 1,
      market: {
        symbol: "X",
        timestamp_utc: "2026-01-01T00:00:00",
        open: 1,
        high: 2,
        low: 1,
        close: 1,
      },
    });
    await paperActions.cancelOrder(client(), "s1", "o1");
    await paperActions.closePosition(client(), "s1", "p1", 110);

    for (const call of fetchMock.mock.calls) {
      expect(String(call[0])).toContain("/api/v1/paper");
      expect((call[1] as RequestInit).method).toBe("POST");
      expect(
        ((call[1] as RequestInit).headers as Record<string, string>)["Authorization"],
      ).toBe("Bearer tok");
    }
  });

  it("posts a backtest run to exactly /api/v1/backtests", async () => {
    fetchMock.mockImplementation(async () => ok({}));

    await backtestActions.run(client(), {
      strategy_name: "csv_signal_strategy",
      dataset: "xauusd_h1",
      symbol: "X",
      timeframe: "H1",
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/api\/v1\/backtests$/);
  });

  it("sends no initial_balance when creating a session", async () => {
    // The balance comes from the account. Stating one would let a run start
    // from a figure the account never had.
    fetchMock.mockImplementation(async () => ok({}));

    await paperActions.createSession(client(), {
      account_id: "a",
      session_name: "n",
      session_type: "manual_paper_session",
    });

    const body = JSON.parse(
      String((fetchMock.mock.calls[0]?.[1] as RequestInit).body ?? "{}"),
    );

    expect(body).not.toHaveProperty("initial_balance");
    expect(body).not.toHaveProperty("user_id");
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

    await expect(
      paperActions.command(client(), "s1", "start"),
    ).rejects.toMatchObject({ status, code, requestId: "req_act_err" });
  });
});
