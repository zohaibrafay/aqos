import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Structural guards over the frontend source.
 *
 * The backend has boundaries enforced by AST guards; this is the same idea on
 * this side of the wire. A browser bundle is public, so anything that finds
 * its way in here is readable by everyone — which makes "nobody would do that"
 * a weaker protection than a failing test.
 */

// Resolved from the project root rather than from `import.meta.url`: the
// jsdom environment does not give this module a file URL.
const SRC_DIR = resolve(process.cwd(), "src");

function sourceFiles(directory: string = SRC_DIR): string[] {
  const found: string[] = [];

  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);

    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      found.push(path);
    }
  }

  return found.sort();
}

function readSources(): { path: string; text: string }[] {
  return sourceFiles().map((path) => ({
    path: relative(SRC_DIR, path).split(sep).join("/"),
    text: readFileSync(path, "utf-8"),
  }));
}

/**
 * This file is the specification, not the application.
 *
 * It necessarily contains every pattern it forbids, so scanning itself would
 * report a violation for each rule. Excluding it is safe because it ships
 * nowhere: `src/**` test files are not part of the browser bundle. The
 * positive-control tests below prove the exclusion is not hiding anything.
 */
const GUARD_FILE = "test/guards.test.ts";

const SOURCES = readSources().filter(({ path }) => path !== GUARD_FILE);

/** Application source: everything that actually ships to a browser. */
const APPLICATION_SOURCES = SOURCES.filter(
  ({ path }) => !path.includes(".test.") && !path.startsWith("test/"),
);

function offenders(predicate: (text: string) => boolean): string[] {
  return SOURCES.filter(({ text }) => predicate(text)).map(({ path }) => path);
}

describe("the frontend has something to check", () => {
  it("found source files", () => {
    expect(SOURCES.length).toBeGreaterThan(10);
  });

  it("excludes only itself", () => {
    // A guard that quietly skipped application files would pass while
    // checking nothing.
    const all = readSources().map(({ path }) => path);
    const scanned = SOURCES.map(({ path }) => path);

    expect(all.filter((path) => !scanned.includes(path))).toEqual([GUARD_FILE]);
  });

  it("scans the application source, not just tests", () => {
    const application = SOURCES.filter(
      ({ path }) => !path.includes(".test.") && !path.startsWith("test/"),
    );

    expect(application.length).toBeGreaterThan(8);
  });
});

