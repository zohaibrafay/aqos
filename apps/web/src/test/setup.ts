import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";

import { resetApiClientForTests } from "@/lib/api";
import { resetSessionForTests } from "@/lib/session";

/** The public configuration every test runs against. */
process.env["NEXT_PUBLIC_AQOS_WEB_API_BASE_URL"] = "http://localhost:8000";
process.env["NEXT_PUBLIC_AQOS_WEB_APP_NAME"] = "AQOS";
process.env["NEXT_PUBLIC_AQOS_WEB_ENV"] = "test";

beforeEach(() => {
  resetSessionForTests();
  resetApiClientForTests();
});

afterEach(() => {
  cleanup();
  resetSessionForTests();
  resetApiClientForTests();
});
