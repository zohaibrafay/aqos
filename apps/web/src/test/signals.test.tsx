import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { API_ERROR_CODES } from "@/api/errors";
import { AqosApiClient } from "@/api/client";
import { models, predictions, signals } from "@/api/resources";
import SignalsPage from "@/app/signals/page";
import SignalDetailPage from "@/app/signals/[signalId]/page";
import {
  PromotionStatusBadge,
  SignalEventsTimeline,
  SignalReasonsPanel,
  formatConfidence,
  formatTimestamp,
} from "@/components/signals";
import {
  EMPTY_FILTERS,
  buildSignalQuery,
} from "@/components/signals/SignalFilters";
import type { PromotionStatus, SignalReason, SignalEvent } from "@/api/types";

const fetchMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/signals",
  useParams: () => ({ signalId: "signal_1" }),
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
    headers: { "Content-Type": "application/json", "X-Request-ID": "req_page" },
  });
}

function fail(status: number, code: string, message = "Refused."): Response {
  return new Response(
    JSON.stringify({
      error: { code, message, details: {}, request_id: "req_fail_123" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function page<T>(items: T[], total = items.length) {
  return { items, count: items.length, total, limit: 25, offset: 0 };
}

const SIGNAL = {
  signal_id: "signal_1",
  user_id: "user_1",
  account_id: "account_1",
  symbol: "XAUUSD",
  timeframe: "H1",
  action: "buy",
  source: "ml_model",
  status: "approved",
  confidence: 0.82,
  generated_at_utc: "2026-01-01T00:00:00",
  expires_at_utc: null,
  entry_price: 100,
  stop_loss: null,
  take_profit: null,
  strategy_name: "Breakout",
  model_id: "model_1",
  model_version: "1.0",
  status_reason: null,
  is_open: true,
  created_at_utc: "2026-01-01T00:00:00",
  updated_at_utc: "2026-01-01T00:01:00",
};

function routeFor(url: string): Response {
  if (url.includes("/promotion-status")) {
    return ok({
      model_id: "model_1",
      state: "unknown",
      is_promoted: false,
      reason: "No promotion record exists for this model.",
      latest_promotion: null,
      promotion_count: 0,
    });
  }

  if (url.includes("/events")) {
    return ok(
      page<SignalEvent>([
        {
          event_id: "event_1",
          signal_id: "signal_1",
          from_status: null,
          to_status: "generated",
          occurred_at_utc: "2026-01-01T00:00:00",
          reason: "Signal created.",
          actor: null,
        },
      ]),
    );
  }

  if (url.includes("/reasons")) {
    return ok(page<SignalReason>([]));
  }

  if (/\/signals\/signal_1(\?|$)/.test(url)) {
    return ok(SIGNAL);
  }

  return ok(page([SIGNAL]));
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: string) => routeFor(String(url)));
});

describe("query building", () => {
  it("sends only the filters a caller actually set", () => {
    const query = buildSignalQuery(
      { ...EMPTY_FILTERS, symbol: " XAUUSD ", status: "approved" },
      25,
      0,
    );

    expect(query).toEqual({
      limit: 25,
      offset: 0,
      symbol: "XAUUSD",
      status: "approved",
    });
  });

  it("never sends a blank filter", () => {
    // Blank means "no opinion", not "match the empty string".
    expect(buildSignalQuery(EMPTY_FILTERS, 25, 50)).toEqual({
      limit: 25,
      offset: 50,
    });
  });

  it("carries no user_id", () => {
    const query = buildSignalQuery(EMPTY_FILTERS, 25, 0) as Record<string, unknown>;

    expect(query["user_id"]).toBeUndefined();
  });
});

describe("formatting", () => {
  it("renders a missing timestamp as a dash, never as an epoch", () => {
    expect(formatTimestamp(null)).toBe("—");
    expect(formatTimestamp(undefined)).toBe("—");
  });

  it("shows what the server sent when a timestamp is unparseable", () => {
    expect(formatTimestamp("not-a-date")).toBe("not-a-date");
  });

  it("renders a missing confidence as a dash, never as zero", () => {
    // 0% would be a measurement. Absent is not a measurement.
    expect(formatConfidence(null)).toBe("—");
    expect(formatConfidence(0)).toBe("0.0%");
  });
});

describe("the signals page", () => {
  it("renders the list it fetched", async () => {
    render(<SignalsPage />);

    expect(await screen.findByText("XAUUSD")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /signal_1/ })).toBeInTheDocument();
  });

  it("shows a loading state first", () => {
    render(<SignalsPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading signals…");
  });

  it("shows an empty state rather than a bare table", async () => {
    fetchMock.mockImplementation(async () => ok(page([])));
    render(<SignalsPage />);

    expect(await screen.findByText("No signals match")).toBeInTheDocument();
  });

  it("shows an API failure with its request id", async () => {
    fetchMock.mockImplementation(async () =>
      fail(503, API_ERROR_CODES.databaseUnavailable, "Database unavailable."),
    );
    render(<SignalsPage />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByTestId("request-id")).toHaveTextContent("req_fail_123");
  });

  it("offers a retry only when the failure was temporary", async () => {
    fetchMock.mockImplementation(async () => fail(429, API_ERROR_CODES.rateLimited));
    render(<SignalsPage />);

    expect(
      await screen.findByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });

  it("offers no retry on a refusal that will not change", async () => {
    fetchMock.mockImplementation(async () => fail(403, API_ERROR_CODES.forbidden));
    render(<SignalsPage />);

    await screen.findByRole("alert");

    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("sends the filters a caller applied", async () => {
    const user = userEvent.setup();

    render(<SignalsPage />);
    await screen.findByText("XAUUSD");

    await user.type(screen.getByLabelText("Symbol"), "EURUSD");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("symbol=EURUSD"))).toBe(true);
    });
  });

  it("pages forward and back", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(async () => ok(page([SIGNAL], 100)));
    render(<SignalsPage />);
    await screen.findByText("XAUUSD");

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call) => String(call[0]));

      expect(urls.some((url) => url.includes("offset=25"))).toBe(true);
    });
  });

  it("disables Previous on the first page", async () => {
    render(<SignalsPage />);
    await screen.findByText("XAUUSD");

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("offers no user_id filter", async () => {
    // The backend scopes by caller; a control here could only ask for
    // somebody else's data.
    render(<SignalsPage />);
    await screen.findByText("XAUUSD");

    expect(screen.queryByLabelText(/user/i)).toBeNull();
  });
});

