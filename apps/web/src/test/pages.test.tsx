import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import DashboardPage from "@/app/dashboard/page";
import HomePage from "@/app/page";
import LoginPage from "@/app/login/page";
import NotFoundPage from "@/app/not-found";
import { AppShell, NAV_ITEMS } from "@/components/layout/AppShell";
import { ErrorMessage } from "@/components/states";
import { AqosApiError } from "@/api/errors";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

describe("the shell renders", () => {
  it("shows the app name and every navigation target", () => {
    render(
      <AppShell appName="AQOS">
        <p>content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "AQOS" })).toBeInTheDocument();

    for (const item of NAV_ITEMS) {
      expect(screen.getByRole("link", { name: item.label })).toBeInTheDocument();
    }
  });

  it("marks the current page for assistive technology", () => {
    render(
      <AppShell appName="AQOS">
        <p>content</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});

describe("every route placeholder renders", () => {
  const pages = [
    { name: "Home", Component: HomePage, heading: "AQOS" },
    { name: "Dashboard", Component: DashboardPage, heading: "Dashboard" },
    { name: "Not found", Component: NotFoundPage, heading: "Page not found" },
  ];

  it.each(pages)("$name", ({ Component, heading }) => {
    render(<Component />);

    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });

  it("says a placeholder is unbuilt rather than showing an empty list", () => {
    // "Nothing here yet" and "you have nothing" are different claims, and
    // only one of them is true. Signals, accounts, paper and backtests are all
    // real screens now; the dashboard is the last placeholder.
    render(<DashboardPage />);

    expect(screen.getByText("Not built yet")).toBeInTheDocument();
  });

  it("renders the login form", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("offers no sign-up or password reset", () => {
    // Neither endpoint exists, so offering either would be a dead end.
    render(<LoginPage />);

    expect(screen.queryByText(/sign up/i)).toBeNull();
    expect(screen.queryByText(/forgot/i)).toBeNull();
    expect(screen.queryByText(/reset/i)).toBeNull();
  });
});

describe("an API failure is shown honestly", () => {
  it("shows the code, the message and the request id", () => {
    render(
      <ErrorMessage
        error={
          new AqosApiError({
            code: "forbidden",
            message: "You can only read your own data.",
            status: 403,
            requestId: "req_abc123",
          })
        }
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("forbidden")).toBeInTheDocument();
    expect(screen.getByText("You can only read your own data.")).toBeInTheDocument();
    expect(screen.getByTestId("request-id")).toHaveTextContent("req_abc123");
  });

  it("shows the retry delay when the server gave one", () => {
    render(
      <ErrorMessage
        error={
          new AqosApiError({
            code: "rate_limited",
            message: "Too many requests.",
            status: 429,
            details: { retry_after_seconds: 42 },
            requestId: "req_1",
          })
        }
      />,
    );

    expect(screen.getByText("Retry in 42s")).toBeInTheDocument();
  });

  it("omits the reference when there is none rather than showing a blank", () => {
    render(
      <ErrorMessage
        error={new AqosApiError({ code: "network_error", message: "Offline.", status: 0 })}
      />,
    );

    expect(screen.queryByTestId("request-id")).toBeNull();
  });
});