describe("the guards would catch a real violation", () => {
  const check = (text: string, pattern: RegExp) => pattern.test(text);

  it("detects a database connection string", () => {
    expect(
      check(
        'const url = "mysql://user:pw@host/db";',
        /(mysql|postgres|postgresql|mongodb|sqlite):\/\//i,
      ),
    ).toBe(true);
  });

  it("detects a stray fetch call", () => {
    expect(check("await fetch(url);", /[f]etch\s*\(/)).toBe(true);
  });

  it("detects localStorage use", () => {
    expect(check("localStorage.setItem(k, v);", /localStorage\s*[.[]/)).toBe(
      true,
    );
  });

  it("detects a hardcoded remote origin", () => {
    expect(
      check(
        'const base = "https://api.production.example.com";',
        /https?:\/\/(?!localhost|127\.0\.0\.1)[a-z0-9.-]+/i,
      ),
    ).toBe(true);
  });

  it("detects a signal action path", () => {
    expect(check('client.post("/api/v1/signals/x/approve")', /\/approve/)).toBe(
      true,
    );
  });
});

describe("the frontend never reaches the backend directly", () => {
  it("imports no Python backend module", () => {
    // There is no mechanism for this to work, which is exactly why a stray
    // path-like import would be a sign somebody misunderstood the boundary.
    expect(
      offenders(
        (text) => /from\s+["'][^"']*src\/aqos/.test(text) || /aqos\.(http_api|database|paper_trading|backtesting)/.test(text),
      ),
    ).toEqual([]);
  });

  it("opens no database connection", () => {
    expect(
      offenders((text) =>
        /(mysql|postgres|postgresql|mongodb|sqlite):\/\//i.test(text),
      ),
    ).toEqual([]);
  });

  it("carries no raw SQL", () => {
    expect(
      offenders((text) =>
        /\b(SELECT\s+\*|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+TABLE)\b/i.test(
          text,
        ),
      ),
    ).toEqual([]);
  });

  it("names no broker or venue integration", () => {
    // The account filters list the venue identifiers the API itself returns —
    // `mt5`, `binance` and so on. Those are values, not integrations, so the
    // pattern targets the libraries and bridges that would actually reach a
    // venue rather than the words.
    expect(
      offenders((text) =>
        /\b(MetaTrader5|mt5_bridge|binance-api|node-binance|ccxt|ib_insync|oandapyV20)\b/i.test(
          text,
        ),
      ),
    ).toEqual([]);
  });

  it("imports no broker client library", () => {
    expect(
      offenders((text) =>
        /from\s+["'](ccxt|binance|ib_insync|metaapi|oandapyV20)[^"']*["']/.test(text),
      ),
    ).toEqual([]);
  });

  it("exposes no backend filesystem artifact path", () => {
    // Application source only: a test that asserts `report_path` never appears
    // must itself name it, and flagging that is flagging the guard working.
    const found = APPLICATION_SOURCES.filter(({ text }) =>
      /(report_path|trades_path|equity_curve_path|orders_path|data_path|backtest_registry_path)/.test(
        text,
      ),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });
});

describe("no secret is referenced", () => {
  it("names no credential-shaped public variable outside the deny-list itself", () => {
    const allowed = new Set(["config/env.ts", "config/env.test.ts"]);
    const found = SOURCES.filter(
      ({ path, text }) =>
        !allowed.has(path) &&
        /NEXT_PUBLIC_\w*(SECRET|PASSWORD|TOKEN|CREDENTIAL|API_KEY|DATABASE_URL)/.test(
          text,
        ),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("hardcodes no production API URL", () => {
    // The origin comes from configuration. A literal one would ship the wrong
    // target in every build that forgot to override it.
    const allowed = new Set(["config/env.test.ts", "api/client.test.ts"]);
    const found = SOURCES.filter(
      ({ path, text }) =>
        !allowed.has(path) && /https?:\/\/(?!localhost|127\.0\.0\.1)[a-z0-9.-]+/i.test(text),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("reads the API origin only from the configuration module", () => {
    const allowed = new Set(["config/env.ts", "config/env.test.ts", "test/setup.ts"]);
    const found = SOURCES.filter(
      ({ path, text }) =>
        !allowed.has(path) && text.includes("NEXT_PUBLIC_AQOS_WEB_API_BASE_URL"),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });
});

describe("every request goes through the API client", () => {
  it("calls fetch nowhere else", () => {
    // One place decides the base URL, the token, the error shape and the
    // request id. A second one would have to re-decide all four.
    const allowed = new Set(["api/client.ts", "api/client.test.ts"]);
    const found = SOURCES.filter(
      ({ path, text }) => !allowed.has(path) && /\bfetch\s*\(/.test(text),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("uses no XMLHttpRequest or WebSocket", () => {
    expect(
      offenders((text) => /\b(XMLHttpRequest|new\s+WebSocket|EventSource)\b/.test(text)),
    ).toEqual([]);
  });
});

describe("only signal lifecycle actions exist in the UI", () => {
  /**
   * The six Sprint 059 signal lifecycle endpoints, and nothing else.
   *
   * These record what a signal *means*. Sprint 065 opened them deliberately.
   * Everything below proves the door did not open any wider: no execution, no
   * order, no paper session control, no account mutation.
   */
  const ALLOWED_ACTION_PATHS = [
    "/approve",
    "/reject",
    "/miss",
    "/expire",
    "/cancel",
    "/mark-pending-approval",
  ];

  /** Paths that would mean this app can move money or reach a venue. */
  const FORBIDDEN_ACTION_PATHS = [
    "/execute",
    "/orders",
    "/positions/",
    "/start",
    "/pause",
    "/resume",
    "/complete",
    "/fail",
    "/close",
  ];

  it.each(FORBIDDEN_ACTION_PATHS)("never calls %s", (forbidden) => {
    // Matched as a quoted path segment, not as a word. The action panel's
    // prose explains that these controls reach no broker, and "execution"
    // appearing in that sentence is the boundary being documented rather than
    // crossed.
    const found = APPLICATION_SOURCES.filter(
      ({ text }) =>
        text.includes(`"${forbidden}`) || text.includes(`${forbidden}"`),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("posts only from the API client and its resource wrappers", () => {
    const allowed = new Set(["api/client.ts", "api/resources.ts"]);
    const found = APPLICATION_SOURCES.filter(
      ({ path, text }) => !allowed.has(path) && /client\.post\s*</.test(text),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("declares exactly the approved write calls", () => {
    // Two for authentication, six for signal lifecycle. A ninth would be a
    // capability nobody approved.
    const resources = SOURCES.find(({ path }) => path === "api/resources.ts");
    const posts = resources?.text.match(/client\.post</g) ?? [];

    expect(posts.length).toBe(8);
  });

  it("targets only auth and signal endpoints with those writes", () => {
    const resources =
      SOURCES.find(({ path }) => path === "api/resources.ts")?.text ?? "";
    const targets = [...resources.matchAll(/API_PREFIX\}(\/[a-z-]+)/g)].map(
      (match) => match[1],
    );

    for (const target of targets) {
      expect([
        "/auth",
        "/signals",
        "/system",
        "/predictions",
        "/models",
        "/accounts",
        "/paper",
        "/backtests",
      ]).toContain(target);
    }
  });

  it("builds action paths only from the allow list", () => {
    const resources =
      SOURCES.find(({ path }) => path === "api/resources.ts")?.text ?? "";
    const declared = [...resources.matchAll(/^\s+(\w+): "([a-z-]+)",$/gm)].map(
      (match) => `/${match[2]}`,
    );

    for (const path of declared) {
      expect(ALLOWED_ACTION_PATHS).toContain(path);
    }
  });

  it("renders no order or session control", () => {
    // Scanned over application source only: a test that asserts the absence
    // of a "Place order" button has to name it, and flagging that would be
    // flagging the guard working.
    const found = APPLICATION_SOURCES.filter(({ text }) =>
      /(Place order|Submit order|Start session|Run backtest|Close position|Execute signal)/i.test(
        text,
      ),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });

  it("mutates no account", () => {
    expect(
      offenders((text) => /(createAccount|updateAccount|deleteAccount)/.test(text)),
    ).toEqual([]);
  });

  it("sends no metadata, category or severity on any action", () => {
    // The taxonomy decides both on the server. A client that could send them
    // could file a breached rule as informational.
    const resources =
      SOURCES.find(({ path }) => path === "api/resources.ts")?.text ?? "";

    // Matched as object properties, not as words: the module documents in
    // prose that it sends no metadata, and a guard that failed on its own
    // rationale would teach people to delete the rationale.
    for (const forbidden of [
      /\bmetadata\s*:/,
      /\bextra_metadata\s*:/,
      /\bseverity\s*:/,
      /\breason_category\s*:/,
    ]) {
      expect(forbidden.test(resources)).toBe(false);
    }
  });
});

describe("the session token is handled deliberately", () => {
  it("never uses localStorage", () => {
    // Matched as a property access rather than as a word: session.ts explains
    // in prose why localStorage is avoided, and a guard that failed on its own
    // rationale would be switched off.
    expect(
      offenders((text) => /localStorage\s*[.[]/.test(text)),
    ).toEqual([]);
  });

  it("never parses the token", () => {
    // AQOS sessions are opaque server-side rows. Decoding one would be
    // assuming a JWT, which this system does not issue.
    expect(
      offenders((text) => /(jwt_decode|jwtDecode|atob\s*\(|split\s*\(\s*["']\.["']\s*\))/.test(text)),
    ).toEqual([]);
  });

  it("touches storage only in the session module", () => {
    const allowed = new Set(["lib/session.ts"]);
    const found = SOURCES.filter(
      ({ path, text }) => !allowed.has(path) && /sessionStorage/.test(text),
    ).map(({ path }) => path);

    expect(found).toEqual([]);
  });
});