describe("the signal detail page", () => {
  it("renders the safe fields", async () => {
    render(<SignalDetailPage />);

    expect(await screen.findByText("Breakout")).toBeInTheDocument();
    // Shown in the detail card and again beside the promotion badge.
    expect(screen.getAllByText("model_1").length).toBeGreaterThan(0);
    expect(screen.getByText("82.0%")).toBeInTheDocument();
  });

  it("renders no internal or ORM field", async () => {
    render(<SignalDetailPage />);
    await screen.findByText("Breakout");

    for (const forbidden of ["extra_metadata", "_sa_instance_state", "user_id"]) {
      expect(screen.queryByText(forbidden)).toBeNull();
    }
  });

  it("shows the lifecycle trail", async () => {
    render(<SignalDetailPage />);

    expect(await screen.findByText("Signal created.")).toBeInTheDocument();
  });

  it("shows an explicit empty state for reasons", async () => {
    render(<SignalDetailPage />);

    expect(await screen.findByText("No structured reasons")).toBeInTheDocument();
  });

  it("shows a not-found signal as an error with its reference", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      String(url).includes("/events") || String(url).includes("/reasons")
        ? ok(page([]))
        : fail(404, API_ERROR_CODES.notFound, "Signal was not found."),
    );
    render(<SignalDetailPage />);

    expect(await screen.findByText("Signal was not found.")).toBeInTheDocument();
    expect(screen.getAllByTestId("request-id")[0]).toHaveTextContent("req_fail_123");
  });

  it("never offers a trading action", async () => {
    render(<SignalDetailPage />);
    await screen.findByText("Breakout");

    for (const label of [
      /execute/i,
      /place order/i,
      /submit order/i,
      /approve/i,
      /reject/i,
      /cancel/i,
    ]) {
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
  });
});

