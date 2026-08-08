import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { API_ERROR_CODES } from "@/api/errors";
import { AqosApiClient } from "@/api/client";
import { SIGNAL_ACTIONS, signalActions } from "@/api/resources";
import SignalDetailPage from "@/app/signals/[signalId]/page";
import {
  ACTIONS_BY_STATUS,
  CONFIRMED_ACTIONS,
  MISS_REASON_CODES,
  REJECT_REASON_CODES,
} from "@/components/signals/SignalActionPanel";
import type { SignalDetail } from "@/api/types";

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
    headers: { "Content-Type": "application/json", "X-Request-ID": "req_ok" },
  });
}

function fail(status: number, code: string, message = "Refused."): Response {
  return new Response(
    JSON.stringify({
      error: { code, message, details: {}, request_id: "req_action_err" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function pageOf<T>(items: T[]) {
  return { items, count: items.length, total: items.length, limit: 25, offset: 0 };
}

function signalWith(status: string): SignalDetail {
  return {
    signal_id: "signal_1",
    user_id: "user_1",
    account_id: "account_1",
    symbol: "XAUUSD",
    timeframe: "H1",
    action: "buy",
    source: "ml_model",
    status,
    confidence: 0.8,
    generated_at_utc: "2026-01-01T00:00:00",
    expires_at_utc: null,
    entry_price: null,
    stop_loss: null,
    take_profit: null,
    strategy_name: null,
    model_id: null,
    model_version: null,
    status_reason: null,
    is_open: true,
    created_at_utc: "2026-01-01T00:00:00",
    updated_at_utc: "2026-01-01T00:00:00",
  };
}

/** Routes every detail-page fetch, with the signal in a chosen status. */
function routeWith(status: string, override?: (url: string) => Response | null) {
  return async (url: unknown) => {
    const target = String(url);
    const custom = override?.(target);

    if (custom) {
      return custom;
    }

    if (target.includes("/events")) {
      return ok(pageOf([]));
    }

    if (target.includes("/reasons")) {
      return ok(pageOf([]));
    }

    return ok(signalWith(status));
  };
}

function postCalls(): { url: string; body: Record<string, unknown> }[] {
  return fetchMock.mock.calls
    .filter((call) => (call[1] as RequestInit)?.method === "POST")
    .map((call) => ({
      url: String(call[0]),
      body: JSON.parse(String((call[1] as RequestInit).body ?? "{}")),
    }));
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation(routeWith("generated"));
});

describe("the action surface is an allow list", () => {
  it("names only signal lifecycle actions", () => {
    expect(Object.values(SIGNAL_ACTIONS).sort()).toEqual([
      "approve",
      "cancel",
      "expire",
      "mark-pending-approval",
      "miss",
      "reject",
    ]);
  });

  it("offers no execution outcome", () => {
    // `executed` and `failed` describe what a broker did. Nothing here talks
    // to one.
    const values = Object.values(SIGNAL_ACTIONS) as string[];

    expect(values).not.toContain("execute");
    expect(values).not.toContain("executed");
    expect(values).not.toContain("failed");
  });

  it("treats every terminal status as final", () => {
    for (const status of ["rejected", "missed", "expired", "executed", "failed", "cancelled"]) {
      expect(ACTIONS_BY_STATUS[status]).toEqual([]);
    }
  });

  it("confirms every action that ends a signal", () => {
    expect([...CONFIRMED_ACTIONS].sort()).toEqual([
      "cancel",
      "expire",
      "miss",
      "reject",
    ]);
  });

  it("uses only real taxonomy codes", () => {
    // Codes are validated server-side against the target status; inventing one
    // here would produce a 422 a user could do nothing about.
    for (const code of [...REJECT_REASON_CODES, ...MISS_REASON_CODES]) {
      expect(code).toMatch(/^[a-z][a-z_]+$/);
    }

    expect(REJECT_REASON_CODES).toContain("manual_rejection");
    expect(MISS_REASON_CODES).toContain("approval_timeout");
  });
});

describe("the action panel", () => {
  it("renders on the signal detail page", async () => {
    render(<SignalDetailPage />);

    expect(await screen.findByText("Lifecycle actions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("says these actions reach no broker", async () => {
    render(<SignalDetailPage />);

    expect(
      await screen.findByText(/place no order and reach\s+no broker/i),
    ).toBeInTheDocument();
  });

  it("disables what the current status cannot do", async () => {
    fetchMock.mockImplementation(routeWith("approved"));
    render(<SignalDetailPage />);

    await screen.findByText("Lifecycle actions");

    // An approved signal cannot be approved again.
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel signal" })).toBeEnabled();
  });

  it("says a finished signal cannot move", async () => {
    fetchMock.mockImplementation(routeWith("rejected"));
    render(<SignalDetailPage />);

    expect(
      await screen.findByText(/is rejected, which is final/i),
    ).toBeInTheDocument();
  });
});

describe("approve and send-for-approval act directly", () => {
  it("approve posts to the approve endpoint", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(postCalls()[0]?.url).toContain("/api/v1/signals/signal_1/approve");
    });
  });

  it("send-for-approval posts to mark-pending-approval", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await waitFor(() => {
      expect(postCalls()[0]?.url).toContain(
        "/api/v1/signals/signal_1/mark-pending-approval",
      );
    });
  });
});

describe("refusing a signal needs a reason", () => {
  it("asks before rejecting", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(screen.getByRole("dialog", { name: /confirm reject/i })).toBeInTheDocument();
    expect(postCalls()).toHaveLength(0);
  });

  it("refuses to send without a reason code", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.click(screen.getByRole("button", { name: /confirm reject/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a reason code.");
    expect(postCalls()).toHaveLength(0);
  });

  it("sends the reason code and nothing else", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.selectOptions(screen.getByLabelText("Reason code"), "manual_rejection");
    await user.click(screen.getByRole("button", { name: /confirm reject/i }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));

    const call = postCalls()[0];

    expect(call?.url).toContain("/api/v1/signals/signal_1/reject");
    expect(call?.body).toEqual({ reason_code: "manual_rejection" });
  });

  it("sends no category, severity or metadata", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.selectOptions(screen.getByLabelText("Reason code"), "spread_too_high");
    await user.click(screen.getByRole("button", { name: /confirm reject/i }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));

    const body = postCalls()[0]?.body ?? {};

    for (const forbidden of ["severity", "reason_category", "category", "metadata"]) {
      expect(body).not.toHaveProperty(forbidden);
    }
  });

  it("offers no control for category or severity", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Reject" }));

    expect(screen.queryByLabelText(/severity/i)).toBeNull();
    expect(screen.queryByLabelText(/category/i)).toBeNull();
    expect(
      screen.getByText(/decided by the reason code on the\s+server/i),
    ).toBeInTheDocument();
  });

  it("requires a reason code for a miss too", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Mark missed" }));
    await user.click(screen.getByRole("button", { name: /confirm mark missed/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a reason code.");
    expect(postCalls()).toHaveLength(0);
  });

  it("sends a miss with its reason code only", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Mark missed" }));
    await user.selectOptions(screen.getByLabelText("Reason code"), "approval_timeout");
    await user.click(screen.getByRole("button", { name: /confirm mark missed/i }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));

    expect(postCalls()[0]?.url).toContain("/api/v1/signals/signal_1/miss");
    expect(postCalls()[0]?.body).toEqual({ reason_code: "approval_timeout" });
  });
});

describe("cancelling needs a note", () => {
  it("refuses to send an empty note", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Cancel signal" }));
    await user.click(screen.getByRole("button", { name: /confirm cancel signal/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Say why this signal is being cancelled.",
    );
    expect(postCalls()).toHaveLength(0);
  });

  it("sends the note and nothing else", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Cancel signal" }));
    await user.type(screen.getByLabelText("Why?"), "  Data was wrong.  ");
    await user.click(screen.getByRole("button", { name: /confirm cancel signal/i }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));

    expect(postCalls()[0]?.url).toContain("/api/v1/signals/signal_1/cancel");
    expect(postCalls()[0]?.body).toEqual({ note: "Data was wrong." });
  });
});

describe("expiring explains itself", () => {
  it("says expiry only works once the time has passed", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Expire" }));

    expect(
      screen.getByText(/expiry time has actually\s+passed/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/cancel it instead/i)).toBeInTheDocument();
  });

  it("shows a refused transition with its request id", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeWith("generated", (url) =>
        url.includes("/expire")
          ? fail(409, API_ERROR_CODES.conflict, "This signal is not due to expire.")
          : null,
      ),
    );

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Expire" }));
    await user.click(screen.getByRole("button", { name: /confirm expire/i }));

    expect(
      await screen.findByText("This signal is not due to expire."),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("request-id")[0]).toHaveTextContent(
      "req_action_err",
    );
    expect(screen.getByText(/server refused this transition/i)).toBeInTheDocument();
  });
});

