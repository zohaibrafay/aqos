import { describe, expect, it } from "vitest";

import {
  AqosWebConfigError,
  assertNoUnsafePublicNames,
  isUnsafeConfigName,
  loadAqosWebConfig,
  normalizeApiBaseUrl,
} from "@/config/env";

function env(overrides: Record<string, string | undefined> = {}) {
  return {
    NEXT_PUBLIC_AQOS_WEB_API_BASE_URL: "https://api.example.com",
    NEXT_PUBLIC_AQOS_WEB_APP_NAME: "AQOS",
    NEXT_PUBLIC_AQOS_WEB_ENV: "production",
    ...overrides,
  };
}

describe("public configuration", () => {
  it("loads a valid configuration", () => {
    const config = loadAqosWebConfig(env());

    expect(config.apiBaseUrl).toBe("https://api.example.com");
    expect(config.environment).toBe("production");
  });

  it("requires the API base URL", () => {
    expect(() =>
      loadAqosWebConfig(env({ NEXT_PUBLIC_AQOS_WEB_API_BASE_URL: "" })),
    ).toThrow(AqosWebConfigError);
  });

  it("requires the environment", () => {
    expect(() => loadAqosWebConfig(env({ NEXT_PUBLIC_AQOS_WEB_ENV: "" }))).toThrow(
      AqosWebConfigError,
    );
  });

  it("refuses an unknown environment", () => {
    expect(() => loadAqosWebConfig(env({ NEXT_PUBLIC_AQOS_WEB_ENV: "prod" }))).toThrow(
      AqosWebConfigError,
    );
  });

  it.each(["", "not a url", "/api/v1", "api.example.com", "ftp://x.example.com"])(
    "refuses %s as a base URL",
    (value) => {
      expect(() => normalizeApiBaseUrl(value)).toThrow(AqosWebConfigError);
    },
  );

  it("strips a trailing slash so paths never double up", () => {
    expect(normalizeApiBaseUrl("https://api.example.com/")).toBe(
      "https://api.example.com",
    );
  });

  it("refuses a deployed build pointed at localhost", () => {
    expect(() =>
      loadAqosWebConfig(
        env({ NEXT_PUBLIC_AQOS_WEB_API_BASE_URL: "http://localhost:8000" }),
      ),
    ).toThrow(AqosWebConfigError);
  });

  it("refuses a staging build pointed at localhost too", () => {
    expect(() =>
      loadAqosWebConfig(
        env({
          NEXT_PUBLIC_AQOS_WEB_API_BASE_URL: "http://127.0.0.1:8000",
          NEXT_PUBLIC_AQOS_WEB_ENV: "staging",
        }),
      ),
    ).toThrow(AqosWebConfigError);
  });

  it("allows localhost locally", () => {
    const config = loadAqosWebConfig(
      env({
        NEXT_PUBLIC_AQOS_WEB_API_BASE_URL: "http://localhost:8000",
        NEXT_PUBLIC_AQOS_WEB_ENV: "development",
      }),
    );

    expect(config.apiBaseUrl).toBe("http://localhost:8000");
  });
});

describe("no secret reaches the browser", () => {
  it.each([
    "NEXT_PUBLIC_DB_PASSWORD",
    "NEXT_PUBLIC_API_SECRET",
    "NEXT_PUBLIC_AQOS_TOKEN",
    "NEXT_PUBLIC_DATABASE_URL",
    "NEXT_PUBLIC_PRIVATE_KEY",
    "NEXT_PUBLIC_AWS_ACCESS_KEY",
  ])("rejects %s", (name) => {
    expect(isUnsafeConfigName(name)).toBe(true);
    expect(() => assertNoUnsafePublicNames(env({ [name]: "value" }))).toThrow(
      AqosWebConfigError,
    );
  });

  it("allows the safe public names", () => {
    for (const name of Object.keys(env())) {
      expect(isUnsafeConfigName(name)).toBe(false);
    }

    expect(() => assertNoUnsafePublicNames(env())).not.toThrow();
  });

  it("ignores server-only variables", () => {
    expect(() =>
      assertNoUnsafePublicNames({ ...env(), AQOS_DB_URL: "server-only-value" }),
    ).not.toThrow();
  });

  it("carries only the three public values", () => {
    const config = loadAqosWebConfig(env());

    expect(Object.keys(config).sort()).toEqual([
      "apiBaseUrl",
      "appName",
      "environment",
    ]);
    expect(JSON.stringify(config)).not.toContain("password");
  });
});