describe("promotion is never overstated", () => {
  const build = (state: PromotionStatus["state"]): PromotionStatus => ({
    model_id: "model_1",
    state,
    is_promoted: state === "promoted",
    reason: null,
    latest_promotion: null,
    promotion_count: 0,
  });

  it("shows promoted as promoted", () => {
    render(<PromotionStatusBadge status={build("promoted")} />);

    expect(screen.getByText("promoted")).toBeInTheDocument();
  });

  it("shows unknown as unknown, not as not-promoted", () => {
    // "Nobody has reviewed this" is not the same as a rejection.
    render(<PromotionStatusBadge status={build("unknown")} />);

    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.queryByText("not promoted")).toBeNull();
  });

  it("shows not-promoted as not-promoted", () => {
    render(<PromotionStatusBadge status={build("not_promoted")} />);

    expect(screen.getByText("not promoted")).toBeInTheDocument();
  });

  it("warns when a signal's model is not confirmed promoted", async () => {
    render(<SignalDetailPage />);

    expect(
      await screen.findByText(/not evidence a model is ready for production/i),
    ).toBeInTheDocument();
  });
});

describe("read-only panels", () => {
  it("renders reasons with the taxonomy fields the server resolved", () => {
    render(
      <SignalReasonsPanel
        reasons={[
          {
            reason_id: "r1",
            signal_id: "signal_1",
            signal_status: "rejected",
            reason_code: "spread_too_high",
            reason_category: "market_condition",
            severity: "warning",
            message: "Spread was 4x normal.",
            source: "gate",
            created_at_utc: "2026-01-01T00:00:00",
          },
        ]}
      />,
    );

    expect(screen.getByText("spread_too_high")).toBeInTheDocument();
    expect(screen.getByText("market_condition")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
  });

  it("offers no control to change a category or severity", () => {
    // The code alone decides both, on the server.
    const { container } = render(
      <SignalReasonsPanel
        reasons={[
          {
            reason_id: "r1",
            signal_id: "signal_1",
            signal_status: "rejected",
            reason_code: "spread_too_high",
            reason_category: "market_condition",
            severity: "warning",
            message: "Spread was 4x normal.",
            source: null,
            created_at_utc: null,
          },
        ]}
      />,
    );

    expect(container.querySelectorAll("select")).toHaveLength(0);
    expect(container.querySelectorAll("input")).toHaveLength(0);
  });

  it("says nothing has happened rather than showing a blank timeline", () => {
    render(<SignalEventsTimeline events={[]} />);

    expect(screen.getByText("No lifecycle events")).toBeInTheDocument();
  });
});

describe("the API client covers every signal endpoint", () => {
  const client = () =>
    new AqosApiClient({
      baseUrl: "http://localhost:8000",
      getToken: () => "tok",
      fetchImpl: (...args: unknown[]) => fetchMock(...args),
    });

  it("requests each path exactly once", async () => {
    await signals.list(client());
    await signals.get(client(), "signal_1");
    await signals.events(client(), "signal_1");
    await signals.reasons(client(), "signal_1");
    await predictions.list(client());
    await models.listPromotions(client());
    await models.promotionStatus(client(), "model_1");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(urls[0]).toContain("/api/v1/signals");
    expect(urls[1]).toContain("/api/v1/signals/signal_1");
    expect(urls[2]).toContain("/api/v1/signals/signal_1/events");
    expect(urls[3]).toContain("/api/v1/signals/signal_1/reasons");
    expect(urls[4]).toContain("/api/v1/predictions");
    expect(urls[5]).toContain("/api/v1/models/promotions");
    expect(urls[6]).toContain("/api/v1/models/model_1/promotion-status");
  });

  it("sends the bearer token on every one", async () => {
    await signals.list(client());
    await signals.events(client(), "signal_1");

    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit;
      const headers = (init.headers ?? {}) as Record<string, string>;

      expect(headers["Authorization"]).toBe("Bearer tok");
    }
  });

  it("issues no write request", async () => {
    await signals.list(client());
    await signals.get(client(), "signal_1");
    await signals.events(client(), "signal_1");
    await signals.reasons(client(), "signal_1");

    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit).method).toBe("GET");
    }
  });
});