describe("the screen never gets ahead of the server", () => {
  it("leaves the status alone when the action fails", async () => {
    const user = userEvent.setup();

    fetchMock.mockImplementation(
      routeWith("generated", (url) =>
        url.includes("/approve") ? fail(409, API_ERROR_CODES.conflict) : null,
      ),
    );

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await screen.findByRole("alert");

    // Still generated: nothing moved, so nothing on screen moved.
    expect(screen.getByText("generated")).toBeInTheDocument();
    expect(screen.queryByText("approved")).toBeNull();
  });

  it("refetches all three panels after a success", async () => {
    const user = userEvent.setup();

    render(<SignalDetailPage />);
    await screen.findByText("Lifecycle actions");

    const before = fetchMock.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      const after = fetchMock.mock.calls
        .slice(before)
        .map((call) => String(call[0]));

      expect(after.some((url) => /\/signals\/signal_1$/.test(url))).toBe(true);
      expect(after.some((url) => url.includes("/events"))).toBe(true);
      expect(after.some((url) => url.includes("/reasons"))).toBe(true);
    });
  });
});

describe("the action client handles every refusal", () => {
  const client = () =>
    new AqosApiClient({
      baseUrl: "http://localhost:8000",
      getToken: () => "tok",
      fetchImpl: (...args: unknown[]) => fetchMock(...args),
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
      signalActions.approve(client(), "signal_1"),
    ).rejects.toMatchObject({ status, code, requestId: "req_action_err" });
  });

  it("posts every action to its own signal endpoint", async () => {
    fetchMock.mockImplementation(async () => ok({}));

    await signalActions.approve(client(), "signal_1");
    await signalActions.reject(client(), "signal_1", "manual_rejection");
    await signalActions.miss(client(), "signal_1", "approval_timeout");
    await signalActions.expire(client(), "signal_1");
    await signalActions.cancel(client(), "signal_1", "note");
    await signalActions.markPendingApproval(client(), "signal_1");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    for (const url of urls) {
      expect(url).toMatch(
        /\/api\/v1\/signals\/signal_1\/(approve|reject|miss|expire|cancel|mark-pending-approval)$/,
      );
    }

    for (const call of fetchMock.mock.calls) {
      expect((call[1] as RequestInit).method).toBe("POST");
      expect(
        ((call[1] as RequestInit).headers as Record<string, string>)[
          "Authorization"
        ],
      ).toBe("Bearer tok");
    }
  });

  it("sends no metadata on any action", async () => {
    fetchMock.mockImplementation(async () => ok({}));

    await signalActions.reject(client(), "signal_1", "manual_rejection");
    await signalActions.miss(client(), "signal_1", "approval_timeout");
    await signalActions.cancel(client(), "signal_1", "note");

    for (const call of fetchMock.mock.calls) {
      const body = JSON.parse(String((call[1] as RequestInit).body ?? "{}"));

      for (const forbidden of ["metadata", "extra_metadata", "severity", "reason_category"]) {
        expect(body).not.toHaveProperty(forbidden);
      }
    }
  });
});
